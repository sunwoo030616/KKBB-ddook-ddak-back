import hashlib
import json

import pytest

from rag_backend.fulltext import document_passages,enrich_document
from rag_backend.adaptive_literature import AdaptiveLiteratureAgent
from rag_backend.knowledge_lab import KnowledgeStore
from rag_backend.evidence_graph import EvidenceGraph

BASE={'id':'test:body','title':'Controlled retrieval','text':'We introduce a controlled retrieval system.',
      'kind':'abstract','source_url':'https://example.com/abstract'}


def enriched():
    a='The alpha mechanism verifies proposed tokens using the target model. '+'A controlled description with contextual details. '*5
    b='The beta mechanism corrects rejected tokens without changing the output distribution. '+'B controlled description with contextual details. '*5
    body=a+b;start=len(BASE['text'])+2
    return {**BASE,'abstract_text':BASE['text'],'text':BASE['text']+'\n\n'+body,'fulltext':{'pages':[
        {'page':2,'start':start,'end':start+len(body),'url':'https://example.com/paper.pdf#page=2',
         'text_sha256':hashlib.sha256(body.encode()).hexdigest()}]}}


def test_pdf_enrichment_is_bounded_versioned_and_idempotent(monkeypatch):
    class Page:
        def extract_text(self):return 'We introduce a mechanism.\nIts target distribution is unchanged.'
    class Reader:
        def __init__(self,*args):self.pages=[Page()]*4
    monkeypatch.setattr('pypdf.PdfReader',Reader)
    record=enrich_document(BASE,b'%PDF-synthetic','https://example.com/paper.pdf')
    assert len(record['fulltext']['pages'])==3
    assert enrich_document(record,b'%PDF-synthetic','https://example.com/paper.pdf')==record
    for page in record['fulltext']['pages']:
        text=record['text'][page['start']:page['end']]
        assert hashlib.sha256(text.encode()).hexdigest()==page['text_sha256']
    assert record['fulltext']['pdf_sha256']==hashlib.sha256(b'%PDF-synthetic').hexdigest()


@pytest.mark.parametrize('size,url',[(5_000_001,'https://example.com/a'),(1,'http://example.com/a')])
def test_untrusted_pdf_budget_rejected_before_parsing(size,url):
    with pytest.raises(ValueError,match='fulltext_source_budget'):enrich_document(BASE,b'a'*size,url)


def test_body_passages_retain_page_and_exact_normalized_text_offsets():
    record=enriched();spans=document_passages(record)
    body=[s for s in spans.values() if s['evidence_role']=='paper_body_context']
    assert body and all(s['page']==2 and s['citation_url'].endswith('#page=2') for s in body)
    assert all(record['text'][s['start']:s['end']]==s['text'] for s in spans.values())


def test_corrupt_fulltext_page_fails_before_model_scoring():
    record=enriched();record['text']+='x';record['fulltext']['pages'][0]['text_sha256']='0'*64
    with pytest.raises(ValueError,match='fulltext_hash'):document_passages(record)


class Ranker:
    def score_pairs(self,pairs):
        return [8. if 'alpha mechanism' in text or 'beta mechanism' in text else 2. for _,text in pairs]


class Selector:
    def __init__(self,slots):self.slots=slots;self.payload=None
    def complete(self,system,user,**kwargs):
        self.payload=json.loads(user)
        return {'text':json.dumps({'t0':self.slots}),'model_calls':1}


@pytest.mark.parametrize('slots,count',[(['a','b'],2),(['b'],1),([],0)])
def test_verifier_selects_each_citation_not_entire_document(tmp_path,slots,count):
    store=KnowledgeStore(tmp_path/'db');store.ingest([enriched()]);model=Selector(slots)
    result=AdaptiveLiteratureAgent(store,Ranker(),None,model).build('Find verification of proposed tokens')
    assert len(result['edges'])==count and result['source_versions_current']
    assert len(model.payload['tasks'][0]['candidates'])==2
    assert {c['slot'] for c in model.payload['tasks'][0]['candidates']}=={'a','b'}
    assert len({e['source_id'] for e in result['edges']})<=1
    if count:
        assert all(e.get('page')==2 for e in result['edges'])
        assert all(e['url'].endswith('#page=2') for e in result['edges'])
    if slots==['b']:
        assert 'beta mechanism' in result['edges'][0]['text']


def test_fulltext_update_invalidates_selected_quotes(tmp_path):
    store=KnowledgeStore(tmp_path/'db');record=enriched();store.ingest([record])
    result=AdaptiveLiteratureAgent(store,Ranker(),None,Selector(['a','b'])).build('Find verification of proposed tokens')
    store.ingest([{**record,'text':record['text']+' Changed.'}])
    assert not EvidenceGraph(store,None,Ranker()).validate(result)


def test_body_prefilter_preserves_abstract_candidates_and_caps_expensive_pairs(tmp_path):
    store=KnowledgeStore(tmp_path/'db');store.ingest([enriched()])
    class Prefilter:
        def __init__(self):self.body_count=0;self.budget=None
        def select(self,query,rows,per_document):
            self.body_count=len(rows);self.budget=per_document
            return rows[:1]
    prefilter=Prefilter();model=Selector(['a'])
    result=AdaptiveLiteratureAgent(store,Ranker(),prefilter,model).build('Find verification of proposed tokens')
    trace=next(t for t in result['trace'] if t['step']=='multilingual_retrieval')
    assert prefilter.budget==8 and prefilter.body_count>1
    assert trace['scored_passages']<=trace['unfiltered_passages']
    assert result['source_versions_current']


def test_catalog_reread_preserves_pdf_page_location(tmp_path):
    from rag_backend.knowledge_catalog import KnowledgeCatalog
    store=KnowledgeStore(tmp_path/'db');record=enriched();store.ingest([record]);current=store.documents()[0]
    page=record['fulltext']['pages'][0]
    reread=KnowledgeCatalog(store).source_span(record['id'],current['content_hash'],page['start'],page['start']+20)
    assert reread['citation_location']['kind']=='paper_body'
    assert reread['citation_location']['page']==2
    assert reread['citation_location']['url'].endswith('#page=2')
    assert reread['quote']==record['text'][page['start']:page['start']+20]
