from threading import Event
import uuid
import pytest

from rag_backend.canvas import ComposeRequest,ComposeConflict
from rag_backend.canvas_jobs import CanvasJobs,QueueFull,RequestConflict


class BlockingComposer:
    def __init__(self):self.started=Event();self.release=Event();self.calls=0
    def compose(self,req,progress):
        self.calls+=1;progress('planning');self.started.set()
        assert self.release.wait(3)
        return {'status':'composed','widgets':[]}


def test_retried_submission_runs_model_once_and_keeps_progress():
    composer=BlockingComposer();jobs=CanvasJobs(composer)
    req=ComposeRequest(message='여행 금융 화면');key=str(uuid.uuid4())
    try:
        first=jobs.submit(req,key);assert composer.started.wait(1)
        again=jobs.submit(req,key)
        assert first['job_id']==again['job_id'] and again['reused'] is True
        assert jobs.get(first['job_id'])['stage']=='planning'
        with pytest.raises(RequestConflict):jobs.submit(ComposeRequest(message='다른 화면'),key)
        composer.release.set();jobs.close()
        assert jobs.get(first['job_id'])['result']['status']=='composed' and composer.calls==1
    finally:composer.release.set();jobs.close()


def test_queue_capacity_and_provider_error_are_explicit():
    composer=BlockingComposer();jobs=CanvasJobs(composer,capacity=1)
    try:
        jobs.submit(ComposeRequest(message='금융 화면'),str(uuid.uuid4()))
        assert composer.started.wait(1)
        with pytest.raises(QueueFull):jobs.submit(ComposeRequest(message='다른 화면'),str(uuid.uuid4()))
    finally:composer.release.set();jobs.close()
    class Failed:
        def compose(self,*args,**kwargs):raise RuntimeError('DO_NOT_LEAK_PROVIDER_RESPONSE')
    jobs=CanvasJobs(Failed());result=jobs.submit(ComposeRequest(message='금융 화면'),str(uuid.uuid4()));jobs.close()
    status=jobs.get(result['job_id']);assert status['status']=='failed'
    assert 'DO_NOT_LEAK' not in str(status)


def test_completed_job_survives_restart_and_is_not_reexecuted(tmp_path):
    class Composer:
        def compose(self,req,progress):progress('planning');return {'status':'composed','widgets':[]}
    path=tmp_path/'jobs.db';req=ComposeRequest(message='원문은 작업 DB에 저장하지 않기');key=str(uuid.uuid4())
    jobs=CanvasJobs(Composer(),path=path);first=jobs.submit(req,key);jobs.close()
    reopened=CanvasJobs(Composer(),path=path)
    try:
        assert reopened.submit(req,key)['job_id']==first['job_id']
        result=reopened.get(first['job_id'])
        assert result['status']=='completed' and result['timings_ms']['total']>=result['timings_ms']['queued']
        assert req.message.encode() not in path.read_bytes()
    finally:reopened.close()


def test_interrupted_jobs_are_not_silently_replayed(tmp_path):
    import json,sqlite3,time
    path=tmp_path/'jobs.db';jobs=CanvasJobs(None,path=path);jobs.close()
    row={'job_id':'old','client_request_id':'key','fingerprint':'hash','status':'running','stage':'planning',
         'expires':time.time()+1000,'error':None,'result':None,'timings_ms':{}}
    with sqlite3.connect(path) as db:db.execute('INSERT INTO jobs VALUES(?,?)',('old',json.dumps(row)))
    reopened=CanvasJobs(None,path=path)
    try:assert reopened.get('old')['stage']=='interrupted'
    finally:reopened.close()


def test_expired_queued_job_never_reaches_the_model(monkeypatch):
    from types import SimpleNamespace
    clock=[0.0]
    monkeypatch.setattr('rag_backend.canvas_jobs.time',SimpleNamespace(time=lambda:clock[0]))
    composer=BlockingComposer();jobs=CanvasJobs(composer,capacity=2,max_wait=1)
    try:
        first=jobs.submit(ComposeRequest(message='먼저 실행'),str(uuid.uuid4()))
        assert composer.started.wait(1)
        second=jobs.submit(ComposeRequest(message='대기중 만료'),str(uuid.uuid4()))
        clock[0]=5;composer.release.set()
        # Let the queued task reach its deadline check; close() deliberately cancels it.
        jobs.executor.shutdown(wait=True,cancel_futures=False)
        assert composer.calls==1 and jobs.get(first['job_id'])['status']=='completed'
        assert jobs.get(second['job_id'])['status']=='failed'
        assert '대기시간' in jobs.get(second['job_id'])['error']['message']
    finally:composer.release.set();jobs.close()
