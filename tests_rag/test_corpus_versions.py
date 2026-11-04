import json

import pytest

from rag_backend.store import DocumentStore,DEFAULT_CORPUS


def test_snapshot_restore_recovers_exact_data_and_version(tmp_path):
    store=DocumentStore(tmp_path/'docs.db');first=store.ingest();original,_=store.load()
    bundle=json.loads(DEFAULT_CORPUS.read_text());bundle['chunks']=bundle['chunks'][:2]
    path=tmp_path/'new.json';path.write_text(json.dumps(bundle,ensure_ascii=False))
    second=store.ingest(path)
    assert second!=first and len(store.load()[0])==2
    assert store.restore(first)==first and store.load()[0]==original
    with pytest.raises(ValueError,match='Unknown'):store.restore('absent')


def test_invalid_ingest_cannot_destroy_last_valid_snapshot(tmp_path):
    store=DocumentStore(tmp_path/'docs.db');version=store.ingest()
    bad=json.loads(DEFAULT_CORPUS.read_text());bad['chunks'][0]['url']='https://unapproved.example/private'
    path=tmp_path/'bad.json';path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):store.ingest(path)
    assert store.load()[1]==version
