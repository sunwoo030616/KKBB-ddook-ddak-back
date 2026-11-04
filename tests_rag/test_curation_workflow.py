from concurrent.futures import ThreadPoolExecutor

import pytest

from rag_backend.curation_workflow import CurationWorkflow,WorkflowConflict
from rag_backend.knowledge_lab import KnowledgeStore

DOC={'id':'test:1','title':'Synthetic workflow fixture','text':'This synthetic document describes controlled source evidence for a local workflow test.',
     'source_url':'https://example.com/synthetic','kind':'abstract'}


class Clock:
    now=1000
    def __call__(self):return self.now


def setup(tmp_path):
    store=KnowledgeStore(tmp_path/'kb.db');store.ingest([DOC]);clock=Clock()
    return store,CurationWorkflow(store,clock=clock),clock


def candidate(job):
    d=job['document'];text=d['text']
    return {'source_id':d['id'],'source_hash':d['content_hash'],'quote':text,'start':0,'end':len(text),
            'category':'context','tags':['synthetic'],'status':'pending_review','source_url':d['source_url']}


def prepare(workflow):
    workflow.enqueue({'model':'fixture'},'test-v1');job=workflow.claim()
    assert workflow.complete(job,candidate(job));return job


def test_enqueue_identity_includes_version_model_and_prompt(tmp_path):
    store,w,c=setup(tmp_path)
    assert w.enqueue({'model':'a'},'v1')==1
    assert w.enqueue({'model':'a'},'v1')==0
    assert w.enqueue({'model':'b'},'v1')==1
    assert w.enqueue({'model':'a'},'v2')==1
    store.ingest([dict(DOC,text=DOC['text']+' Updated.')])
    assert w.enqueue({'model':'a'},'v1')==1


def test_concurrent_connections_cannot_own_same_job(tmp_path):
    store,w,c=setup(tmp_path);w.enqueue({'model':'a'},'v1')
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims=list(pool.map(lambda _:CurationWorkflow(store,clock=c).claim(),range(8)))
    assert len([j for j in claims if j])==1


def test_crash_recovery_fences_late_result_and_limits_retries(tmp_path):
    store,w,c=setup(tmp_path);w.enqueue({'model':'a'},'v1');first=w.claim(5)
    c.now+=6;second=CurationWorkflow(store,clock=c).claim(5)
    assert second['attempt']==2 and second['lease_token']!=first['lease_token']
    with pytest.raises(WorkflowConflict):w.complete(first,candidate(first))
    c.now+=6;third=w.claim(5);assert third['attempt']==3
    c.now+=6;assert w.claim(5) is None
    assert w.status()['states']=={'failed':1}


def test_source_update_invalidates_inflight_and_queued_work(tmp_path):
    store,w,c=setup(tmp_path);w.enqueue({'model':'a'},'v1');job=w.claim()
    store.ingest([dict(DOC,text=DOC['text']+' New source.')])
    assert w.complete(job,candidate(job)) is False
    assert w.status()['states']=={'stale':1}
    assert w.enqueue({'model':'a'},'v1')==1
    assert w.claim()['document']['text'].endswith('New source.')


def test_invalid_provenance_and_auto_approval_are_rejected(tmp_path):
    store,w,c=setup(tmp_path);w.enqueue({'model':'a'},'v1');job=w.claim()
    bad=candidate(job);bad['quote']='A fabricated statement that was never in this source.'
    with pytest.raises(ValueError):w.complete(job,bad)
    bad=candidate(job);bad['status']='approved'
    with pytest.raises(ValueError):w.complete(job,bad)
    bad=candidate(job);bad['start']=False
    with pytest.raises(ValueError):w.complete(job,bad)


def test_transient_failure_backoff_and_invalid_output_terminal(tmp_path):
    store,w,c=setup(tmp_path);w.enqueue({'model':'a'},'v1');job=w.claim()
    assert w.fail(job,'model_unavailable',retryable=True)=='queued'
    assert w.claim() is None
    c.now+=2;second=w.claim();assert second['attempt']==2
    assert w.fail(second,'invalid_output',retryable=True)=='failed'
    assert w.claim() is None


def test_review_requires_current_source_and_revision(tmp_path):
    store,w,c=setup(tmp_path);job=prepare(w)
    assert w.decide(job['id'],'approved','fixture-reviewer',0,'synthetic assertion')==1
    with pytest.raises(WorkflowConflict):w.decide(job['id'],'rejected','other',0,'outdated form')
    store.ingest([dict(DOC,text=DOC['text']+' Updated.')])
    with pytest.raises(WorkflowConflict):w.decide(job['id'],'approved','fixture-reviewer',1,'changed source')


def test_release_atomicity_revocation_and_source_change(tmp_path):
    store,w,c=setup(tmp_path);job=prepare(w)
    with pytest.raises(WorkflowConflict):w.publish([job['id']],'fixture-operator',0)
    w.decide(job['id'],'approved','fixture-reviewer',0,'synthetic assertion')
    release=w.publish([job['id']],'fixture-operator',0)
    assert release['revision']==1 and w.active()['valid']
    with pytest.raises(WorkflowConflict):w.publish([job['id']],'fixture-operator',0)
    w.decide(job['id'],'rejected','fixture-reviewer',1,'revoke approval')
    assert not w.active()['valid'] and w.active()['manifest']==[]
    w.decide(job['id'],'approved','fixture-reviewer',2,'new synthetic review')
    w.publish([job['id']],'fixture-operator',1)
    store.ingest([dict(DOC,text=DOC['text']+' Replaced.')])
    assert not w.active()['valid']
    with pytest.raises(WorkflowConflict):w.publish([job['id']],'fixture-operator',2)
    assert w.active()['revision']==2


def test_failed_publish_never_partially_updates_active_release(tmp_path):
    store,w,c=setup(tmp_path);job=prepare(w)
    w.decide(job['id'],'approved','fixture-reviewer',0,'synthetic assertion')
    with pytest.raises(WorkflowConflict):w.publish([job['id'],'unknown'],'fixture-operator',0)
    assert w.active()['revision']==0
    with store.connect() as db:assert db.execute('SELECT COUNT(*) FROM curation_releases').fetchone()[0]==0


def test_rollback_restores_reviewed_release_but_rejects_stale_source(tmp_path):
    store,w,c=setup(tmp_path);first=prepare(w)
    w.decide(first['id'],'approved','fixture-reviewer',0,'synthetic assertion')
    a=w.publish([first['id']],'fixture-operator',0)
    store.ingest([dict(DOC,id='test:2')]);w.enqueue({'model':'fixture'},'test-v1');second=w.claim()
    w.complete(second,candidate(second));w.decide(second['id'],'approved','fixture-reviewer',0,'synthetic assertion')
    w.publish([first['id'],second['id']],'fixture-operator',1)
    assert w.activate(a['id'],'fixture-operator',2)['revision']==3
    assert len(w.active()['manifest'])==1
    store.ingest([dict(DOC,text=DOC['text']+' Changed.')])
    with pytest.raises(WorkflowConflict):w.activate(a['id'],'fixture-operator',3)


def test_worker_is_pinned_to_model_prompt_and_never_self_approves(tmp_path):
    import json
    store,w,c=setup(tmp_path)
    class Model:
        identity={'model':'worker-fixture'}
        calls=0
        def complete(self,*args,**kwargs):
            self.calls+=1
            return {'text':json.dumps({'span_id':'s0','category':'context','tags':['fixture']})}
    model=Model();w.enqueue(model.identity,'worker-v1')
    assert w.work_one(model,'different-prompt')['state']=='idle' and model.calls==0
    assert w.work_one(model,'worker-v1')['state']=='prepared'
    assert w.work_one(model,'worker-v1')['state']=='idle' and model.calls==1
    assert w.status()['reviews']=={'pending':1}
    assert w.active()['valid'] is False


def test_audit_replays_history_and_detects_missing_review_event(tmp_path):
    store,w,c=setup(tmp_path);job=prepare(w)
    w.decide(job['id'],'approved','fixture-reviewer',0,'synthetic assertion')
    assert w.audit()['valid']
    with store.connect() as db:db.execute("DELETE FROM curation_events WHERE kind='reviewed'")
    assert w.audit()['problems']==[{'id':job['id'],'reason':'review_history_mismatch'}]


def test_audit_distinguishes_historical_source_from_corrupt_evidence(tmp_path):
    store,w,c=setup(tmp_path);job=prepare(w)
    store.ingest([dict(DOC,text=DOC['text']+' Updated.')])
    assert w.audit()['valid'] and w.audit()['historical_candidates']==1
    with store.connect() as db:db.execute("UPDATE versions SET payload=payload||' ' WHERE hash=?",(job['document']['content_hash'],))
    assert not w.audit()['valid']


def test_reviewed_search_never_exposes_pending_or_revoked_cards(tmp_path):
    store,w,c=setup(tmp_path);job=prepare(w)
    assert w.search_reviewed('source')['cards']==[]
    w.decide(job['id'],'approved','fixture-reviewer',0,'synthetic assertion')
    w.publish([job['id']],'fixture-operator',0)
    result=w.search_reviewed('source')
    assert result['status']=='ok' and len(result['cards'])==1
    assert result['cards'][0]['quote']==DOC['text'] and 'text' not in result['cards'][0]
    assert w.search_reviewed('source',kind='financial_summary')['cards']==[]
    w.decide(job['id'],'rejected','fixture-reviewer',1,'revoke approval')
    assert w.search_reviewed('source')['cards']==[]


def test_review_revoked_during_ranking_fails_closed(tmp_path):
    store,w,c=setup(tmp_path);job=prepare(w)
    w.decide(job['id'],'approved','fixture-reviewer',0,'synthetic assertion')
    w.publish([job['id']],'fixture-operator',0)
    class Ranker:
        def score_pairs(self,pairs):
            w.decide(job['id'],'rejected','fixture-reviewer',1,'revoked during scoring')
            return [1.0]*len(pairs)
    result=w.search_reviewed('source',reranker=Ranker())
    assert result['status']=='stale_release' and result['cards']==[]


def test_restoring_source_can_resume_stale_job_without_resetting_attempt_budget(tmp_path):
    store,w,c=setup(tmp_path);original=store.documents()[0]['content_hash']
    w.enqueue({'model':'fixture'},'v1');first=w.claim()
    store.ingest([dict(DOC,text=DOC['text']+' Updated.')])
    assert not w.complete(first,candidate(first))
    store.restore(DOC['id'],original)
    assert w.enqueue({'model':'fixture'},'v1')==1
    second=w.claim();assert second['id']==first['id'] and second['attempt']==2
    with pytest.raises(WorkflowConflict):w.complete(first,candidate(first))
    assert w.complete(second,candidate(second))
