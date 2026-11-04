#!/usr/bin/env python3
"""Incremental AI curation + multilingual retrieval + exact-cache experiments.

Stop other model servers before running to avoid two copies of GPU weights.
Full source abstracts and pending notes stay in ignored var/.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rag_backend.knowledge_lab import KnowledgeStore
from rag_backend.inference_cache import MemoizedGenerator
from rag_backend.evidence_agent import SearchAction
from rag_backend.research_models import MLXGenerator,CrossEncoderReranker


def brief(result):return {k:v for k,v in result.items() if k!='new_notes'}


def run():
    abstracts=json.loads((ROOT/'var/literature/abstracts.json').read_text())['records']
    finance=json.loads((ROOT/'data/financial_guides.json').read_text())['chunks']
    records=abstracts+[{'id':'finance:'+r['id'],'title':r['title'],'text':r['text'],
        'source_url':r['url'],'kind':'financial_summary','institution':r['institution'],
        'verified_at':r['verified_at']} for r in finance]
    kb=KnowledgeStore(ROOT/'var/knowledge.sqlite3')
    ingest=kb.ingest(records)
    base=MLXGenerator('canvas_generator');cached=MemoizedGenerator(base)
    print('Preparing review candidates for',len(records),'documents',flush=True)
    first=kb.prepare_notes(cached)
    second_ingest=kb.ingest(records);second=kb.prepare_notes(cached)
    notes=kb.notes();by_id={r['id']:r for r in kb.documents()}
    checks=[by_id[n['source_id']]['text'][n['start']:n['end']]==n['quote']
            and by_id[n['source_id']]['content_hash']==n['source_hash'] for n in notes]
    automation={'first_ingest':ingest,'first_run':brief(first),'second_ingest':second_ingest,
        'second_run':brief(second),'notes':len(notes),'all_source_offsets_valid':all(checks),
        'scope':'Pending-review source spans, NOT approved factual claims. Full abstracts and quotes are local only.'}
    (ROOT/'reports/knowledge-automation.json').write_text(json.dumps(automation,ensure_ascii=False,indent=2)+'\n')
    print('Automation',json.dumps(brief(first)),json.dumps(brief(second)),flush=True)
    reranker=CrossEncoderReranker();raw=(ROOT/'data/literature_queries.json').read_bytes()
    evaluation={'scope':'12 developer-authored topic queries, 6 source abstracts, language-paired and not independent. '
        'Lexical vs whole small-pool multilingual cross-encoder; not an ANN benchmark.',
        'dataset_sha256':hashlib.sha256(raw).hexdigest(),'rows':[]}
    for case in json.loads(raw):
        for mode in ('lexical','neural'):
            started=time.perf_counter();hits=kb.search(case['query'],reranker=reranker if mode=='neural' else None)
            ids=[h['id'] for h in hits];rank=ids.index(case['expected'])+1 if case['expected'] in ids else None
            evaluation['rows'].append({'id':case['id'],'mode':mode,'ids':ids,'expected':case['expected'],
                'hit_at_1':rank==1,'hit_at_3':rank is not None,'rr_at_3':1/rank if rank else 0,
                'seconds':time.perf_counter()-started})
    evaluation['summary']={mode:{'n':len(rows),'hit_at_1':sum(r['hit_at_1'] for r in rows),
        'hit_at_3':sum(r['hit_at_3'] for r in rows),'mrr_at_3':statistics.mean(r['rr_at_3'] for r in rows)}
        for mode in ('lexical','neural') if (rows:=[r for r in evaluation['rows'] if r['mode']==mode])}
    (ROOT/'reports/literature-retrieval.json').write_text(json.dumps(evaluation,ensure_ascii=False,indent=2)+'\n')
    print('Retrieval',json.dumps(evaluation['summary']),flush=True)
    system='Return action search, queries containing ONE protection topic query. JSON only. Use exact query 예금보호 한도.'
    prompts=['예금보호 기준을 확인해줘','보호 대상 원금과 이자 안내를 찾아줘']
    result={'scope':'Exact result memoization, not KV caching. Two prompts repeated three times; warmed model. '
            'This duplicate workload does not estimate production cache hit rate.','rows':[]}
    reference={}
    for mode,generator in [('off',base),('on',MemoizedGenerator(base))]:
        for repeat in range(3):
            for i,user in enumerate(prompts):
                started=time.perf_counter();output=generator.complete(system,user,max_tokens=120,output_type=SearchAction)
                parsed=SearchAction.model_validate_json(output['text']).model_dump()
                if mode=='off' and repeat==0:reference[i]=parsed
                result['rows'].append({'mode':mode,'repeat':repeat,'prompt_index':i,
                    'seconds':time.perf_counter()-started,'model_calls':output.get('model_calls',1),
                    'cache_hit':output.get('cache_hit',False),'same_as_initial':parsed==reference[i]})
        if mode=='on':result['cache_stats']=generator.snapshot()
    concurrent=MemoizedGenerator(base)
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs=list(pool.map(lambda _:concurrent.complete(system,prompts[0],max_tokens=120,output_type=SearchAction),range(4)))
    result['concurrent_duplicates']={'submitted':len(outputs),'model_calls':sum(r['model_calls'] for r in outputs),
        'identical_outputs':len({r['text'] for r in outputs})==1,'stats':concurrent.snapshot()}
    result['summary']={mode:{'n':len(rows),'model_calls':sum(r['model_calls'] for r in rows),
        'median_seconds':statistics.median(r['seconds'] for r in rows),'equivalent':all(r['same_as_initial'] for r in rows)}
        for mode in ('off','on') if (rows:=[r for r in result['rows'] if r['mode']==mode])}
    (ROOT/'reports/exact-inference-cache.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Cache',json.dumps(result['summary']),flush=True)


if __name__=='__main__':run()
