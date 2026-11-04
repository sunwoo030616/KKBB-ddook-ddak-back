#!/usr/bin/env python3
"""One-command incremental curation. No changes -> no model load or inference.

--refresh fetches a new official arXiv snapshot before computing source differences.
All generated tags/categories stay pending review; no publication or live-corpus promotion.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rag_backend.inference_cache import MemoizedGenerator
from rag_backend.knowledge_lab import KnowledgeStore
from rag_backend.research_models import LazyMLXGenerator


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
    started=time.perf_counter()
    if args.refresh:
        from scripts.collect_abstracts import fetch
        fetch()
    abstracts=json.loads((ROOT/'var/literature/abstracts.json').read_text())['records']
    finance=json.loads((ROOT/'data/financial_guides.json').read_text())['chunks']
    records=abstracts+[{'id':'finance:'+r['id'],'title':r['title'],'text':r['text'],'source_url':r['url'],
        'kind':'financial_summary','institution':r['institution'],'verified_at':r['verified_at']} for r in finance]
    store=KnowledgeStore(ROOT/'var/knowledge.sqlite3');ingest=store.ingest(records)
    lazy=LazyMLXGenerator();result=store.prepare_notes(MemoizedGenerator(lazy))
    report={'ingest':ingest,'curation':{k:v for k,v in result.items() if k!='new_notes'},
        'model_loads':lazy.loads,'seconds':time.perf_counter()-started,'automatic_live_publication':False}
    (ROOT/'reports/incremental-refresh.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
