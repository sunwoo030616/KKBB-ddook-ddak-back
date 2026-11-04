"""Profile the actual endpoint in one model process; stop the server first."""
import argparse
import cProfile
import hashlib
import inspect
import json
import os
from pathlib import Path
import pstats
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='reports/literature-bottleneck.json')
    parser.add_argument('--repeats',type=int,default=2);args=parser.parse_args()
    os.environ.update(RAG_ENABLE_CANVAS='1',RAG_EXACT_CACHE='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        LITERATURE_RERANKER='tiny',LITERATURE_DENSE_POOL='10')
    from rag_backend.app import create_app
    start=time.perf_counter();app=create_app(enable_dense=False)
    report={'scope':'Fresh actual application factory and endpoint in one process; exact result cache disabled.',
        'setup_seconds':time.perf_counter()-start,'rows':[],
        'environment':{k:os.getenv(k) for k in ('RAG_SYSTEM_PREFIX_CACHE','RAG_MLX_CACHE_MB','RAG_MPS_CACHE_POLICY','RERANKER_DEVICE')},
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'rag_backend').glob('*.py')}}
    route=next(route for route in app.routes if getattr(route,'path',None)=='/knowledge/research')
    request_type=inspect.signature(route.endpoint).parameters['req'].annotation
    case=next(c for c in json.loads((ROOT/'data/model_routing_holdout.json').read_text()) if c['id']=='h4')
    for i in range(args.repeats):
        profile=cProfile.Profile();before=resource.getrusage(resource.RUSAGE_SELF);start=time.perf_counter()
        profile.enable()
        try:result=route.endpoint(request_type(question=case['question'],mode='anchored'))
        finally:profile.disable()
        elapsed=time.perf_counter()-start;after=resource.getrusage(resource.RUSAGE_SELF)
        stats=pstats.Stats(profile)
        frames=[{'file':Path(file).name,'line':line,'function':name,'calls':value[1],
                 'self_seconds':value[2],'cumulative_seconds':value[3]}
                for (file,line,name),value in sorted(stats.stats.items(),key=lambda item:-item[1][3])[:30]]
        row={'run':i+1,'seconds':elapsed,'status':result['status'],'trace':result['trace'],
             'source_ids':sorted({e['source_id'] for e in result['edges']}),
             'minor_faults':after.ru_minflt-before.ru_minflt,'major_faults':after.ru_majflt-before.ru_majflt,
             'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'profile':frames}
        report['rows'].append(row);(ROOT/args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(row,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
