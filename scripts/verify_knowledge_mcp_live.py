"""SDK -> local AI endpoint -> current source span, without approval actions."""
import asyncio
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


async def main():
    from mcp import Client
    from rag_backend.knowledge_mcp import create_server
    from rag_backend.knowledge_lab import KnowledgeStore
    store=KnowledgeStore(ROOT/'var/knowledge.sqlite3')
    async with Client(create_server(store),read_timeout_seconds=90) as client:
        before=await client.call_tool('curation_status',{})
        result=await client.call_tool('research_literature',{'question':'Which paper studies IO-aware exact attention?'})
        assert not result.is_error,result
        graph=result.structured_content;ids=sorted({e['source_id'] for e in graph['edges']})
        after=await client.call_tool('curation_status',{})
        checks={'actual_ai_endpoint_connected':ids==['arxiv:2205.14135'],
            'source_versions_current':graph['source_versions_current'],
            'human_review_required':graph['requires_human_review'],'approval_not_performed':graph['approval_performed'] is False,
            'review_state_unchanged':before.structured_content['reviews']==after.structured_content['reviews']}
        report={'checks':checks,'source_ids':ids,'scope':'Actual local model endpoint and MCP quote revalidation. No approval or paid API call.'}
    (ROOT/'reports/knowledge-mcp-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(checks))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':asyncio.run(main())
