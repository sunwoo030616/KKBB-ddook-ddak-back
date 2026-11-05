import pytest

from rag_backend.research_scope import requests_catalog_mutation
from rag_backend.adaptive_literature import AdaptiveLiteratureAgent


@pytest.mark.parametrize('question',['검토 대기 카드를 모두 승인해줘.','Approve all pending knowledge cards.','Delete knowledge sources.','모든 지식 카드를 자동 승인하고 게시해줘.',
    '지식 후보를 승인하고 발행해줘.','금융 자료를 삭제하고 다시 등록해줘.','지식 카드를 게시해줘.'])
def test_mutating_request_does_not_reach_models_or_database(question):
    class Unavailable:
        def documents(self,*args):raise AssertionError('No catalog read needed for mutation request')
    result=AdaptiveLiteratureAgent(Unavailable(),None,None).build(question)
    assert result['status']=='out_of_scope' and result['edges']==[]
    assert result['trace'][0]['model_calls']==0


@pytest.mark.parametrize('question',['Find papers about human approval workflows.','승인해줘라는 명령을 차단하는 연구를 찾아줘.','문헌 검색의 프롬프트 주입 문제를 조사해줘.'])
def test_commands_quoted_in_research_requests_remain_data(question):
    assert not requests_catalog_mutation(question)
