"""Bounded background UI-composition jobs with idempotent submission and real stage updates."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import hashlib
import json
import time
import uuid
import sqlite3
from pathlib import Path

from fastapi.encoders import jsonable_encoder

from .canvas import ComposeConflict


class QueueFull(Exception):pass
class RequestConflict(Exception):pass


class CanvasJobs:
    def __init__(self,composer,capacity=8,ttl=1800,path=None,max_wait=120):
        self.composer=composer;self.capacity=capacity;self.ttl=ttl
        self.path=Path(path) if path else None;self.max_wait=max_wait
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='canvas')
        self.lock=Lock();self.jobs={};self.keys={}
        if self.path:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            with sqlite3.connect(self.path) as db:
                db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
                for id,payload in db.execute('SELECT id,payload FROM jobs'):
                    job=json.loads(payload)
                    if job['expires']<time.time():continue
                    if job['status'] in ('queued','running'):
                        job.update(status='failed',stage='interrupted',error={'status':503,
                                   'message':'서버가 재시작되어 작업이 중단됐습니다. 최신 화면에서 새 요청을 보내주세요.'})
                    self.jobs[id]=job;self.keys[job['client_request_id']]=id
            self._persist()

    def _persist(self):
        # One local server process owns this queue. Never persist the request text.
        if self.path:
            with sqlite3.connect(self.path) as db:
                db.execute('DELETE FROM jobs')
                db.executemany('INSERT INTO jobs VALUES(?,?)',[(id,json.dumps(job,ensure_ascii=False))
                                                           for id,job in self.jobs.items()])

    def submit(self,request,client_request_id):
        fingerprint=hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        with self.lock:
            now=time.time()
            expired=[id for id,j in self.jobs.items() if j['expires']<now and j['status'] in ('completed','failed')]
            for id in expired:
                del self.keys[self.jobs[id]['client_request_id']];del self.jobs[id]
            prior=self.keys.get(client_request_id)
            if prior:
                job=self.jobs[prior]
                if job['fingerprint']!=fingerprint:raise RequestConflict('동일한 요청 ID에 다른 내용을 보낼 수 없습니다.')
                return {'job_id':prior,'status':job['status'],'reused':True}
            if sum(j['status'] in ('queued','running') for j in self.jobs.values())>=self.capacity:
                raise QueueFull('화면 구성 요청이 많습니다. 잠시 후 다시 보내주세요.')
            if len(self.jobs)>=128:raise QueueFull('완료된 작업 보관 공간이 가득 찼습니다. 잠시 후 다시 보내주세요.')
            id=str(uuid.uuid4());self.keys[client_request_id]=id
            self.jobs[id]={'job_id':id,'client_request_id':client_request_id,'fingerprint':fingerprint,
                           'status':'queued','stage':'queued','result':None,'error':None,'expires':now+self.ttl,
                           'created_at':now,'stage_started_at':now,'timings_ms':{}}
            self._persist()
        self.executor.submit(self._run,id,request)
        return {'job_id':id,'status':'queued','reused':False}

    def _run(self,id,request):
        def progress(stage):
            with self.lock:
                job=self.jobs[id];now=time.time()
                old=job['stage'];elapsed=(now-job['stage_started_at'])*1000
                job['timings_ms'][old]=job['timings_ms'].get(old,0)+round(elapsed,3)
                job.update(status='running',stage=stage,stage_started_at=now)
                self._persist()
        try:
            if time.time()-self.jobs[id]['created_at']>self.max_wait:
                raise TimeoutError('queue_wait_budget_exceeded')
            progress('context')
            result=self.composer.compose(request,progress=progress)
            with self.lock:
                self._finish(id,'completed',result=jsonable_encoder(result))
        except ComposeConflict as error:
            with self.lock:self._finish(id,'failed',error={'status':409,'message':str(error)})
        except TimeoutError:
            with self.lock:self._finish(id,'failed',error={'status':503,'message':'대기시간 한도를 넘었습니다. 잠시 후 다시 요청해주세요.'})
        except Exception:
            # Do not expose model output, stack traces, or provider data through polling.
            with self.lock:self._finish(id,'failed',error={'status':503,'message':'화면을 구성하지 못했습니다. 기존 화면을 유지하고 다시 시도해주세요.'})

    def _finish(self,id,status,**values):
        job=self.jobs[id];now=time.time();stage=job['stage']
        job['timings_ms'][stage]=job['timings_ms'].get(stage,0)+round((now-job['stage_started_at'])*1000,3)
        job['timings_ms']['total']=round((now-job['created_at'])*1000,3)
        job.update(status=status,stage=status,expires=now+self.ttl,**values)
        self._persist()

    def get(self,id):
        with self.lock:
            job=self.jobs.get(id)
            if not job or (job['expires']<time.time() and job['status'] in ('completed','failed')):return None
            return {key:job[key] for key in ('job_id','status','stage','result','error','timings_ms')}

    def close(self):self.executor.shutdown(wait=True,cancel_futures=True)
