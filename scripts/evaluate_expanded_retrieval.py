#!/usr/bin/env python3
"""Paired internal retrieval study over 30 abstracts. No hosted inference."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'reports/expanded-retrieval.json'


def save(report):OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


def rank(records,query,reranker,prefilter=None,pool=20):
    import re
    if prefilter:
        candidates=[d for d,id,s in prefilter.select(query,
            [(d,'doc',{'text':d['title']+'\n'+d['text']}) for d in records],per_document=1)][:pool]
    else:
        words=set(re.findall(r'\w+',query.lower()))
        candidates=sorted(records,key=lambda d:(-len(words&set(re.findall(r'\w+',d['title'].lower()+' '+d['text'].lower()))),d['id']))[:pool]
    scores=reranker.score_pairs([(query,d['title']+'\n'+d['text']) for d in candidates])
    ordered=sorted(zip(candidates,scores),key=lambda ds:(-ds[1],ds[0]['id']))
    return [d['id'] for d,s in ordered[:3]],[d['id'] for d in candidates]


def run(kind):
    from rag_backend.knowledge_lab import KnowledgeStore
    from rag_backend.retrieval_acceleration import CachedReranker,SpanPrefilter
    from rag_backend.dense import LocalEncoder
    store=KnowledgeStore(ROOT/'var/research-expanded.sqlite3')
    records=store.documents('abstract');cases=json.loads((ROOT/'data/expanded_literature_queries.json').read_text())
    report=json.loads(OUT.read_text());setup=time.perf_counter()
    prefilter=SpanPrefilter(LocalEncoder(),ROOT/'var/expanded-vectors.sqlite3')
    prefilter.vectors([d['title']+'\n'+d['text'] for d in records])
    if kind=='bge':
        from rag_backend.research_models import CrossEncoderReranker
        base=CrossEncoderReranker()
        configs={'bge_overlap20':(None,20),'bge_dense20':(prefilter,20),'bge_dense10':(prefilter,10)}
    else:
        from rag_backend.literature_reranker import EnglishLiteratureReranker
        base=EnglishLiteratureReranker();configs={'tiny_en_dense10':(prefilter,10)}
        cases=[c for c in cases if c['language']=='en']
    rankers={key:CachedReranker(base) for key in configs}
    report.setdefault('execution',{})[kind]={'model':base.identity,'device':base.device,'dtype':base.dtype,
        'embedding':prefilter.encoder.name,'setup_seconds':time.perf_counter()-setup};save(report)
    for index,case in enumerate(cases):
        keys=list(configs);keys=keys[index%len(keys):]+keys[:index%len(keys)]
        for key in keys:
            filter_,pool=configs[key];started=time.perf_counter()
            ids,candidates=rank(records,case['query'],rankers[key],filter_,pool)
            position=ids.index(case['expected'])+1 if case['expected'] in ids else None
            row={k:case[k] for k in ('id','source_group','split','language','expected')}
            row.update(mode=key,ids=ids,candidate_ids=candidates,target_in_pool=case['expected'] in candidates,
                       hit_at_1=position==1,hit_at_3=position is not None,rr_at_3=1/position if position else 0,
                       scored_pairs=len(candidates),seconds=time.perf_counter()-started)
            report['rows'].append(row);save(report)
            print(case['id'],key,row['hit_at_1'],round(row['seconds'],2),flush=True)
    report['execution'][kind]['score_caches']={k:r.stats for k,r in rankers.items()};save(report)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--worker',choices=('bge','tiny'));args=parser.parse_args()
    if args.worker:run(args.worker);return
    from rag_backend.knowledge_lab import KnowledgeStore
    abstracts=json.loads((ROOT/'var/literature/expanded-abstracts.json').read_text())['records']
    store=KnowledgeStore(ROOT/'var/research-expanded.sqlite3');store.ingest(abstracts)
    report={'scope':'60 developer-authored queries paired by language over 30 curated abstracts. Target-ID retrieval, not answer correctness. Source groups split 15/15 before inference; paired languages are not independent.',
            'dataset_sha256':hashlib.sha256((ROOT/'data/expanded_literature_queries.json').read_bytes()).hexdigest(),
            'corpus':{d['id']:d['content_hash'] for d in store.documents('abstract')},'rows':[],
            'limits':['Exact brute-force vector candidates, no ANN scale claim.',
                      'Tiny reranker evaluated on English only, never averaged as Korean performance.',
                      'Different CPU/MPS models have different memory contexts; device and precision are recorded.']}
    cases=json.loads((ROOT/'data/expanded_literature_queries.json').read_text())
    for case in cases:
        begin=time.perf_counter();ids=[d['id'] for d in store.search(case['query'])]
        position=ids.index(case['expected'])+1 if case['expected'] in ids else None
        report['rows'].append({**{k:case[k] for k in ('id','source_group','split','language','expected')},
            'mode':'token_overlap','ids':ids,'hit_at_1':position==1,'hit_at_3':position is not None,
            'rr_at_3':1/position if position else 0,'seconds':time.perf_counter()-begin,'scored_pairs':0})
    save(report)
    for kind in ('bge','tiny'):
        subprocess.run([sys.executable,str(Path(__file__)),'--worker',kind],cwd=ROOT,check=True)
    report=json.loads(OUT.read_text());report['summary']={}
    for mode in sorted({r['mode'] for r in report['rows']}):
        report['summary'][mode]={}
        for language in ('ko','en'):
            rows=[r for r in report['rows'] if r['mode']==mode and r['language']==language]
            if not rows:continue
            report['summary'][mode][language]={'n':len(rows),'hit_at_1':sum(r['hit_at_1'] for r in rows),
                'hit_at_3':sum(r['hit_at_3'] for r in rows),'mrr_at_3':statistics.mean(r['rr_at_3'] for r in rows),
                'median_seconds':statistics.median(r['seconds'] for r in rows),'scored_pairs':sum(r['scored_pairs'] for r in rows),
                'target_in_pool':sum(r.get('target_in_pool',False) for r in rows) if mode!='token_overlap' else None}
    save(report);print(json.dumps(report['summary']),flush=True)


if __name__=='__main__':main()
