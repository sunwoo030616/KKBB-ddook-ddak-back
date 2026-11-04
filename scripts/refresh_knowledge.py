#!/usr/bin/env python3
"""Incremental, resumable local curation. No source changes -> no model loading.

--refresh explicitly fetches an official arXiv snapshot. AI creates pending cards only.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rag_backend.knowledge_lab import KnowledgeStore,PROMPT_VERSION
from rag_backend.curation_workflow import CurationWorkflow
from rag_backend.research_models import LazyMLXGenerator


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--corpus',choices=('baseline','expanded'),default='expanded')
    parser.add_argument('--legacy',action='store_true');parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--deadline-seconds',type=int,default=1800);args=parser.parse_args()
    if not 1<=args.limit<=100 or not 1<=args.deadline_seconds<=3600:parser.error('invalid work budget')
    started=time.perf_counter()
    if args.refresh:
        if args.corpus=='expanded':
            from scripts.collect_research_corpus import fetch
        else:
            from scripts.collect_abstracts import fetch
        fetch()
    path=ROOT/'var/literature'/('expanded-abstracts.json' if args.corpus=='expanded' else 'abstracts.json')
    if not path.exists():parser.error('Collect the selected official corpus explicitly before refreshing.')
    abstracts=json.loads(path.read_text())['records']
    finance=json.loads((ROOT/'data/financial_guides.json').read_text())['chunks']
    records=abstracts+[{'id':'finance:'+r['id'],'title':r['title'],'text':r['text'],'source_url':r['url'],
        'kind':'financial_summary','institution':r['institution'],'verified_at':r['verified_at']} for r in finance]
    store=KnowledgeStore(ROOT/'var/knowledge.sqlite3');ingest=store.ingest(records);lazy=LazyMLXGenerator()
    if args.legacy:
        result=store.prepare_notes(lazy,limit=args.limit)
        curation={k:v for k,v in result.items() if k!='new_notes'}
    else:
        workflow=CurationWorkflow(store);added=workflow.enqueue(lazy.identity,PROMPT_VERSION)
        migration=workflow.import_legacy(lazy.identity,PROMPT_VERSION);rows=[]
        for _ in range(args.limit):
            if time.perf_counter()-started>=args.deadline_seconds:break
            row=workflow.work_one(lazy,PROMPT_VERSION)
            if row['state']=='idle':break
            rows.append(row);print(json.dumps(row),flush=True)
        curation={'enqueued':added,'legacy_migration':migration,'processed':len(rows),
            'model_calls':sum(r['model_calls'] for r in rows),'rows':rows,
            'status':workflow.status(),'audit':workflow.audit(),
            'model_call_scope':'Completed generation returns; interrupted in-flight calls may have unknown execution count.'}
    report={'ingest':ingest,'corpus':args.corpus,'documents':len(store.documents()),'curation':curation,
        'model_loads':lazy.loads,'seconds':time.perf_counter()-started,
        'automatic_approval':False,'automatic_live_publication':False,
        'deadline_scope':'Checked between jobs; does not interrupt an in-flight generation.'}
    (ROOT/'reports/incremental-refresh.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
