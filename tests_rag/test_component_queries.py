from rag_backend.component_queries import component_queries,multi_query_scores


def test_query_views_keep_full_context_and_cap_work():
    message='예금을 깨는 비용을 비교하고, 매달 얼마씩 갚는지도 보고 싶어. 예금보호는 빼줘.'
    views=component_queries(message)
    assert views[0]==message and len(views)<=4
    assert any(v.startswith('매달') for v in views[1:])
    assert any('예금보호는 빼줘' in v for v in views[1:])


def test_clause_rank_normalization_can_recover_suppressed_second_intent():
    registry={'comparison':{'purpose':'비용 비교'},'repayment':{'purpose':'월 상환'}}
    class Ranker:
        def score_pairs(self,pairs):
            return [.9,.001,.8,.001,.001,.2]
    values,original,queries=multi_query_scores(Ranker(),'비용 비교를 해 보고, 매달 갚을 돈도 보자',['comparison','repayment'],registry)
    assert len(queries)==3 and original==[.9,.001]
    assert values[0]==1 and values[1]>.99


def test_flat_clause_scores_do_not_promote_unrelated_widgets():
    class Ranker:
        def score_pairs(self,pairs):return [.9,.001,.8,.001,.00002,.00002]
    values,_,_=multi_query_scores(Ranker(),'비용 비교를 해 보고, 아무 의미 없는 부연이야',
        ['comparison','repayment'],{'comparison':{'purpose':'비교'},'repayment':{'purpose':'상환'}})
    assert values[1]<.01


def test_retrieval_can_abstain_when_every_neural_match_is_weak():
    class Ranker:
        def score_pairs(self,pairs):return [.00002]*len(pairs)
    values,original,_=multi_query_scores(Ranker(),'지원하지 않는 주식 자동 매매',
        ['fx','loan'],{'fx':{'purpose':'환전'},'loan':{'purpose':'대출'}})
    assert values==[0,0] and original==[.00002,.00002]


def test_composer_abstains_before_llm_and_returns_trace(tmp_path):
    from rag_backend.canvas import CanvasComposer,ComposeRequest
    class WeakRanker:
        def score_pairs(self,pairs):return [.00002]*len(pairs)
    class NeverCallModel:
        def complete(self,*args,**kwargs):raise AssertionError('unsupported request reached LLM')
    composer=CanvasComposer(None,NeverCallModel(),tmp_path/'screens.db',WeakRanker())
    result=composer.compose(ComposeRequest(message='주식 시장가 자동 매수를 해줘',retrieval_mode='multi',review_mode='off'))
    assert result['status']=='clarify' and result['widgets']==[]
    assert result['trace'][0]['abstention']=='no_supported_component'
