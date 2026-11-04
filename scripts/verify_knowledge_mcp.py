"""Real stdio initialize/list/call round trip against a synthetic local DB."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


async def verify(path):
    from mcp import Client,StdioServerParameters
    params=StdioServerParameters(command=sys.executable,args=['-m','rag_backend.knowledge_mcp','--db',str(path)],cwd=ROOT)
    async with Client(params,read_timeout_seconds=15) as client:
        tools=await client.list_tools()
        result=await client.call_tool('search_sources',{'question':'synthetic retrieval'})
        assert not result.is_error and len(result.structured_content['hits'])==1
        hit=result.structured_content['hits'][0]
        quote=await client.call_tool('read_source_span',{'source_id':hit['id'],'expected_hash':hit['hash'],'start':0,'end':9})
        assert quote.structured_content['quote']=='Synthetic'
        invalid=await client.call_tool('catalog_sources',{'limit':10000})
        assert invalid.is_error
        return {'transport':'stdio','initialized':True,'tools':[t.name for t in tools.tools],
            'read_only_annotations':all(t.annotations.read_only_hint and not t.annotations.destructive_hint for t in tools.tools),
            'actual_search_and_quote':True,'invalid_input_rejected':True,'scope':'Synthetic protocol test; no neural call or approval performed.'}


def main():
    from rag_backend.knowledge_lab import KnowledgeStore
    with tempfile.TemporaryDirectory(prefix='mcp-stdio-',dir=ROOT/'var') as folder:
        path=Path(folder)/'knowledge.db';KnowledgeStore(path).ingest([{'id':'synthetic:mcp','title':'Synthetic protocol test',
            'text':'Synthetic retrieval evidence for a controlled stdio test.','kind':'abstract','source_url':'https://example.com/synthetic'}])
        report=asyncio.run(verify(path))
    (ROOT/'reports/knowledge-mcp-stdio.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
