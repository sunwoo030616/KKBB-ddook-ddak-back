"""Reproducible free-model evaluation; preregistered set is never a tuning set."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',choices=['pilot','regression','preregistered'],required=True)
    p.add_argument('--output',required=True);args=p.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OPENAI_API_KEY='')
    from rag_backend.research_models import MLXGenerator
    from rag_backend.knowledge_lab import KnowledgeStore
    from rag_backend.adaptive_literature import AdaptiveLiteratureAgent
    from rag_backend.multilingual_literature import MultilingualLiteratureReranker
    from rag_backend.literature_reranker import EnglishLiteratureReranker
    from rag_backend.retrieval_acceleration import CachedReranker
    files=['literature_preregistered_evaluation.json'] if args.suite=='preregistered' else [
        'evidence_graph_cases.json','model_routing_holdout.json','literature_fresh_validation.json','literature_guard_cases.json']
    datasets={name:(ROOT/'data'/name).read_bytes() for name in files}
    if args.suite=='preregistered':
        protocol=json.loads((ROOT/'data/literature_evaluation_protocol.json').read_text())
        if hashlib.sha256(next(iter(datasets.values()))).hexdigest()!=protocol['dataset_sha256']:
            raise ValueError('preregistered_dataset_changed')
    setup=time.perf_counter();generator=MLXGenerator('canvas_generator');store=KnowledgeStore(ROOT/'var/knowledge.sqlite3')
    a=AdaptiveLiteratureAgent(store,CachedReranker(MultilingualLiteratureReranker()),None,generator,
        english_reranker=CachedReranker(EnglishLiteratureReranker()))
    before={d['id']:d['content_hash'] for d in store.documents()}
    report={'suite':args.suite,'scope':'Developer-authored preregistered holdout or observed regression. NOT external independent human evaluation. First-three-page corpus extension is targeted; old/new corpora differ.',
        'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'backend_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in (ROOT/'rag_backend').glob('*.py')},
        'datasets':{name:hashlib.sha256(raw).hexdigest() for name,raw in datasets.items()},
        'sources':before,'generator':generator.identity,'paid_api_enabled':False,'setup_seconds':time.perf_counter()-setup,'rows':[]}
    for file,raw in datasets.items():
        for case in json.loads(raw):
            if args.suite=='pilot' and case['id'] not in ('g3','v4'):continue
            begin=time.perf_counter();graph=a.build(case['question']);elapsed=time.perf_counter()-begin
            current={d['id']:d for d in store.documents('abstract')}
            actual=sorted({e['source_id'] for e in graph['edges']});expected=sorted(case['expected_sources'])
            quotes_valid=all(type(e['start']) is int and type(e['end']) is int and 0<=e['start']<e['end']<=len(current[e['source_id']]['text']) and
                current[e['source_id']]['text'][e['start']:e['end']]==e['text'] and current[e['source_id']]['content_hash']==e['source_hash'] for e in graph['edges'])
            row={'id':case['id'],'question':case['question'],'dataset':file,'expected':expected,'actual':actual,
                'exact':actual==expected and graph['source_versions_current'] and (not case.get('expected_status') or graph['status']==case['expected_status']),
                'unexpected_sources':sorted(set(actual)-set(expected)),'missing_sources':sorted(set(expected)-set(actual)),
                'seconds':elapsed,'status':graph['status'],'quotes_valid':quotes_valid,'citation_count':len(graph['edges']),
                'missing_aspect_ok':bool(graph['missing_task_ids']) if case.get('expects_missing',case['id'] in ('g7','g8','h7','h8')) else True,
                'graph':graph}
            report['rows'].append(row)
            (ROOT/args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print(case['id'],row['exact'],round(elapsed,3),actual,'citations',row['citation_count'],flush=True)
    rows=report['rows'];report['summary']={'n':len(rows),'exact':sum(r['exact'] for r in rows),
        'unexpected_sources':sum(len(r['unexpected_sources']) for r in rows),
        'all_quotes_valid':all(r['quotes_valid'] for r in rows),'missing_aspect_failures':sum(not r['missing_aspect_ok'] for r in rows),
        'median_seconds':statistics.median(r['seconds'] for r in rows),'max_seconds':max(r['seconds'] for r in rows),
        'source_data_unchanged':before=={d['id']:d['content_hash'] for d in store.documents()}}
    report['complete']=True
    (ROOT/args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
