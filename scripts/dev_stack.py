#!/usr/bin/env python3
"""Start the local React -> Spring -> neural composer stack, checking real readiness."""
from pathlib import Path
import os
import signal
import subprocess
import time
import urllib.request
import json

ROOT=Path(__file__).resolve().parents[1]
FRONT=ROOT.parent/'kkbb-ddook-ddak-front'
LOGS=ROOT/'var'/'dev-stack';LOGS.mkdir(parents=True,exist_ok=True)
processes=[];handles=[]


def ready(url,kind):
    try:
        with urllib.request.urlopen(url,timeout=2) as response:
            body=response.read().decode()
            if kind=='ai':return json.loads(body).get('canvas_configured') is True
            if kind=='spring':return json.loads(body).get('service')=='canvas-v2'
            return 'kkbb-ddook-ddak-front' in body
    except Exception:return False


def start(name,cmd,cwd,url,env=None):
    if ready(url,name):
        print(f'{name}: already responding at {url}',flush=True);return
    log=(LOGS/(name+'.log')).open('w');handles.append(log)
    process=subprocess.Popen(cmd,cwd=cwd,env={**os.environ,**(env or {})},stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    processes.append(process)
    for _ in range(360):
        if process.poll() is not None:raise RuntimeError(f'{name} exited; inspect {log.name}')
        if ready(url,name):print(f'{name}: ready',flush=True);return
        time.sleep(.5)
    raise RuntimeError(f'{name} did not become ready; inspect {log.name}')


try:
    start('ai',[str(ROOT/'.venv/bin/python'),'-m','uvicorn','rag_backend.app:create_app','--factory','--host','127.0.0.1','--port','8767','--no-access-log'],ROOT,'http://127.0.0.1:8767/health',
          {'RAG_ENABLE_CANVAS':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'})
    # A POST-free public catalog gives the Spring process a simple, non-generating readiness check.
    start('spring',[str(ROOT/'mvnw'),'-q','-o',f'-Dmaven.repo.local={ROOT/"var/maven-repository"}','spring-boot:run','-Dspring-boot.run.arguments=--server.port=8088'],ROOT,'http://127.0.0.1:8088/api/canvas/v2/health',
          {'MAVEN_USER_HOME':str(ROOT/'var/maven-home')})
    start('front',['npm','run','dev'],FRONT,'http://localhost:5173')
    print('Open http://localhost:5173 — Ctrl+C stops only processes launched here.',flush=True)
    while True:
        if any(p.poll() is not None for p in processes):raise RuntimeError('A stack process exited; inspect var/dev-stack logs')
        time.sleep(1)
except KeyboardInterrupt:pass
finally:
    for process in reversed(processes):
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGINT)
            try:process.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGTERM)
    for handle in handles:handle.close()
