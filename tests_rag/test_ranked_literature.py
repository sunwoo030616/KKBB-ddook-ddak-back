import json

import pytest

from rag_backend.knowledge_lab import KnowledgeStore
from rag_backend.ranked_literature import RankedLiteratureSearch

ALPHA={'id':'test:alpha','title':'Synthetic alpha','text':'Alpha mechanisms describe controlled evidence for source retrieval in this synthetic fixture.',
       'source_url':'https://example.com/alpha','kind':'abstract'}
BETA={**ALPHA,'id':'test:beta','title':'Synthetic beta','text':'Beta mechanisms describe controlled evidence for source retrieval in this synthetic fixture.','source_url':'https://example.com/beta'}


class Ranker:
    def __init__(self):self.calls=0
    def score_pairs(self,pairs):
        self.calls+=1
        return [8. if ('alpha' in query.lower())==('Alpha' in text or 'alpha' in text) else -8. for query,text in pairs]


class Model:
    def __init__(self,values):self.values=iter(values);self.calls=0
    def complete(self,*args,**kwargs):
        self.calls+=1;return {'text':json.dumps(next(self.values)),'model_calls':1}


def search(tmp_path,model=None,ranker=None):
    store=KnowledgeStore(tmp_path/'knowledge.db');store.ingest([ALPHA,BETA])
    return RankedLiteratureSearch(store,model,ranker or Ranker(),None)


def test_english_retrieval_needs_no_generator_and_copies_server_evidence(tmp_path):
    result=search(tmp_path).build('Find alpha mechanisms')
    assert result['status']=='candidate_complete' and result['source_versions_current']
    assert len(result['edges'])==1
    edge=result['edges'][0]
    assert edge['source_id']==ALPHA['id'] and ALPHA['text'][edge['start']:edge['end']]==edge['text']
    assert not any(t['step'] in ('short_query_plan','bind_evidence') for t in result['trace'])


def test_two_korean_clauses_use_one_plan_without_final_generative_picker(tmp_path):
    model=Model([{'queries':['alpha mechanisms','beta mechanisms']}]);s=search(tmp_path,model)
    question='알파 연구와 베타 연구를 찾아줘.';result=s.build(question)
    assert model.calls==1 and result['status']=='candidate_complete'
    assert {e['source_id'] for e in result['edges']}=={ALPHA['id'],BETA['id']}
    assert all(question[t['anchor_start']:t['anchor_end']]==t['request_quote'] for t in result['tasks'])


@pytest.mark.parametrize('question',['Find RTX 5090 measured power consumption.','RTX 5090 전력 소비량 측정값을 찾아줘.'])
def test_absent_hardware_measurement_skips_generation_and_reranking(tmp_path,question):
    model=Model([]);ranker=Ranker();result=search(tmp_path,model,ranker).build(question)
    assert result['status']=='not_found' and model.calls==ranker.calls==0


@pytest.mark.parametrize('scores',[[0.,-.1],[-8.,-10.]])
def test_ambiguous_or_low_scoring_sources_abstain(tmp_path,scores):
    class Low:
        def score_pairs(self,pairs):return scores[:len(pairs)]
    result=search(tmp_path,ranker=Low()).build('Find alpha mechanisms')
    assert result['status']=='not_found' and result['edges']==[]


def test_title_match_does_not_override_weak_passage_support(tmp_path):
    class TitleOnly:
        def score_pairs(self,pairs):return [8. if '\n' in text and 'alpha' in text.lower() else -8. for q,text in pairs]
    assert search(tmp_path,ranker=TitleOnly()).build('Find alpha mechanisms')['edges']==[]


def test_malformed_plan_retries_once_then_stops_without_search(tmp_path):
    model=Model([{'queries':['alpha, beta']},{'queries':['alpha, beta']}]);ranker=Ranker()
    result=search(tmp_path,model,ranker).build('알파 연구를 찾아줘.')
    assert result['status']=='invalid_plan' and model.calls==2 and ranker.calls==0


def test_document_replacement_during_ranking_rejects_stale_evidence(tmp_path):
    s=search(tmp_path)
    class Replacing(Ranker):
        def score_pairs(self,pairs):
            s.store.ingest([{**ALPHA,'text':ALPHA['text']+' Replacement.'}])
            return super().score_pairs(pairs)
    s.reranker=Replacing();result=s.build('Find alpha mechanisms')
    assert result['status']=='stale_snapshot' and result['edges']==[]
