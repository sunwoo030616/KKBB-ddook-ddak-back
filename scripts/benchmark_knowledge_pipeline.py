"""Synthetic batch/query benchmark. Never mix synthetic rows into the real KB."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    from rag_backend.batch_ingest import ingest_jsonl
    from rag_backend.knowledge_lab import KnowledgeStore
    from rag_backend.knowledge_catalog import KnowledgeCatalog
    parser=argparse.ArgumentParser();parser.add_argument('--documents',type=int,default=5000);args=parser.parse_args()
    if not 100<=args.documents<=50000:parser.error('documents must be 100..50000')
    class MeasuredStore(KnowledgeStore):
        def __init__(self,path):self.batch_lookup_queries=0;super().__init__(path)
        def connect(self):
            db=super().connect()
            def trace(sql):
                if sql.startswith('SELECT id,hash FROM documents WHERE id IN'):self.batch_lookup_queries+=1
            db.set_trace_callback(trace);return db
    with tempfile.TemporaryDirectory(prefix='kb-benchmark-',dir=ROOT/'var') as directory:
        folder=Path(directory);source=folder/'synthetic.jsonl'
        def record(i):return {'id':f'synthetic:{i:06d}','title':f'Synthetic benchmark document {i}',
            'text':f'Controlled synthetic source evidence for ingestion. Unique term needle{i:06d}.',
            'kind':'abstract','source_url':'https://example.com/synthetic/'+str(i)}
        with source.open('w') as handle:
            for i in range(args.documents):handle.write(json.dumps(record(i),sort_keys=True)+'\n')
        store=MeasuredStore(folder/'knowledge.db');first=ingest_jsonl(source,store,batch_size=200)
        lookups_first=store.batch_lookup_queries;noop=ingest_jsonl(source,store,batch_size=200)
        catalog=KnowledgeCatalog(store);timings=[]
        for _ in range(20):
            start=time.perf_counter();page=catalog.page(after=f'synthetic:{args.documents//2:06d}',limit=25)
            timings.append(time.perf_counter()-start)
        query_plan=catalog.query_plan(after=f'synthetic:{args.documents//2:06d}')
        target=args.documents-1;start=time.perf_counter();hits=catalog.search(f'needle{target:06d}');fts_seconds=time.perf_counter()-start
        assert [h['id'] for h in hits['hits']]==[f'synthetic:{target:06d}']
        assert first['state']['seen']==args.documents and first['state']['complete']
        assert noop['batches_this_run']==0 and len(page['records'])==25
        assert any('documents_kind_id' in row for row in query_plan)
        with source.open('w') as handle:
            for i in range(args.documents):
                row=record(i)
                if i==0:row['text']+=' Revised source version.'
                handle.write(json.dumps(row,sort_keys=True)+'\n')
        changed=ingest_jsonl(source,store,batch_size=200)
        assert changed['state']['changed']==1 and changed['state']['unchanged']==args.documents-1
        with store.connect() as db:
            counts={name:db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in ('documents','versions','knowledge_fts')}
        assert counts=={'documents':args.documents,'versions':args.documents+1,'knowledge_fts':args.documents}
        report={'scope':'Synthetic local SQLite benchmark; no real research documents, models, production TPS or distributed scale claim.',
            'synthetic_documents':args.documents,'batch_size':200,'first':first,'unchanged_run':noop,'one_changed_record':changed,
            'batch_existing_version_selects_first':lookups_first,'deep_page':{'repetitions':20,'median_seconds':statistics.median(timings),
            'scope':'Repeated identical warmed keyset query, not independent production traffic.','query_plan':query_plan},
            'fts':{'target_id':hits['hits'][0]['id'],'seconds':fts_seconds},'final_counts':counts,
            'real_knowledge_database_modified':False}
    (ROOT/'reports/knowledge-pipeline-benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
