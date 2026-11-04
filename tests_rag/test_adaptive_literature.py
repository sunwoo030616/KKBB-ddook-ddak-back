import json

import pytest

from rag_backend.adaptive_literature import AdaptiveLiteratureAgent
from rag_backend.knowledge_lab import KnowledgeStore

DOC={'id':'test:a','title':'Synthetic alpha','text':'Synthetic alpha describes a controlled mechanism with verifiable source evidence.',
     'kind':'abstract','source_url':'https://example.com/a'}


class Model:
    def __init__(self,value):self.value=value;self.calls=0
    def complete(self,*args,**kwargs):self.calls+=1;return {'text':json.dumps(self.value),'model_calls':1}


class Ranker:
    def __init__(self,ambiguous=False):self.calls=0;self.ambiguous=ambiguous
    def score_pairs(self,pairs):
        self.calls+=1
        return [.1 if self.ambiguous else 8. if 'alpha' in text else -8. for query,text in pairs]


def agent(tmp_path,model=None,ranker=None):
    store=KnowledgeStore(tmp_path/'knowledge.db')
    store.ingest([DOC,{**DOC,'id':'test:b','title':'Synthetic beta','text':DOC['text'].replace('alpha','beta')}])
    return AdaptiveLiteratureAgent(store,ranker or Ranker(),None,model)


def test_high_margin_supported_source_skips_generation_and_preserves_quote(tmp_path):
    model=Model({});result=agent(tmp_path,model).build('Find alpha mechanism')
    assert model.calls==0 and result['status']=='candidate_complete' and result['source_versions_current']
    edge=result['edges'][0];assert DOC['text'][edge['start']:edge['end']]==edge['text']


def test_missing_hardware_skips_every_model(tmp_path):
    model=Model({});ranker=Ranker();result=agent(tmp_path,model,ranker).build('RTX 5090 전력 소비량 측정값을 찾아줘.')
    assert result['status']=='not_found' and model.calls==ranker.calls==0


def test_uncertain_tasks_share_one_bounded_adjudication(tmp_path):
    model=Model({'choices':[0,1]});a=agent(tmp_path,model,Ranker(True))
    result=a.build('알파 연구와 베타 연구를 찾아줘.')
    assert model.calls==1 and len(result['edges'])==2
    assert result['status']=='candidate_complete'


@pytest.mark.parametrize('choice',[True,4,-2])
def test_invalid_choice_abstains_instead_of_inventing_source(tmp_path,choice):
    model=Model({'choices':[choice]});result=agent(tmp_path,model,Ranker(True)).build('Find the mechanism')
    assert result['edges']==[] and model.calls==1
    assert next(t for t in result['trace'] if t['step']=='adjudicate')['status']=='invalid_abstained'


def test_uncertainty_without_generator_remains_unapproved_and_abstains(tmp_path):
    result=agent(tmp_path,ranker=Ranker(True)).build('Find the mechanism')
    assert result['status']=='not_found' and result['edges']==[]


def test_source_change_during_adjudication_invalidates_all_candidates(tmp_path):
    a=agent(tmp_path,ranker=Ranker(True))
    class Changing(Model):
        def complete(self,*args,**kwargs):
            a.store.ingest([{**DOC,'text':DOC['text']+' Changed.'}]);return super().complete(*args,**kwargs)
    a.generator=Changing({'choices':[0]});result=a.build('Find the mechanism')
    assert result['status']=='stale_snapshot' and result['edges']==[]
