"""Aggregate local catalog metadata with bounded outputs; no model calls."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    from rag_backend.knowledge_lab import KnowledgeStore
    from rag_backend.knowledge_catalog import KnowledgeCatalog
    parser=argparse.ArgumentParser();parser.add_argument('--db',type=Path,default=ROOT/'var/knowledge.sqlite3')
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    report=KnowledgeCatalog(KnowledgeStore(args.db)).statistics();text=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(text)
    print(text,end='')


if __name__=='__main__':main()
