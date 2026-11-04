import json
from datetime import date

import pytest

from rag_backend.evidence_agent import EvidenceAgent, bind_knowledge
from rag_backend.canvas import CanvasComposer, ComposeRequest
from rag_backend.pipeline import Pipeline
from rag_backend.store import DocumentStore


class Model:
    def __init__(self, *actions): self.actions=iter(actions);self.calls=0
    def complete(self,*args,**kwargs):
        self.calls+=1
        return {'text':json.dumps(next(self.actions),ensure_ascii=False),'latency_ms':1}


def search(topic, query='예금보호 한도'):
    return {'action':'search','queries':[{'topic':topic,'query':query}]}


@pytest.fixture
def pipeline(tmp_path):
    store=DocumentStore(tmp_path/'docs.db');store.ingest();return Pipeline(store)


def test_model_may_retry_only_missing_topics_and_quotes_are_server_owned(pipeline):
    model=Model(search('funding_compare','예금 중도해지 담보대출 비교'),
                {'action':'search','queries':[{'topic':t,'query':'예금 대출 상환 조건 입력'}
                                           for t in ('funding_inputs','collateral_close')]})
    result=EvidenceAgent(pipeline,model).run('비교 조건', ['funding_comparison_widget'], 'kb_card', date(2026,11,4))
    assert model.calls==2 and result['status']=='complete'
    for hits in result['evidence_by_topic'].values():
        for h in hits:assert h['text']==pipeline.by_id[h['chunk_id']].text
    assert {s['institution'] for s in result['trace'] if s['step']=='evidence_search'}=={'kb_bank'}


def test_invalid_scope_cannot_retrieve_an_unrequested_topic(pipeline):
    model=Model(search('release'))
    result=EvidenceAgent(pipeline,model).run('보호', ['deposit_protection_widget'], 'kb_card',date(2026,11,4))
    assert result['status']=='not_found' and not result['evidence_by_topic']
    assert result['trace'][0]['action']=='invalid_plan'


def test_date_scope_and_retry_budget_are_enforced(pipeline):
    model=Model(search('protection'),search('protection','보호 원금 이자'))
    result=EvidenceAgent(pipeline,model).run('보호', ['deposit_protection_widget'], 'kb_card',date(2025,1,1))
    assert model.calls==2 and result['status']=='not_found'
    assert result['missing_topics']==['protection']


def test_once_mode_and_clarification_do_not_loop(pipeline):
    for action in (search('protection'),{'action':'clarify','queries':[]}):
        model=Model(action)
        result=EvidenceAgent(pipeline,model).run('보호',['deposit_protection_widget'],'kb_card',date(2025,1,1),'once')
        assert model.calls==1 and result['status']=='not_found'


def test_irrelevant_widgets_do_not_call_model(pipeline):
    model=Model()
    assert EvidenceAgent(pipeline,model).run('상환표',['loan_repayment_schedule_widget'],'kb_bank',date(2026,11,4)) is None
    assert model.calls==0


def test_bank_security_device_release_is_not_payment_card_evidence(pipeline):
    model=Model(search('release','분실신고 해제'),{'action':'clarify','queries':[]})
    result=EvidenceAgent(pipeline,model).run('카드 해제',['card_recovery_widget'],'kb_bank',date(2026,11,4))
    assert result['status']=='not_found' and result['evidence_by_topic']=={}


def test_citations_are_bound_only_to_their_widget(pipeline):
    result=EvidenceAgent(pipeline,Model(search('protection'))).run('보호',['deposit_protection_widget'],'kb_card',date(2026,11,4))
    nodes=bind_knowledge([{'type':'deposit_protection_widget'},{'type':'loan_inputs_widget'}],result)
    assert nodes[0]['knowledge']['evidence'] and 'knowledge' not in nodes[1]


def test_real_composer_path_retains_evidence_on_zero_call_form_update(pipeline,tmp_path):
    plan={'title':'예금 비교','widgets':[{'type':'funding_comparison_widget','priority':1}],'clarification':''}
    queries={'action':'search','queries':[{'topic':t,'query':'예금 대출 해지 비교 조건'}
                                         for t in ('funding_compare','funding_inputs','collateral_close')]}
    model=Model(plan,queries)
    composer=CanvasComposer(pipeline,model,tmp_path/'screens.db')
    first=composer.compose(ComposeRequest(message='예금 해지 비교',evidence_mode='adaptive'))
    second=composer.compose(ComposeRequest(message='입력한 조건으로 계산해줘',session_id=first['session_id'],expected_revision=1,
        evidence_mode='adaptive',calculation={'kind':'funding_comparison','maturity_interest_net_won':'1000000',
        'early_interest_net_won':'300000','loan_principal_won':'10000000','annual_loan_rate_percent':'3.65',
        'loan_days':100,'extra_loan_cost_won':'10000'}))
    assert model.calls==2
    node=next(n for n in second['widgets'] if n['type']=='funding_comparison_widget')
    assert node['knowledge']['evidence'] and node['data']['values']['interest_difference_won']=='590000'
