"""Bounded exact-input inference memoization, NOT a KV/prefix cache.

All model inputs/schema/identity are hashed. Entries live in process memory only.
One in-flight inference per key; tools and screen commits still execute normally.
"""
from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
from threading import Event, Lock
import time


class MemoizedGenerator:
    def __init__(self, generator, capacity=32, ttl=300, max_bytes=2_000_000):
        if capacity<0 or ttl<0 or max_bytes<=0:raise ValueError('invalid_cache_budget')
        self.generator=generator;self.capacity=capacity;self.ttl=ttl;self.max_bytes=max_bytes
        self.identity=getattr(generator,'identity',{})
        self.entries=OrderedDict();self.inflight={};self.lock=Lock();self.bytes=0
        self.stats={'hits':0,'misses':0,'waits':0,'executions':0}

    def complete(self, system, user, max_tokens=500, output_type=None):
        started=time.perf_counter()
        schema=output_type.model_json_schema() if output_type is not None else None
        key=hashlib.sha256(json.dumps({'system':system,'user':user,'max_tokens':max_tokens,
            'schema':schema,'identity':self.identity},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        while True:
            with self.lock:
                now=time.monotonic()
                for old in list(self.entries):
                    if self.entries[old][0]<=now:
                        _,_,size=self.entries.pop(old);self.bytes-=size
                if key in self.entries:
                    _,value,_=self.entries[key];self.entries.move_to_end(key);self.stats['hits']+=1
                    result=deepcopy(value)
                    return dict(result,cache_hit=True,model_calls=0,
                        original_generation_ms=result.get('latency_ms'),latency_ms=round((time.perf_counter()-started)*1000,3))
                if key not in self.inflight:
                    event=Event();self.inflight[key]=event;self.stats['misses']+=1;break
                event=self.inflight[key];self.stats['waits']+=1
            # A bounded wait does not cancel the owner or create duplicate work.
            if not event.wait(180):raise TimeoutError('inference_cache_wait_timeout')
        try:
            with self.lock:self.stats['executions']+=1
            value=self.generator.complete(system,user,max_tokens=max_tokens,output_type=output_type)
            size=len(json.dumps(value,ensure_ascii=False).encode())
            cacheable=True
            if output_type is not None:
                try:output_type.model_validate_json(value['text'])
                except (ValueError,TypeError,KeyError):cacheable=False
            with self.lock:
                if cacheable and size<=self.max_bytes:
                    while self.entries and (len(self.entries)>=self.capacity or self.bytes+size>self.max_bytes):
                        _,(_,_,old_size)=self.entries.popitem(last=False);self.bytes-=old_size
                    if self.capacity>0:
                        self.entries[key]=(time.monotonic()+self.ttl,deepcopy(value),size);self.bytes+=size
            return dict(value,cache_hit=False,model_calls=1)
        finally:
            with self.lock:
                self.inflight.pop(key).set()

    def snapshot(self):
        with self.lock:return {**self.stats,'entries':len(self.entries),'bytes':self.bytes,
                               'capacity':self.capacity,'ttl_seconds':self.ttl}
