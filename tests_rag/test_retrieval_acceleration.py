from rag_backend.retrieval_acceleration import CachedReranker,SpanPrefilter


class Base:
    def __init__(self):self.pairs=[]
    def score_pairs(self,pairs):self.pairs.extend(pairs);return [float(len(p[1])) for p in pairs]


def test_reranker_deduplicates_batches_and_invalidates_changed_text():
    base=Base();cache=CachedReranker(base,capacity=2)
    assert cache.score_pairs([('q','a'),('q','a'),('q','bb')])==[1,1,2]
    assert len(base.pairs)==2
    cache.score_pairs([('q','a')]);assert len(base.pairs)==2
    cache.score_pairs([('q','changed')]);assert len(base.pairs)==3 and len(cache.cache)==2


class Encoder:
    name='test-revision'
    def __init__(self):self.inputs=[]
    def encode(self,texts):
        self.inputs.extend(texts)
        return [[1.0 if 'tools' in t else 0.0,1.0 if 'memory' in t else 0.0] for t in texts]


def test_document_vectors_persist_but_query_vectors_do_not(tmp_path):
    encoder=Encoder();path=tmp_path/'vectors.db'
    spans=[({'id':'doc'},'s0',{'text':'tools reason'}),({'id':'doc'},'s1',{'text':'memory index'})]
    prefilter=SpanPrefilter(encoder,path)
    assert prefilter.select('tools',spans,1)[0][1]=='s0'
    assert prefilter.stats['embedded_spans']==2
    reopened=SpanPrefilter(encoder,path);reopened.select('tools',spans,1)
    assert reopened.stats['embedded_spans']==0 and reopened.stats['query_embeddings']==1
    changed=[(spans[0][0],'s0',{'text':'tools changed'}),spans[1]]
    reopened.select('tools',changed,1)
    assert reopened.stats['embedded_spans']==1


def test_prefilter_preserves_per_document_budget(tmp_path):
    prefilter=SpanPrefilter(Encoder(),tmp_path/'vectors.db')
    spans=[({'id':doc},str(i),{'text':'tools '+str(i)}) for doc in ('a','b') for i in range(5)]
    result=prefilter.select('tools',spans,2)
    assert len(result)==4 and sum(r[0]['id']=='a' for r in result)==2


def test_nonfinite_reranker_output_never_enters_cache():
    import pytest
    class Invalid(Base):
        def score_pairs(self,pairs):return [float('nan')]*len(pairs)
    cache=CachedReranker(Invalid())
    with pytest.raises(ValueError,match='nonfinite'):cache.score_pairs([('q','doc')])
    assert not cache.cache
