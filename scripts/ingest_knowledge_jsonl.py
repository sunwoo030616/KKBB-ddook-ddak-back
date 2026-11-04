"""Explicit local batch import; no model loading or arbitrary network fetching."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    from rag_backend.batch_ingest import ingest_jsonl
    from rag_backend.knowledge_lab import KnowledgeStore
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path)
    parser.add_argument('--db',type=Path,default=ROOT/'var/knowledge.sqlite3')
    parser.add_argument('--batch-size',type=int,default=200);parser.add_argument('--max-batches',type=int,default=1000)
    args=parser.parse_args();print(json.dumps(ingest_jsonl(args.source,KnowledgeStore(args.db),args.batch_size,args.max_batches),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
