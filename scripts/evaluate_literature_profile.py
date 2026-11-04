#!/usr/bin/env python3
"""Evaluate a lightweight English literature path, preserving every failure."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=('compact','contextual','anchored'),default='contextual')
    parser.add_argument('--dense-candidates',action='store_true');parser.add_argument('--per-clause',action='store_true')
    parser.add_argument('--binding-format',choices=('ids','ordinal'),default='ids');args=parser.parse_args()
    import mlx.core as mx
    from rag_backend.inference_resources import configure_mlx_cache,mlx_memory
    from rag_backend.research_models import MLXGenerator
    from rag_backend.literature_reranker import EnglishLiteratureReranker
    from rag_backend.retrieval_acceleration import CachedReranker
    from rag_backend.knowledge_lab import KnowledgeStore
    from rag_backend.evidence_graph import EvidenceGraph
    policy=configure_mlx_cache(mx);setup=time.perf_counter()
    generator=MLXGenerator('canvas_generator');ranker=CachedReranker(EnglishLiteratureReranker())
    store=KnowledgeStore(ROOT/'var/knowledge.sqlite3')
    document_prefilter=None
    if args.dense_candidates:
        from rag_backend.literature_encoder import EnglishLiteratureEncoder,DocumentPrefilter
        document_prefilter=DocumentPrefilter(EnglishLiteratureEncoder(),ROOT/'var/english-document-vectors.sqlite3',limit=10)
        document_prefilter.base.vectors([d['title']+'\n'+d['text'] for d in store.documents('abstract')])
    report={'scope':'Combined profile: Qwen3-4B + CPU English MiniLM reranker + named measurement source-presence guard + opt-in MLX allocator cap. No response cache. Not an isolated causal ablation against older BGE runs.',
            'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'dirty_source_files':subprocess.check_output(['git','diff','--name-only','--','rag_backend','scripts','data'],cwd=ROOT,text=True).splitlines(),
            'generator':generator.identity,'reranker':ranker.identity,'resource_policy':policy,'mode':args.mode,
            'system_prefix_cache_enabled':generator.system_prefix_cache is not None,
            'per_clause_prototype':args.per_clause,
            'binding_format':args.binding_format,
            'document_prefilter':document_prefilter.encoder.identity if document_prefilter else None,
            'setup_seconds':time.perf_counter()-setup,'corpus':{d['id']:d['content_hash'] for d in store.documents('abstract')},
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'rag_backend').glob('*.py')},
            'rows':[],'datasets':{}}
    out=ROOT/'reports/literature-lightweight-profile.json';rawdir=ROOT/'var/literature-profile-raw';rawdir.mkdir(exist_ok=True)
    def save():out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    splits=[('dev','evidence_graph_cases.json'),('regression','model_routing_holdout.json'),('fresh','literature_fresh_validation.json')]
    for split,file in splits:
        raw=(ROOT/'data'/file).read_bytes();report['datasets'][split]=hashlib.sha256(raw).hexdigest()
        for case in json.loads(raw):
            begin=time.perf_counter()
            try:
                graph=EvidenceGraph(store,generator,ranker,document_prefilter=document_prefilter,per_clause=args.per_clause,binding_format=args.binding_format).build(case['question'],args.mode)
                (rawdir/(case['id']+'.json')).write_text(json.dumps(graph,ensure_ascii=False,indent=2)+'\n')
                actual=sorted({e['source_id'] for e in graph['edges']});valid=graph['status'] not in ('invalid_plan','invalid_selection','stale_snapshot')
                row={'status':graph['status'],'actual':actual,'exact':valid and actual==sorted(case['expected_sources']),
                    'missing':graph.get('missing_task_ids',[]),'missing_aspect_ok':bool(graph.get('missing_task_ids')) if case.get('expects_missing',case['id'] in ('g7','g8','h7','h8')) else True,
                    'tasks':graph['tasks'],'trace':graph['trace'],'source_versions_current':graph.get('source_versions_current'),
                    'edges':[{k:e[k] for k in ('task_id','source_id','source_hash','start','end')} for e in graph['edges']]}
            except Exception as error:row={'status':'error','error':type(error).__name__,'exact':False,'missing_aspect_ok':False}
            row.update(id=case['id'],split=split,expected=case['expected_sources'],seconds=time.perf_counter()-begin,memory=mlx_memory(mx))
            report['rows'].append(row);save();print(split,case['id'],row['status'],row['exact'],round(row['seconds'],2),flush=True)
        rows=[r for r in report['rows'] if r['split']==split]
        report[split]={'n':len(rows),'exact':sum(r['exact'] for r in rows),
            'missing_aspect_failures':sum(not r['missing_aspect_ok'] for r in rows),
            'median_seconds':statistics.median(r['seconds'] for r in rows)}
        save()
    report['score_cache_stats']=ranker.stats
    report['system_prefix_cache_stats']=generator.system_prefix_cache.snapshot() if generator.system_prefix_cache else None
    save();print(json.dumps({k:report[k] for k,file in splits}),flush=True)


if __name__=='__main__':main()
