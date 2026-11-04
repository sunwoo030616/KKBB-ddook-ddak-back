from scripts.evaluate_expanded_retrieval import summarize


def row(id,mode,hit=True,language='en'):
    return dict(id=id,mode=mode,language=language,hit_at_1=hit,hit_at_3=hit,
                rr_at_3=float(hit),seconds=1.0,scored_pairs=10,target_in_pool=True)


def test_interrupted_model_compares_only_identical_english_queries():
    result=summarize({'rows':[row('a','bge_dense10'),row('a','tiny_en_dense10',False),
        row('b','tiny_en_dense10'),row('c','bge_dense10',language='ko')]})
    assert result['summary']['tiny_en_dense10']['en']['n']==2
    assert result['paired_english']['query_ids']==['a']
    assert result['paired_english']['modes']['tiny_en_dense10']['hit_at_1']==0
    assert result['paired_english']['modes']['bge_dense10']['n']==1


def test_disjoint_queries_cannot_produce_a_paired_comparison():
    result=summarize({'rows':[row('a','bge_dense10'),row('b','tiny_en_dense10')]})
    assert result['paired_english']['n']==0
    assert all(m['median_seconds'] is None and m['mrr_at_3'] is None
               for m in result['paired_english']['modes'].values())
