from copy import deepcopy
import json

import pytest

from rag_backend.knowledge_lab import KnowledgeStore

DOC={'id':'paper:1','title':'Retrieval study','text':'This study evaluates retrieval quality with a small controlled experiment.',
     'source_url':'https://example.com/paper','kind':'abstract'}


class Model:
    identity={'revision':'test'}
    def __init__(self,quote=None):self.calls=0;self.quote=quote
    def complete(self,*args,**kwargs):
        self.calls+=1;return {'text':json.dumps({'category':'method','span_id':'forged' if self.quote else 's0','tags':['retrieval']}),'latency_ms':1}


def test_incremental_run_does_not_repeat_ai_calls(tmp_path):
    store=KnowledgeStore(tmp_path/'kb.db');model=Model()
    assert store.ingest([DOC])['changed']==['paper:1']
    assert store.prepare_notes(model)['processed']==1
    assert store.ingest([DOC])['unchanged']==1
    assert store.prepare_notes(model)['reused']==1 and model.calls==1
    note=store.notes()[0];assert DOC['text'][note['start']:note['end']]==note['quote']
    assert note['status']=='pending_review'


def test_changed_documents_invalidate_notes_and_rollback_restores_them(tmp_path):
    store=KnowledgeStore(tmp_path/'kb.db');store.ingest([DOC]);old=store.documents()[0]['content_hash']
    store.prepare_notes(Model());updated=dict(DOC,text='A different source version with new information.')
    store.ingest([updated]);assert store.notes()==[]
    store.restore(DOC['id'],old);assert len(store.notes())==1


def test_fabricated_quote_is_not_promoted_or_retried_silently(tmp_path):
    store=KnowledgeStore(tmp_path/'kb.db');store.ingest([DOC]);model=Model('A fabricated sentence missing from source')
    assert store.prepare_notes(model)['failed']==1 and store.notes()==[]
    assert store.prepare_notes(model)['reused']==1 and model.calls==1


def test_batch_validation_is_atomic_and_search_is_kind_scoped(tmp_path):
    store=KnowledgeStore(tmp_path/'kb.db')
    with pytest.raises(ValueError):store.ingest([DOC,dict(DOC,id='bad',source_url='file:///secret')])
    assert store.documents()==[]
    store.ingest([DOC,dict(DOC,id='finance:1',kind='financial_summary')])
    assert [r['id'] for r in store.search('retrieval',kind='abstract')]==['paper:1']


def test_neural_fallback_can_search_without_english_keyword_overlap(tmp_path):
    class Ranker:
        def score_pairs(self,pairs):return [.8]*len(pairs)
    store=KnowledgeStore(tmp_path/'kb.db');store.ingest([DOC])
    assert store.search('근거 검색')==[]
    assert store.search('근거 검색',reranker=Ranker())[0]['id']=='paper:1'


def test_lazy_model_loads_only_when_work_reaches_generation(monkeypatch,tmp_path):
    from rag_backend import research_models
    monkeypatch.setattr(research_models,'manifest',lambda role:(tmp_path,{'revision':'test'}))
    class Generator(Model):
        def __init__(self,role):super().__init__()
    monkeypatch.setattr(research_models,'MLXGenerator',Generator)
    lazy=research_models.LazyMLXGenerator()
    assert lazy.loads==0
    lazy.complete('system','user');lazy.complete('system','another')
    assert lazy.loads==1


def test_knowledge_api_validation_and_optional_neural_dependency(monkeypatch,tmp_path):
    from fastapi.testclient import TestClient
    from rag_backend.app import create_app
    path=tmp_path/'knowledge.db';KnowledgeStore(path).ingest([DOC])
    monkeypatch.setenv('KNOWLEDGE_DB_PATH',str(path))
    with TestClient(create_app(tmp_path/'corpus.db',enable_dense=False,enable_research=False,enable_canvas=False)) as client:
        assert client.get('/knowledge/status').json()['documents']==1
        response=client.post('/knowledge/search',json={'question':'retrieval','mode':'lexical'})
        assert response.status_code==200 and response.json()['hits'][0]['id']=='paper:1'
        assert client.post('/knowledge/search',json={'question':'retrieval','mode':'neural'}).status_code==503
        assert client.post('/knowledge/search',json={'question':'retrieval','kind':'private_files'}).status_code==422
