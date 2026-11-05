"""Explicit offline ingestion from pinned official PDFs. Never downloads in an API request."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rag_backend.fulltext import enrich_document
from rag_backend.knowledge_lab import KnowledgeStore


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--db',default='var/knowledge.sqlite3')
    parser.add_argument('--pdf-dir',default='var/fulltext');parser.add_argument('--output',default='reports/fulltext-ingestion.json')
    args=parser.parse_args();store=KnowledgeStore(ROOT/args.db)
    manifest=json.loads((ROOT/'data/literature_fulltext_manifest.json').read_text())
    documents={d['id']:d for d in store.documents('abstract')};records=[];rows=[]
    for item in manifest['sources']:
        raw=(ROOT/args.pdf_dir/item['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['pdf_sha256']:raise ValueError('fulltext_pdf_hash_mismatch')
        record=enrich_document(documents[item['source_id']],raw,item['url']);records.append(record)
        rows.append({'source_id':item['source_id'],'pdf_sha256':item['pdf_sha256'],
            'fulltext':record['fulltext'],'text_chars':len(record['text'])})
    outcome=store.ingest(records)
    (ROOT/args.output).write_text(json.dumps({'scope':manifest['scope'],'rows':rows,'ingestion':outcome},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(outcome))

if __name__=='__main__':main()
