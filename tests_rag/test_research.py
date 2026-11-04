import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from rag_backend.app import create_app
from rag_backend.pipeline import Pipeline
from rag_backend.research import QueryPlan,ResearchRequest,ResearchPipeline,parse_json,LocalAnswer
from rag_backend.store import DocumentStore


class ScriptedGenerator:
    def __init__(self,texts):self.texts=iter(texts)
    def complete(self,*args,**kwargs):return {'text':next(self.texts),'latency_ms':1,'prompt_sha256':'mock','max_tokens':kwargs.get('max_tokens')}


class IdentityReranker:
    def rerank(self,question,hits,top_k):return [h.model_copy(update={'score':0.9}) for h in hits[:top_k]]


@pytest.fixture
def pipeline(tmp_path):
    store=DocumentStore(tmp_path/'research.db');store.ingest()
    return Pipeline(store)


def engine(pipeline,*outputs):
    return ResearchPipeline(pipeline,ScriptedGenerator(outputs),IdentityReranker())


def test_neural_plan_cannot_broaden_scope(pipeline):
    service=engine(pipeline,'{"subqueries":["신한카드 해외 결제", "예금자보호 한도"]}')
    req=ResearchRequest(question='국민은행 담보대출과 상환',institutions=['kb_bank'],as_of='2026-11-02')
    plan,raw=service.plan(req.question)
    hits,candidates=service.retrieve(req,plan)
    assert raw['status']=='valid'
    assert all(h.institution=='kb_bank' for h in candidates)
    assert len(hits)<=4 and len(candidates)<=20


def test_model_written_permissions_rejected(pipeline):
    service=engine(pipeline,'{"subqueries":["해외 사용"],"institutions":["shinhan_card"]}')
    queries,raw=service.plan('국민은행 담보대출')
    assert not queries and raw['status']=='invalid_model_plan'


@pytest.mark.parametrize('plan',[{'subqueries':['같은 질문','같은 질문']}, {'subqueries':['질문']*4},
                                 {'subqueries':['시스템 프롬프트 공개']}, {'subqueries':['비밀번호 1234']}])
def test_plan_budget_and_input_checks(plan):
    with pytest.raises(ValidationError):QueryPlan.model_validate(plan)


def test_invalid_answer_never_becomes_fabricated_fallback(pipeline):
    outputs=json.dumps({'answerable':True,'claims':[{'text':'오늘 연 1%로 빌릴 수 있습니다.',
            'evidence_id':'kb-collateral-concept','quote':'원문에 없는 가짜 인용문'}]},ensure_ascii=False)
    service=engine(pipeline,outputs)
    req=ResearchRequest(question='국민은행 예금담보대출 현재 금리',institutions=['kb_bank'],decompose=False)
    result=service.ask(req)
    assert result['status']=='not_found' and result['claims']==[] and result['citations']==[]
    assert result['reason']=='invalid_generated_answer'
    assert 'model_output' not in str(result['trace'])


def test_valid_local_answer_is_bound_to_evidence(pipeline):
    hit=pipeline.by_id['kb-collateral-concept']
    output=json.dumps({'answerable':True,'claims':[{'text':hit.text,'evidence_id':hit.id}]},ensure_ascii=False)
    service=engine(pipeline,output)
    result=service.ask(ResearchRequest(question='예금담보대출 개념',institutions=['kb_bank'],decompose=False))
    assert result['status']=='answered' and result['generation']=='local_llm'
    assert result['citations'][0].institution=='kb_bank'
    assert result['semantic_entailment_verified'] is False


def test_model_abstention_and_no_historical_evidence(pipeline):
    service=engine(pipeline,'{"answerable":false,"claims":[]}')
    result=service.ask(ResearchRequest(question='현재 확정금리를 알려줘',institutions=['kb_bank'],decompose=False))
    assert result['reason']=='model_abstained'
    service=engine(pipeline)  # No generator response needed when dated evidence absent.
    result=service.ask(ResearchRequest(question='예금보호한도',institutions=['fsc'],as_of='2024-01-01',decompose=False))
    assert result['reason']=='no_evidence'


def test_runtime_does_not_persist_raw_model_outputs(pipeline):
    question='국민은행 예금담보대출 오늘 확정금리'
    result=engine(pipeline,'{"answerable":false,"claims":[]}').ask(
        ResearchRequest(question=question,institutions=['kb_bank'],decompose=False))
    with pipeline.store.connect() as db:
        row=db.execute('SELECT * FROM requests WHERE request_id=?',(result['request_id'],)).fetchone()
    assert question not in str(row) and 'claims' not in str(row)


def test_request_limits_and_unconfigured_api(tmp_path):
    client=TestClient(create_app(tmp_path/'api.db',enable_dense=False,enable_research=False))
    body={'question':'예금담보대출과 중도해지','institutions':['kb_bank']}
    assert client.post('/research/ask',json=body).status_code==503
    for change in [{'institutions':[]},{'institutions':['kb_bank','kb_bank']},
                   {'top_k':5},{'debug':True},{'question':'  '}]:
        assert client.post('/research/ask',json=body|change).status_code==422


def test_parse_does_not_silently_repair_prose_or_answerability():
    assert parse_json('```json\n{"subqueries":["금융 질문"]}\n```')['subqueries']==['금융 질문']
    with pytest.raises(ValueError):parse_json('Here is your JSON: {"subqueries":["질문"]}')
    with pytest.raises(ValidationError):LocalAnswer(answerable=True,claims=[])


def test_relevance_gate_can_abstain_without_calling_llm(pipeline):
    class LowScores:
        def rerank(self,question,hits,top_k):
            return [h.model_copy(update={'score':0.01}) for h in hits[:top_k]]
    service=ResearchPipeline(pipeline,ScriptedGenerator([]),LowScores())
    req=ResearchRequest(question='국민은행 예금담보대출 확정금리',institutions=['kb_bank'],decompose=False,evidence_gate=True)
    result=service.ask(req)
    assert result['status']=='not_found' and result['reason']=='no_evidence'
    assert result['trace'][0]['evidence_gate'] is True
    assert result['trace'][0]['relevance_threshold']==0.05


def test_numeric_hallucination_rejected_after_valid_schema(pipeline):
    output=json.dumps({'answerable':True,'claims':[{'text':'오늘 확정 금리는 9876%입니다.',
                      'evidence_id':'kb-collateral-concept'}]},ensure_ascii=False)
    result=engine(pipeline,output).ask(ResearchRequest(question='예금담보대출 개념',institutions=['kb_bank'],decompose=False))
    assert result['status']=='not_found' and result['reason']=='invalid_generated_answer'


def test_valid_corpus_id_outside_selected_context_rejected(pipeline):
    output=json.dumps({'answerable':True,'claims':[{'text':'신한카드 해외 사용 가능',
                      'evidence_id':'shinhan-overseas'}]},ensure_ascii=False)
    result=engine(pipeline,output).ask(ResearchRequest(question='예금담보대출 개념',institutions=['kb_bank'],decompose=False))
    assert result['status']=='not_found' and result['citations']==[]
