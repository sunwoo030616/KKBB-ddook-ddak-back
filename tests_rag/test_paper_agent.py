import json

from rag_backend.paper_agent import PaperAgent


class Model:
    def __init__(self,*actions):self.actions=iter(actions)
    def complete(self,*args,**kwargs):return {'text':json.dumps(next(self.actions)),'latency_ms':1}


RECORDS=[{'doi':'10.1234/real','title':'Retrieval augmented generation evidence evaluation','authors':['A'],'year':2024}]


def test_lookup_must_follow_actual_search_observation():
    agent=PaperAgent(RECORDS,Model({'action':'lookup','query':'','doi':'10.999/fabricated'}))
    result=agent.run('Find evidence evaluation papers')
    assert result['status']=='not_found' and result['records']==[]


def test_search_lookup_and_finish_return_exact_metadata():
    agent=PaperAgent(RECORDS,Model({'action':'search','query':'retrieval evidence','doi':''},
        {'action':'lookup','query':'','doi':'10.1234/real'},{'action':'finish','query':'','doi':''}))
    result=agent.run('근거 검색 평가 논문')
    assert result['records']==RECORDS and [t['tool'] for t in result['trace']]==['search','lookup','finish']


def test_tool_budget_is_bounded_when_model_repeats_search():
    action={'action':'search','query':'retrieval','doi':''}
    result=PaperAgent(RECORDS,Model(action,action,action)).run('검색')
    assert len(result['trace'])==3 and result['status']=='search_only'
