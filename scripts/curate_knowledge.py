#!/usr/bin/env python3
"""Explicit local curation commands; worker creates pending candidates only."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rag_backend.curation_workflow import CurationWorkflow
from rag_backend.knowledge_lab import KnowledgeStore,PROMPT_VERSION


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=ROOT/'var/knowledge.sqlite3')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('status')
    sub.add_parser('audit')
    for command in ('enqueue','work'):
        item=sub.add_parser(command)
        item.add_argument('--role',choices=('generator','canvas_generator'),default='canvas_generator')
        if command=='enqueue':item.add_argument('--kind',choices=('abstract','financial_summary'))
        else:
            item.add_argument('--limit',type=int,default=10)
            item.add_argument('--deadline-seconds',type=int,default=600)
    inspect=sub.add_parser('inspect');inspect.add_argument('job_id')
    review=sub.add_parser('review');review.add_argument('job_id')
    review.add_argument('decision',choices=('approved','rejected'))
    review.add_argument('--reviewer',required=True);review.add_argument('--reason',required=True)
    review.add_argument('--revision',type=int,required=True)
    publish=sub.add_parser('publish');publish.add_argument('job_ids',nargs='+')
    activate=sub.add_parser('activate');activate.add_argument('release_id')
    for item in (publish,activate):
        item.add_argument('--operator',required=True);item.add_argument('--revision',type=int,required=True)
    args=parser.parse_args();store=KnowledgeStore(args.db);workflow=CurationWorkflow(store)
    if args.command=='status':result=workflow.status()
    elif args.command=='audit':result=workflow.audit()
    elif args.command=='inspect':
        with store.connect() as db:
            row=db.execute('SELECT document_id,source_hash,state,result,review,review_revision,error FROM curation_jobs WHERE id=?',(args.job_id,)).fetchone()
        if row is None:parser.error('unknown job')
        result=dict(zip(('source_id','source_hash','state','candidate','review','review_revision','error'),row))
        if result['candidate']:result['candidate']=json.loads(result['candidate'])
    elif args.command in ('enqueue','work'):
        from rag_backend.research_models import LazyMLXGenerator
        generator=LazyMLXGenerator(args.role)
        if args.command=='enqueue':result={'added':workflow.enqueue(generator.identity,PROMPT_VERSION,args.kind),'model_loads':0}
        else:
            if not 1<=args.limit<=100 or not 1<=args.deadline_seconds<=3600:parser.error('limit 1..100; deadline 1..3600')
            start=time.perf_counter();rows=[]
            for _ in range(args.limit):
                if time.perf_counter()-start>=args.deadline_seconds:break
                row=workflow.work_one(generator,PROMPT_VERSION);rows.append(row)
                if row['state']=='idle':break
                print(json.dumps(row,ensure_ascii=False),flush=True)
            result={'rows':rows,'model_loads':generator.loads,'seconds':time.perf_counter()-start,
                    'deadline_scope':'Checked between jobs; does not interrupt an in-flight local generation.',
                    'automatic_approval':False,'automatic_publication':False}
    elif args.command=='review':
        result={'revision':workflow.decide(args.job_id,args.decision,args.reviewer,args.revision,args.reason)}
    elif args.command=='publish':result=workflow.publish(args.job_ids,args.operator,args.revision)
    else:result=workflow.activate(args.release_id,args.operator,args.revision)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
