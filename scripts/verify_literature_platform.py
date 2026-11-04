"""Live cold-first request observations; run immediately after server readiness."""
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def http(path,body=None):
    request=urllib.request.Request('http://127.0.0.1:8767'+path,
        data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=90) as response:return json.load(response)


def main():
    from rag_backend.knowledge_lab import KnowledgeStore
    store=KnowledgeStore(ROOT/'var/knowledge.sqlite3');before={d['id']:d['content_hash'] for d in store.documents()}
    health=http('/health');reviews_before=http('/knowledge/curation/status')['reviews']
    cases={c['id']:c for name in ['model_routing_holdout.json','literature_fresh_validation.json','evidence_graph_cases.json','literature_guard_cases.json']
           for c in json.loads((ROOT/'data'/name).read_text())}
    report={'scope':'Actual HTTP default adaptive route. First request follows fresh server readiness; repeated request may use exact generation cache.',
        'environment':health,'rows':[]}
    for id in ['h4','h4','g2','v2','h7','q11']:
        start=time.perf_counter();result=http('/knowledge/research',{'question':cases[id]['question']});seconds=time.perf_counter()-start
        actual=sorted({e['source_id'] for e in result['edges']})
        row={'id':id,'seconds':seconds,'status':result['status'],'mode':result['mode'],'actual':actual,'expected':sorted(cases[id]['expected_sources']),
            'strict_source_match':actual==sorted(cases[id]['expected_sources']),'resource_setup_ms':result['resource_setup_ms'],
            'request_latency_ms':result['request_latency_ms'],'graph_latency_ms':result.get('latency_ms'),
            'source_versions_current':result.get('source_versions_current'),'trace':result['trace'],
            'llm_calls':sum(t.get('model_calls',0) or 0 for t in result['trace'])}
        report['rows'].append(row);(ROOT/'reports/literature-platform-api.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(id,round(seconds,3),row['status'],row['strict_source_match'],'LLM',row['llm_calls'],flush=True)
    report['checks']={'default_adaptive':all(r['mode']=='adaptive' for r in report['rows']),
        'cold_first_request_under_60_seconds':report['rows'][0]['seconds']<60,
        'h4_correct_after_fresh_start':report['rows'][0]['strict_source_match'],
        'all_source_versions_current':all(r['source_versions_current'] for r in report['rows']),
        'at_most_one_generative_call_per_request':all(r['llm_calls']<=1 for r in report['rows']),
        'unsupported_measurement_skips_llm':report['rows'][-2]['llm_calls']==0 and not report['rows'][-2]['actual'],
        'mutation_request_rejected_without_llm':report['rows'][-1]['status']=='out_of_scope' and report['rows'][-1]['llm_calls']==0,
        'no_source_data_changes':before=={d['id']:d['content_hash'] for d in store.documents()},
        'review_state_unchanged':reviews_before==http('/knowledge/curation/status')['reviews'],
        'paid_generation_unconfigured':not health['llm_configured']}
    report['after']=http('/health');report['complete']=True
    (ROOT/'reports/literature-platform-api.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if not all(report['checks'].values()):raise SystemExit('platform_integration_check_failed')


if __name__=='__main__':main()
