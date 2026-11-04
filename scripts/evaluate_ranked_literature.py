"""Actual free-model evaluation; keep old reports and every failed case."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--split',choices=('dev','regression','fresh','all'),default='all')
    parser.add_argument('--engine',choices=('ranked','adaptive'),default='ranked')
    parser.add_argument('--output',default='reports/ranked-literature.json');args=parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    from rag_backend.research_models import MLXGenerator
    from rag_backend.literature_encoder import EnglishLiteratureEncoder,DocumentPrefilter
    from rag_backend.literature_reranker import EnglishLiteratureReranker
    from rag_backend.retrieval_acceleration import CachedReranker
    from rag_backend.knowledge_lab import KnowledgeStore
    from rag_backend.ranked_literature import RankedLiteratureSearch
    start=time.perf_counter();generator=MLXGenerator('canvas_generator')
    store=KnowledgeStore(ROOT/'var/knowledge.sqlite3')
    if args.engine=='adaptive':
        from rag_backend.multilingual_literature import MultilingualLiteratureReranker
        from rag_backend.dense import LocalEncoder
        from rag_backend.retrieval_acceleration import SpanPrefilter
        from rag_backend.adaptive_literature import AdaptiveLiteratureAgent
        ranker=CachedReranker(MultilingualLiteratureReranker())
        prefilter=SpanPrefilter(LocalEncoder(),ROOT/'var/adaptive-literature-vectors.sqlite3')
        search=AdaptiveLiteratureAgent(store,ranker,prefilter,generator,english_reranker=CachedReranker(EnglishLiteratureReranker()))
    else:
        ranker=CachedReranker(EnglishLiteratureReranker())
        prefilter=DocumentPrefilter(EnglishLiteratureEncoder(),ROOT/'var/ranked-literature-vectors.sqlite3',limit=10)
        search=RankedLiteratureSearch(store,generator,ranker,prefilter)
    report={'scope':'Internal developer-authored diagnostic, not blind external accuracy. One process, no exact result cache.',
        'setup_seconds':time.perf_counter()-start,'engine':args.engine,'generator':generator.identity,'reranker':ranker.identity,
        'sources':{d['id']:d['content_hash'] for d in store.documents('abstract')},
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'rag_backend').glob('*.py')},
        'datasets':{},'rows':[]}
    for split,file in [('dev','evidence_graph_cases.json'),('regression','model_routing_holdout.json'),('fresh','literature_fresh_validation.json')]:
        if args.split not in ('all',split):continue
        data=(ROOT/'data'/file).read_bytes();report['datasets'][split]=hashlib.sha256(data).hexdigest()
        for case in json.loads(data):
            begin=time.perf_counter();result=search.build(case['question']);actual=sorted({e['source_id'] for e in result['edges']})
            valid=result['status'] not in ('invalid_plan','model_unavailable','stale_snapshot')
            row={'id':case['id'],'split':split,'expected':sorted(case['expected_sources']),'actual':actual,
                'exact':valid and actual==sorted(case['expected_sources']),
                'missing_aspect_ok':bool(result.get('missing_task_ids')) if case.get('expects_missing',case['id'] in ('g7','g8','h7','h8')) else True,
                'seconds':time.perf_counter()-begin,'status':result['status'],'tasks':result['tasks'],
                'trace':result['trace'],'source_versions_current':result.get('source_versions_current'),
                'edges':[{k:e[k] for k in ('task_id','source_id','source_hash','start','end')} for e in result['edges']]}
            report['rows'].append(row);(ROOT/args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print(split,case['id'],row['exact'],round(row['seconds'],2),actual,flush=True)
    report['summary']={split:{'n':len(rows),'exact':sum(r['exact'] for r in rows),
        'missing_aspect_failures':sum(not r['missing_aspect_ok'] for r in rows),
        'median_seconds':statistics.median(r['seconds'] for r in rows),'max_seconds':max(r['seconds'] for r in rows)}
        for split in sorted({r['split'] for r in report['rows']})
        if (rows:=[r for r in report['rows'] if r['split']==split])}
    report.update(complete=True,score_cache_stats=ranker.stats)
    (ROOT/args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
