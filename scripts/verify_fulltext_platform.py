"""Actual local HTTP and MCP checks after restoring the final free-model server."""
import asyncio
import hashlib
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


async def main():
    from mcp import Client
    from rag_backend.knowledge_lab import KnowledgeStore
    from rag_backend.knowledge_catalog import KnowledgeCatalog
    from rag_backend.knowledge_mcp import create_server
    store=KnowledgeStore(ROOT/'var/knowledge.sqlite3');catalog=KnowledgeCatalog(store)
    before={d['id']:d['content_hash'] for d in store.documents()};reviews_before=http('/knowledge/curation/status')['reviews']
    health=http('/health');hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'rag_backend').glob('*.py')}
    cases={c['id']:c for name in ['evidence_graph_cases.json','literature_fresh_validation.json','literature_preregistered_evaluation.json'] for c in json.loads((ROOT/'data'/name).read_text())}
    acceptance=json.loads((ROOT/'data/literature_missing_case_acceptance.json').read_text())['cases']
    rows=[]
    for id in ['g3','g3','v4','i11']:
        start=time.perf_counter();graph=http('/knowledge/research',{'question':cases[id]['question']});elapsed=time.perf_counter()-start
        actual=sorted({e['source_id'] for e in graph['edges']})
        quotes_ok=True;locations_ok=True
        for edge in graph['edges']:
            span=catalog.source_span(edge['source_id'],edge['source_hash'],edge['start'],edge['end'])
            quotes_ok &= span['quote']==edge['text']
            if edge.get('page') is not None:locations_ok &= span['citation_location'].get('page')==edge['page'] and span['citation_location']['url']==edge['url']
        task_match=all(sorted({e['source_id'] for e in graph['edges'] if e['task_id']==task})==expected for task,expected in acceptance.get(id,{}).items())
        rows.append({'id':id,'seconds':elapsed,'actual':actual,'exact':actual==sorted(cases[id]['expected_sources']),
            'status':graph['status'],'source_versions_current':graph['source_versions_current'],'task_sources_match':task_match,
            'quotes_valid':quotes_ok,'page_locations_valid':locations_ok,
            'citation_count':len(graph['edges']),'body_citations':sum(e.get('page') is not None for e in graph['edges']),
            'model_calls':sum(t.get('model_calls',0) or 0 for t in graph['trace']),
            'trace':graph['trace'],'resource_setup_ms':graph['resource_setup_ms']})
        print(id,round(elapsed,3),rows[-1]['exact'],'citations',len(graph['edges']),flush=True)
    async with Client(create_server(store),read_timeout_seconds=90) as client:
        result=await client.call_tool('research_literature',{'question':cases['g3']['question']})
        if result.is_error:raise ValueError('live_mcp_fulltext_failed')
        mcp=result.structured_content
        body=next(e for e in mcp['edges'] if e.get('page') is not None)
        reread=await client.call_tool('read_source_span',{'source_id':body['source_id'],'expected_hash':body['source_hash'],'start':body['start'],'end':body['end']})
        mcp_checks={'mcp_sources_correct':sorted({e['source_id'] for e in mcp['edges']})==sorted(cases['g3']['expected_sources']),
            'mcp_multiple_citations':len([e for e in mcp['edges'] if e['task_id']=='t0'])==2,
            'mcp_page_reread':not reread.is_error and reread.structured_content['citation_location']['page']==body['page'],
            'mcp_no_approval':mcp['approval_performed'] is False and mcp['requires_human_review'] is True}
    checks={'all_http_sources_match':all(r['exact'] and r['task_sources_match'] for r in rows),
        'all_quotes_current':all(r['quotes_valid'] and r['source_versions_current'] for r in rows),
        'all_page_locations_valid':all(r['page_locations_valid'] for r in rows),
        'missing_cases_have_body_evidence':all(r['body_citations']>0 for r in rows if r['id'] in ('g3','v4')),
        'repaired_mutation_route_skips_generation':rows[-1]['status']=='out_of_scope' and rows[-1]['model_calls']==0,
        'at_most_one_generative_call':all(r['model_calls']<=1 for r in rows),
        'source_data_unchanged':before=={d['id']:d['content_hash'] for d in store.documents()},
        'review_state_unchanged':reviews_before==http('/knowledge/curation/status')['reviews'],
        'paid_generation_unconfigured':not health['llm_configured'],
        'runtime_sources_match':health['runtime_source_sha256']==hashes,**mcp_checks}
    report={'scope':'Live final HTTP/MCP acceptance. i11 is now observed regression, NOT a new independent evaluation. g3 first request follows fresh server; repeat may reuse exact generation cache.',
        'backend_sha256':hashes,'rows':rows,'checks':checks,'complete':True}
    (ROOT/'reports/fulltext-platform-api.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(checks,flush=True)
    if not all(checks.values()):raise SystemExit('fulltext_live_check_failed')

if __name__=='__main__':asyncio.run(main())
