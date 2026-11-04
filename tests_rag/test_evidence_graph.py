import json

from rag_backend.evidence_graph import EvidenceGraph
from rag_backend.knowledge_lab import KnowledgeStore


DOC={'id':'paper:1','title':'Tool observations','text':'Reasoning and external tool observations can update the next action in a controlled process.',
     'kind':'abstract','source_url':'https://example.com/paper'}


class Ranker:
    def score_pairs(self,pairs):return [.8]*len(pairs)


class Model:
    def __init__(self,*outputs):self.outputs=iter(outputs)
    def complete(self,*args,**kwargs):return {'text':json.dumps(next(self.outputs)),'latency_ms':1}


def store(tmp_path):
    kb=KnowledgeStore(tmp_path/'kb.db');kb.ingest([DOC]);return kb


def test_graph_returns_exact_source_offsets_and_detects_changed_documents(tmp_path):
    kb=store(tmp_path);model=Model({'tasks':[{'request_quote':'tool observations','query':'tool observations'}]}, {'t0':['e0']})
    graph=EvidenceGraph(kb,model,Ranker());result=graph.build('Find tool observations')
    assert result['status']=='candidate_complete' and graph.validate(result)
    edge=result['edges'][0];assert DOC['text'][edge['start']:edge['end']]==edge['text']
    kb.ingest([dict(DOC,text='A changed paper now describes different external observations.')])
    assert not graph.validate(result)


def test_model_cannot_add_a_request_that_user_did_not_make(tmp_path):
    graph=EvidenceGraph(store(tmp_path),Model({'tasks':[{'request_quote':'invented ask','query':'tool observations'}]}),Ranker())
    assert graph.build('Find tool observations')['status']=='invalid_plan'


def test_unseen_evidence_ids_are_rejected(tmp_path):
    graph=EvidenceGraph(store(tmp_path),Model({'t0':['forged']}),Ranker())
    assert graph.build('Find tool observations','single')['status']=='invalid_selection'


def test_empty_selection_exposes_missing_task_instead_of_claiming_success(tmp_path):
    graph=EvidenceGraph(store(tmp_path),Model({'t0':[]}),Ranker())
    result=graph.build('GPU energy measurements','single')
    assert result['status']=='not_found' and result['missing_task_ids']==['t0']


def test_empty_corpus_never_reaches_selection_model(tmp_path):
    kb=KnowledgeStore(tmp_path/'empty.db');graph=EvidenceGraph(kb,Model(),Ranker())
    result=graph.build('Find tool observations','single')
    assert result['status']=='not_found' and result['selected_document_ids']==[]


def test_multiple_tasks_share_three_document_budget(tmp_path):
    kb=store(tmp_path)
    kb.ingest([dict(DOC,id='paper:'+str(i),title='Study '+str(i)) for i in range(2,7)])
    model=Model({'tasks':[{'request_quote':q,'query':q} for q in ('first','second','third')]},
                {'t0':[],'t1':[],'t2':[]})
    result=EvidenceGraph(kb,model,Ranker()).build('first second third')
    assert len(result['selected_document_ids'])<=3


def test_equivalent_dynamic_schemas_share_grammar_key_but_different_domains_do_not():
    from pydantic import create_model
    from typing import Literal
    from rag_backend.research_models import schema_fingerprint
    a=create_model('SameBindings',choice=(Literal['e0','e1'],...))
    b=create_model('SameBindings',choice=(Literal['e0','e1'],...))
    c=create_model('SameBindings',choice=(Literal['e0','e2'],...))
    assert a is not b and schema_fingerprint(a)==schema_fingerprint(b)
    assert schema_fingerprint(a)!=schema_fingerprint(c)


def test_source_change_during_selection_cannot_return_fresh_evidence(tmp_path):
    kb=store(tmp_path)
    class ChangingModel(Model):
        def complete(self,*args,**kwargs):
            kb.ingest([dict(DOC,text='The source was replaced while inference was running.')])
            return super().complete(*args,**kwargs)
    graph=EvidenceGraph(kb,ChangingModel({'t0':['e0']}),Ranker())
    result=graph.build('tool observations','single')
    assert result['status']=='stale_snapshot' and result['edges']==[]
    assert result['source_versions_current'] is False


def test_compact_plan_keeps_server_owned_request_provenance(tmp_path):
    kb=store(tmp_path);model=Model({'queries':['reasoning tool observations']},{'t0':['e0']})
    graph=EvidenceGraph(kb,model,Ranker())
    result=graph.build('A method combining reasoning and tool use','compact')
    assert len(result['tasks'])==1 and result['tasks'][0]['anchor_scope']=='whole_request'
    assert result['tasks'][0]['request_quote']=='A method combining reasoning and tool use'


def test_fast_prefilter_bounds_cross_encoder_span_work(tmp_path):
    kb=store(tmp_path)
    class Filter:
        def select(self,query,spans):return spans[:1]
    result=EvidenceGraph(kb,Model({'queries':['tool observations']},{'t0':['e0']}),Ranker(),prefilter=Filter()).build('Find tools','fast')
    assert next(t['scored_pairs'] for t in result['trace'] if t['step']=='span_search')==1
