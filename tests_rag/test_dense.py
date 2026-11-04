from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from rag_backend.app import create_app
from rag_backend.dense import DenseIndex, fuse_rankings
from rag_backend.models import AskRequest
from rag_backend.pipeline import Pipeline
from rag_backend.store import DocumentStore


class FakeEncoder:
    name = 'fake-encoder-for-contract-tests-only'

    def __init__(self):
        self.encoded = 0

    def encode(self, texts):
        self.encoded += len(texts)
        return [[float('해외' in t), float('분실' in t), 1.0] for t in texts]


def test_embedding_cache_reuses_unchanged_documents(tmp_path):
    store = DocumentStore(tmp_path / 'docs.db')
    store.ingest()
    chunks, _ = store.load()
    encoder = FakeEncoder()
    a = DenseIndex(chunks, encoder, tmp_path / 'vectors.db')
    b = DenseIndex(chunks, encoder, tmp_path / 'vectors.db')
    assert a.new_embeddings == len(chunks)
    assert b.new_embeddings == 0 and b.cache_hits == len(chunks)
    assert encoder.encoded == len(chunks)


def test_content_change_invalidates_only_changed_vector(tmp_path):
    store = DocumentStore(tmp_path / 'docs.db')
    store.ingest()
    chunks, _ = store.load()
    encoder = FakeEncoder()
    DenseIndex(chunks, encoder, tmp_path / 'vectors.db')
    changed = [chunks[0].model_copy(update={'text': chunks[0].text + ' 검수한 추가 문장입니다.'}), *chunks[1:]]
    index = DenseIndex(changed, encoder, tmp_path / 'vectors.db')
    assert index.new_embeddings == 1 and index.cache_hits == len(chunks) - 1


def test_new_model_does_not_reuse_other_model_vectors(tmp_path):
    store = DocumentStore(tmp_path / 'docs.db')
    store.ingest()
    chunks, _ = store.load()
    first = FakeEncoder()
    DenseIndex(chunks, first, tmp_path / 'vectors.db')
    second = FakeEncoder()
    second.name = 'different-model'
    index = DenseIndex(chunks, second, tmp_path / 'vectors.db')
    assert index.new_embeddings == len(chunks) and index.cache_hits == 0


def test_dense_scope_and_rrf_do_not_duplicate_hits(tmp_path):
    store = DocumentStore(tmp_path / 'docs.db')
    store.ingest()
    index = DenseIndex(store.load()[0], FakeEncoder(), tmp_path / 'vectors.db')
    hits = index.search('분실', 'kb_card', 5)
    assert all(h.institution == 'kb_card' for h in hits)
    fused = fuse_rankings([hits, list(reversed(hits))], 5)
    assert len(fused) == len({h.chunk_id for h in fused}) == 5
    pipeline = Pipeline(store, dense_index=index)
    result = pipeline.ask(AskRequest(question='KB국민카드 분실신고', retriever='fusion'))
    assert result.status == 'answered'
    assert all(h.institution == 'kb_card' for h in result.citations)


def test_api_reports_unavailable_dense_mode(tmp_path):
    client = TestClient(create_app(tmp_path / 'docs.db', enable_dense=False))
    for endpoint in ('/ask', '/search'):
        response = client.post(endpoint, json={'question': '국민카드 분실신고', 'retriever': 'dense'})
        assert response.status_code == 503


def test_concurrent_requests_keep_separate_audit_rows(tmp_path):
    client = TestClient(create_app(tmp_path / 'docs.db', enable_dense=False))

    def ask(_):
        return client.post('/ask', json={'question': 'KB증권 체크카드 할부 가능해?'}).json()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(ask, range(12)))
    assert all(r['status'] == 'answered' for r in results)
    assert len({r['request_id'] for r in results}) == 12
