#!/usr/bin/env python3
"""Separate-process local model comparison. No simultaneous generator residency."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'reports/model-routing.json'
CONFIGS={'4b_compact':('canvas_generator','compact'),
         '1.7b_compact':('generator','compact'),'4b_fast':('canvas_generator','fast')}
FILES={'dev':'evidence_graph_cases.json','holdout':'model_routing_holdout.json'}


def save(report):OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


def summary(report,split):
    return {key:{'n':len(rows),'exact':sum(r['exact'] for r in rows),
                 'missing_aspect_failures':sum(not r['missing_aspect_ok'] for r in rows),
                 'invalid':sum(r['status'].startswith('invalid') or r['status']=='error' for r in rows),
                 'median_seconds':statistics.median(r['seconds'] for r in rows),
                 'span_pairs':sum(r['span_pairs'] for r in rows)}
            for key in CONFIGS if (rows:=[r for r in report['rows'] if r['split']==split and r['config']==key])}


def child(key,split):
    from rag_backend.research_models import MLXGenerator,CrossEncoderReranker
    from rag_backend.evidence_graph import EvidenceGraph
    from rag_backend.knowledge_lab import KnowledgeStore,source_spans
    from rag_backend.retrieval_acceleration import CachedReranker,SpanPrefilter
    started=time.perf_counter();role,mode=CONFIGS[key]
    store=KnowledgeStore(ROOT/'var/model-routing-baseline.sqlite3')
    if len(store.documents('abstract'))!=6:raise ValueError('baseline_six_source_snapshot_required')
    generator=MLXGenerator(role)
    ranker=CachedReranker(CrossEncoderReranker());prefilter=None
    if mode=='fast':
        from rag_backend.dense import LocalEncoder
        prefilter=SpanPrefilter(LocalEncoder(),ROOT/'var/span-vectors.sqlite3')
        prefilter.vectors([s['text'] for d in store.documents('abstract') for s in source_spans(d['text']).values()])
    report=json.loads(OUT.read_text())
    report.setdefault('execution',{})[key+':'+split]={'setup_seconds':time.perf_counter()-started,
        'generator':generator.identity,'reranker':ranker.identity,
        'embedding':prefilter.encoder.name if prefilter else None}
    save(report)
    for case in json.loads((ROOT/'data'/FILES[split]).read_bytes()):
        begin=time.perf_counter()
        try:
            result=EvidenceGraph(store,generator,ranker,prefilter=prefilter).build(case['question'],mode)
            actual=sorted({e['source_id'] for e in result['edges']})
            valid=result['status'] not in ('invalid_plan','invalid_selection','stale_snapshot')
            row={'status':result['status'],'actual':actual,'exact':valid and actual==sorted(case['expected_sources']),
                 'tasks':result['tasks'],'missing':result.get('missing_task_ids',[]),'trace':result['trace'],
                 'missing_aspect_ok':bool(result.get('missing_task_ids')) if case['id'] in ('g7','g8','h7','h8') else True,
                 'span_pairs':sum(t.get('scored_pairs',0) for t in result['trace'])}
        except Exception as error:row={'status':'error','error':type(error).__name__,'exact':False,'span_pairs':0,'missing_aspect_ok':False}
        row.update(id=case['id'],split=split,config=key,seconds=time.perf_counter()-begin,expected=case['expected_sources'])
        report['rows'].append(row);save(report)
        print(split,case['id'],key,row['status'],row['exact'],round(row['seconds'],2),flush=True)
    report['execution'][key+':'+split]['reranker_stats']=ranker.stats;save(report)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',choices=CONFIGS);parser.add_argument('--split',choices=FILES)
    args=parser.parse_args()
    if args.config:
        if not args.split:parser.error('--split required with --config')
        child(args.config,args.split);return
    from rag_backend.knowledge_lab import KnowledgeStore
    baseline=KnowledgeStore(ROOT/'var/model-routing-baseline.sqlite3')
    records=json.loads((ROOT/'var/literature/abstracts.json').read_text())['records']
    baseline.ingest(records)
    if {d['id'] for d in baseline.documents('abstract')}!={d['id'] for d in records} or len(records)!=6:
        raise ValueError('baseline_corpus_mismatch')
    report={'scope':'Internal developer-authored six-source comparison; heldout wording shares corpus. One generator per child process. No LLM response cache.',
            'datasets':{s:hashlib.sha256((ROOT/'data'/f).read_bytes()).hexdigest() for s,f in FILES.items()},
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                [ROOT/'rag_backend/evidence_graph.py',ROOT/'rag_backend/retrieval_acceleration.py',ROOT/'rag_backend/knowledge_lab.py',Path(__file__)]},
            'rows':[]}
    save(report)
    for split in FILES:
        for key in CONFIGS:
            subprocess.run([sys.executable,str(Path(__file__)), '--config',key,'--split',split],cwd=ROOT,check=True)
        report=json.loads(OUT.read_text());report[split]=summary(report,split)
        if split=='dev':
            report['selected_from_dev']=min(CONFIGS,key=lambda k:(-report['dev'][k]['exact'],report['dev'][k]['invalid'],report['dev'][k]['median_seconds']))
            report['selection_frozen_before_holdout']=True
        save(report)
    print(json.dumps({k:report[k] for k in ('dev','holdout','selected_from_dev')}),flush=True)


if __name__=='__main__':main()
