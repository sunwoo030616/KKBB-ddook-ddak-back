#!/usr/bin/env python3
"""Actual local-model cross-request isolation and parity checks; no response cache."""
import json
from pathlib import Path
import sys
import time
from typing import Literal

from pydantic import BaseModel,ConfigDict

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


class Echo(BaseModel):
    model_config=ConfigDict(extra='forbid')
    code:Literal['alpha','beta','gamma']


def main():
    from rag_backend.research_models import MLXGenerator
    generator=MLXGenerator('canvas_generator');cache=generator.system_prefix_cache
    if cache is None:raise ValueError('RAG_SYSTEM_PREFIX_CACHE=1_required')
    report={'scope':'Actual 4B constrained generation: changing user codes under the same system prefix. No response memoization. Off warms grammar before on; latency is diagnostic, not a causal speed estimate.','rows':[]}
    system='Read the JSON user data. Return its code value exactly as the code field. Never use a value from another request.'
    for mode in ('off','on'):
        generator.system_prefix_cache=cache if mode=='on' else None
        for value in ('alpha','beta','gamma','alpha'):
            started=time.perf_counter();raw=generator.complete(system,json.dumps({'code':value}),max_tokens=40,output_type=Echo)
            actual=Echo.model_validate_json(raw['text']).code
            report['rows'].append({'mode':mode,'input':value,'output':actual,'correct':actual==value,
                'seconds':time.perf_counter()-started,'prefix':raw['system_prefix_cache']})
            (ROOT/'reports/system-prefix-isolation.json').write_text(json.dumps(report,indent=2)+'\n')
            print(mode,value,actual,raw['system_prefix_cache'],flush=True)
    report['cache']=cache.snapshot();report['all_inputs_respected']=all(r['correct'] for r in report['rows'])
    report['actual_prefix_reuse']=cache.snapshot()['hits']>=3
    (ROOT/'reports/system-prefix-isolation.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['all_inputs_respected'] or not report['actual_prefix_reuse']:raise SystemExit('prefix_cache_not_verified')


if __name__=='__main__':main()
