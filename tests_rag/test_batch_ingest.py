import json

import pytest

from rag_backend.batch_ingest import ingest_jsonl
from rag_backend.knowledge_catalog import KnowledgeCatalog
from rag_backend.knowledge_lab import KnowledgeStore


def dataset(tmp_path,n=11):
    path=tmp_path/'records.jsonl'
    records=[{'id':f'test:{i:04d}','title':'Synthetic dataset paper','text':'Synthetic amber source evidence for batch transaction testing.',
        'kind':'abstract','source_url':'https://example.com/paper'} for i in range(n)]
    path.write_text(''.join(json.dumps(r)+'\n' for r in records));return path,records


def test_bounded_import_resumes_and_completed_dataset_is_a_noop(tmp_path):
    path,records=dataset(tmp_path);store=KnowledgeStore(tmp_path/'knowledge.db')
    first=ingest_jsonl(path,store,batch_size=4,max_batches=1)
    assert first['state']['seen']==4 and not first['state']['complete']
    second=ingest_jsonl(path,store,batch_size=4)
    assert second['state']['seen']==second['state']['changed']==len(records)
    assert second['state']['complete'] and len(store.documents())==11
    assert ingest_jsonl(path,store)['batches_this_run']==0


def test_crash_rolls_back_documents_fts_and_progress_together(tmp_path,monkeypatch):
    path,records=dataset(tmp_path);store=KnowledgeStore(tmp_path/'knowledge.db');original=store.ingest_in_transaction
    def crash(db,batch):
        original(db,batch);raise RuntimeError('simulated_process_failure_before_commit')
    monkeypatch.setattr(store,'ingest_in_transaction',crash)
    with pytest.raises(RuntimeError):ingest_jsonl(path,store,batch_size=4)
    assert store.documents()==[] and KnowledgeCatalog(store).search('amber')['hits']==[]
    with store.connect() as db:assert db.execute('SELECT seen,offset FROM ingestion_runs').fetchone()==(0,0)
    monkeypatch.setattr(store,'ingest_in_transaction',original)
    assert ingest_jsonl(path,store)['state']['changed']==len(records)


def test_invalid_batch_keeps_prior_checkpoint_and_never_partially_commits(tmp_path):
    path,records=dataset(tmp_path,5);records[3]['source_url']='file:///private/data'
    path.write_text(''.join(json.dumps(r)+'\n' for r in records));store=KnowledgeStore(tmp_path/'knowledge.db')
    with pytest.raises(ValueError):ingest_jsonl(path,store,batch_size=2)
    assert len(store.documents())==2
    with store.connect() as db:assert db.execute('SELECT seen,line FROM ingestion_runs').fetchone()==(2,2)


def test_oversized_line_is_rejected_without_unbounded_read(tmp_path):
    path=tmp_path/'large.jsonl';path.write_bytes(b'x'*65537);store=KnowledgeStore(tmp_path/'knowledge.db')
    with pytest.raises(ValueError,match='record_line_too_large'):ingest_jsonl(path,store)
    assert store.documents()==[]


def test_different_dataset_hash_has_independent_progress_and_preserves_history(tmp_path):
    path,records=dataset(tmp_path,1);store=KnowledgeStore(tmp_path/'knowledge.db');first=ingest_jsonl(path,store)
    records[0]['text']+=' Updated.';path.write_text(json.dumps(records[0])+'\n');second=ingest_jsonl(path,store)
    assert first['dataset_sha256']!=second['dataset_sha256']
    with store.connect() as db:assert db.execute('SELECT COUNT(*) FROM versions').fetchone()[0]==2
