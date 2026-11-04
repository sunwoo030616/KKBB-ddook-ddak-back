from concurrent.futures import ThreadPoolExecutor
from threading import Event

from fastapi.testclient import TestClient

from rag_backend.app import create_app


def setup(tmp_path,monkeypatch,build):
    class Ranker:
        identity={'fixture':True}
        def score_pairs(self,pairs):return [1.]*len(pairs)
    class Encoder:
        name='synthetic-test'
        def encode(self,texts):return [[1.,0.] for _ in texts]
    monkeypatch.setattr('rag_backend.multilingual_literature.MultilingualLiteratureReranker',Ranker)
    monkeypatch.setattr('rag_backend.literature_reranker.EnglishLiteratureReranker',Ranker)
    monkeypatch.setattr('rag_backend.dense.LocalEncoder',Encoder)
    monkeypatch.setattr('rag_backend.adaptive_literature.AdaptiveLiteratureAgent.build',build)
    monkeypatch.setenv('KNOWLEDGE_DB_PATH',str(tmp_path/'knowledge.db'))
    return create_app(db_path=tmp_path/'finance.db',enable_dense=False,enable_research=False,enable_canvas=False)


def test_busy_research_returns_429_instead_of_waiting_in_another_model_queue(tmp_path,monkeypatch):
    started=Event();release=Event()
    def build(self,question):
        started.set();assert release.wait(3)
        return {'status':'not_found','latency_ms':0,'edges':[],'trace':[]}
    app=setup(tmp_path,monkeypatch,build)
    with TestClient(app) as client,ThreadPoolExecutor(max_workers=1) as pool:
        first=pool.submit(client.post,'/knowledge/research',json={'question':'synthetic query'})
        assert started.wait(1)
        try:assert client.post('/knowledge/research',json={'question':'another query'}).status_code==429
        finally:release.set()
        response=first.result();assert response.status_code==200
        body=response.json();assert body['mode']=='adaptive' and body['request_latency_ms']>=body['resource_setup_ms']>=0


def test_admission_is_released_after_an_endpoint_error(tmp_path,monkeypatch):
    calls=[]
    def build(self,question):
        calls.append(question)
        if len(calls)==1:raise RuntimeError('synthetic_failure')
        return {'status':'not_found','latency_ms':0,'edges':[],'trace':[]}
    app=setup(tmp_path,monkeypatch,build)
    with TestClient(app,raise_server_exceptions=False) as client:
        assert client.post('/knowledge/research',json={'question':'first query'}).status_code==500
        assert client.post('/knowledge/research',json={'question':'second query'}).status_code==200
