from concurrent.futures import ThreadPoolExecutor
from threading import Event
import json

import pytest
from pydantic import BaseModel

from rag_backend.inference_cache import MemoizedGenerator


class Model:
    identity={'revision':'fixed'}
    def __init__(self):self.calls=0
    def complete(self,system,user,**kwargs):
        self.calls+=1;return {'text':json.dumps({'value':user}),'latency_ms':10}


def test_key_isolates_context_schema_and_token_budget():
    model=Model();cache=MemoizedGenerator(model)
    class A(BaseModel):value:str
    class B(BaseModel):number:int
    first=cache.complete('rules','session one',output_type=A)
    assert cache.complete('rules','session one',output_type=A)['model_calls']==0
    for system,user,schema,tokens in [('rules','session two',A,500),('other','session one',A,500),
                                      ('rules','session one',B,500),('rules','session one',A,100)]:
        assert cache.complete(system,user,output_type=schema,max_tokens=tokens)['cache_hit'] is False
    assert model.calls==5 and first['cache_hit'] is False


def test_capacity_and_ttl_prevent_unbounded_or_stale_reuse():
    model=Model();cache=MemoizedGenerator(model,capacity=1,ttl=0)
    cache.complete('s','a');cache.complete('s','a')
    assert model.calls==2
    cache=MemoizedGenerator(model,capacity=1)
    cache.complete('s','a');cache.complete('s','b');cache.complete('s','a')
    assert cache.snapshot()['entries']==1 and model.calls==5


def test_concurrent_duplicates_execute_once():
    started=Event();release=Event()
    class Blocking(Model):
        def complete(self,*args,**kwargs):started.set();assert release.wait(3);return super().complete(*args,**kwargs)
    model=Blocking();cache=MemoizedGenerator(model)
    with ThreadPoolExecutor(max_workers=3) as pool:
        owner=pool.submit(cache.complete,'s','same');assert started.wait(1)
        waiting=[pool.submit(cache.complete,'s','same') for _ in range(2)]
        release.set();results=[owner.result()]+[f.result() for f in waiting]
    assert model.calls==1 and sum(r['model_calls'] for r in results)==1


def test_failure_is_not_cached_or_left_inflight():
    class Failing(Model):
        def complete(self,*args,**kwargs):raise ValueError('failure')
    cache=MemoizedGenerator(Failing())
    for _ in range(2):
        with pytest.raises(ValueError):cache.complete('s','u')
    assert not cache.inflight and cache.snapshot()['entries']==0


def test_structurally_invalid_output_is_never_cached():
    class Schema(BaseModel):number:int
    model=Model();cache=MemoizedGenerator(model)
    cache.complete('s','u',output_type=Schema);cache.complete('s','u',output_type=Schema)
    assert model.calls==2 and cache.snapshot()['entries']==0
