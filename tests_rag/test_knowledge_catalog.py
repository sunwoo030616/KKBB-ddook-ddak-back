import pytest

from rag_backend.knowledge_catalog import KnowledgeCatalog
from rag_backend.knowledge_lab import KnowledgeStore

DOC={'id':'test:a','title':'Synthetic retrieval paper','text':'Synthetic amber mechanism and source evidence for a controlled test.',
     'kind':'abstract','source_url':'https://example.com/a'}


def catalog(tmp_path):
    store=KnowledgeStore(tmp_path/'knowledge.db');store.ingest([DOC]);return KnowledgeCatalog(store)


def test_existing_rows_are_indexed_once_and_updates_remove_old_terms(tmp_path):
    c=catalog(tmp_path);assert c.search('amber')['hits'][0]['id']==DOC['id']
    KnowledgeCatalog(c.store)
    assert len(c.search('amber')['hits'])==1
    old_hash=c.store.documents()[0]['content_hash']
    c.store.ingest([{**DOC,'text':DOC['text'].replace('amber','cobalt')}])
    assert c.search('amber')['hits']==[] and len(c.search('cobalt')['hits'])==1
    c.store.restore(DOC['id'],old_hash)
    assert c.search('cobalt')['hits']==[] and len(c.search('amber')['hits'])==1
    with c.store.connect() as db:db.execute('DELETE FROM documents WHERE id=?',(DOC['id'],))
    assert c.search('amber')['hits']==[]


def test_keyset_pagination_and_kind_filter_use_index(tmp_path):
    c=catalog(tmp_path)
    c.store.ingest([{**DOC,'id':f'test:{i:03d}'} for i in range(105)]+[{**DOC,'id':'finance','kind':'financial_summary'}])
    ids=[];after=''
    while True:
        page=c.page(limit=20,after=after);ids += [r['id'] for r in page['records']]
        if not page['next_cursor']:break
        after=page['next_cursor']
    assert len(ids)==len(set(ids))==106 and 'finance' not in ids
    assert any('documents_kind_id' in row for row in c.query_plan())


def test_source_span_requires_current_hash_and_exact_bounded_offsets(tmp_path):
    c=catalog(tmp_path);hash=c.store.documents()[0]['content_hash']
    assert c.source_span(DOC['id'],hash,0,9)['quote']=='Synthetic'
    c.store.ingest([{**DOC,'text':DOC['text']+' Updated.'}])
    with pytest.raises(ValueError,match='stale_source_version'):c.source_span(DOC['id'],hash,0,9)


@pytest.mark.parametrize('query',['amber" OR *','amber; DROP TABLE documents;','"','amber NEAR( source )'])
def test_fts_query_syntax_is_treated_as_literal_terms(tmp_path,query):
    c=catalog(tmp_path);c.search(query)
    assert c.page()['records'][0]['id']==DOC['id']


def test_unchanged_batch_reuses_rowids_and_does_not_duplicate_fts(tmp_path):
    c=catalog(tmp_path)
    records=[{**DOC,'id':f'test:{i:04d}'} for i in range(801)]
    assert len(c.store.ingest(records)['changed'])==801
    with c.store.connect() as db:before=dict(db.execute('SELECT id,rowid FROM documents'))
    assert c.store.ingest(records)['unchanged']==801
    with c.store.connect() as db:
        assert before==dict(db.execute('SELECT id,rowid FROM documents'))
        assert db.execute('SELECT COUNT(*) FROM knowledge_fts').fetchone()[0]==802


def test_statistics_distinguish_versions_from_current_documents(tmp_path):
    c=catalog(tmp_path);c.store.ingest([{**DOC,'id':'test:b'}])
    c.store.ingest([{**DOC,'text':DOC['text']+' Updated.'}])
    result=c.statistics()
    assert result['kinds'][0]['documents']==result['indexed_documents']==2
    assert result['versions']==3
    assert result['duplicate_text_samples']==[]
