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
    kb=store(tmp_path);model=Model({'count':1},{'queries':['reasoning tool observations']},{'t0':['e0']})
    graph=EvidenceGraph(kb,model,Ranker())
    result=graph.build('A method combining reasoning and tool use','compact')
    assert len(result['tasks'])==1 and result['tasks'][0]['anchor_scope']=='whole_request'
    assert result['tasks'][0]['request_quote']=='A method combining reasoning and tool use'


def test_fast_prefilter_bounds_cross_encoder_span_work(tmp_path):
    kb=store(tmp_path)
    class Filter:
        def select(self,query,spans):return spans[:1]
    result=EvidenceGraph(kb,Model({'count':1},{'queries':['tool observations']},{'t0':['e0']}),Ranker(),prefilter=Filter()).build('Find tools','fast')
    assert next(t['scored_pairs'] for t in result['trace'] if t['step']=='span_search')==1


def test_fixed_need_count_rejects_extra_or_missing_queries(tmp_path):
    graph=EvidenceGraph(store(tmp_path),Model({'count':2},{'queries':['only one query']}),Ranker())
    assert graph.build('Compare two independent methods','compact')['status']=='invalid_plan'


def test_missing_named_hardware_measurement_skips_retrieval_and_selector(tmp_path):
    class NeverRank:
        def score_pairs(self,pairs):raise AssertionError('unsupported hardware must not be scored')
    result=EvidenceGraph(store(tmp_path),Model(),NeverRank()).build('Measured RTX 5090 power consumption','single')
    assert result['status']=='not_found' and result['missing_task_ids']==['t0']
    assert any(t['step']=='measurement_source_presence' for t in result['trace'])


def test_measurement_entity_gate_does_not_block_a_method_task(tmp_path):
    graph=EvidenceGraph(store(tmp_path),Model({'count':2},{'queries':['reasoning tool observations','RTX 5090 power consumption']},{'t0':['e0'],'t1':[]}),Ranker())
    result=graph.build('Find tool observations and RTX 5090 power consumption','compact')
    assert result['status']=='partial' and result['missing_task_ids']==['t1']


def test_hardware_presence_is_whitespace_tolerant_but_not_a_variant_substring():
    from rag_backend.evidence_graph import mentions_entities
    assert mentions_entities('We used RTX 5090 in the experiment.',['RTX5090'])
    assert not mentions_entities('We used RTX5090Ti in the experiment.',['RTX5090'])


def test_anchored_mode_uses_server_offsets_and_skips_count_model(tmp_path):
    question='Find tool observations; find a second method.'
    model=Model({'query':'tool observations'},{'query':'second method'},{'choices':[0,-1]})
    result=EvidenceGraph(store(tmp_path),model,Ranker(),per_clause=True,binding_format='ordinal').build(question,'anchored')
    assert result['status']=='partial'
    assert not any(t['step']=='count_needs' for t in result['trace'])
    assert result['tasks'][0]['anchor_scope']=='exact_quote'
    for task in result['tasks']:
        assert question[task['anchor_start']:task['anchor_end']]==task['request_quote']


def test_korean_postpositions_do_not_hide_measurement_system_identifiers(tmp_path):
    from rag_backend.evidence_graph import measurement_entities
    assert 'Apple M4' in measurement_entities('Apple M4에서 측정한 전력 소비량','measured power consumption')
    assert 'MI300X' in measurement_entities('AMD MI300X에서 전력 실측값','measured power consumption')
    result=EvidenceGraph(store(tmp_path),Model({'query':'Apple M4 measured power consumption'}),Ranker(),per_clause=True).build('Apple M4에서 전력 실측값을 찾아줘.','anchored')
    assert result['status']=='not_found' and result['missing_task_ids']==['t0']


def test_invalid_query_plan_has_one_bounded_repair(tmp_path):
    graph=EvidenceGraph(store(tmp_path),Model({'query':'# invalid'},{'query':'tool observations'},{'choices':[0]}),Ranker(),per_clause=True,binding_format='ordinal')
    result=graph.build('Find tool observations','anchored')
    plans=[t for t in result['trace'] if t['step']=='compact_plan']
    assert result['status']=='candidate_complete' and [p['status'] for p in plans]==['rejected','validated']


def test_fixed_ordinal_decoder_still_checks_actual_candidate_pool(tmp_path):
    result=EvidenceGraph(store(tmp_path),Model({'queries':['tool observations']},{'choices':[2]}),Ranker(),binding_format='ordinal').build('Find tool observations','anchored')
    assert result['status']=='invalid_selection' and result['edges']==[]


def test_boolean_cannot_masquerade_as_a_selection_index(tmp_path):
    result=EvidenceGraph(store(tmp_path),Model({'queries':['tool observations']},{'choices':[True]}),Ranker(),binding_format='ordinal').build('Find tool observations','anchored')
    assert result['status']=='invalid_selection'


def test_korean_measurement_intent_is_available_before_query_generation():
    from rag_backend.evidence_graph import measurement_entities
    assert measurement_entities('RTX 5090 전력 측정값','RTX 5090 전력 측정값')==['RTX 5090']
    assert measurement_entities('A100을 사용하는 방법','A100을 사용하는 방법')==[]


def test_snapshot_checks_selected_sources_even_without_an_edge(tmp_path):
    kb=store(tmp_path);other=dict(DOC,id='paper:2');kb.ingest([other])
    class ChangesUnusedSource(Model):
        def complete(self,*args,**kwargs):
            kb.ingest([dict(other,text='A different source replaced during selection without a selected edge.')])
            return super().complete(*args,**kwargs)
    result=EvidenceGraph(kb,ChangesUnusedSource({'t0':['e0']}),Ranker()).build('tool observations','single')
    assert result['status']=='stale_snapshot' and result['edges']==[]


def test_default_anchored_group_plan_preserves_verified_source(tmp_path):
    kb=store(tmp_path)
    result=EvidenceGraph(kb,Model({'queries':['tool observations']},{'t0':['e0']}),Ranker()).build('Find tool observations','anchored')
    assert result['status']=='candidate_complete' and result['source_versions_current']
    edge=result['edges'][0]
    assert DOC['text'][edge['start']:edge['end']]==edge['text']
    assert next(t for t in result['trace'] if t['step']=='bind_evidence')['format']=='evidence_ids'
