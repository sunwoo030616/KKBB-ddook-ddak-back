import asyncio

import pytest

pytest.importorskip('mcp')
from mcp import Client
from rag_backend.knowledge_lab import KnowledgeStore
from rag_backend.knowledge_mcp import create_server

DOC={'id':'test:paper','title':'Synthetic MCP paper','text':'Synthetic source evidence about controlled retrieval for protocol testing.',
     'kind':'abstract','source_url':'https://example.com/paper'}


def store(tmp_path):
    result=KnowledgeStore(tmp_path/'knowledge.db');result.ingest([DOC]);return result


def test_actual_mcp_handshake_discovery_and_version_checked_quote(tmp_path):
    s=store(tmp_path)
    async def check():
        async with Client(create_server(s)) as client:
            tools=await client.list_tools()
            assert {t.name for t in tools.tools}=={'catalog_sources','search_sources','read_source_span','research_literature','curation_status'}
            assert all(t.annotations.read_only_hint and not t.annotations.destructive_hint for t in tools.tools)
            result=await client.call_tool('search_sources',{'question':'retrieval'})
            assert not result.is_error
            hit=result.structured_content['hits'][0]
            quote=await client.call_tool('read_source_span',{'source_id':hit['id'],'expected_hash':hit['hash'],'start':0,'end':9})
            assert quote.structured_content['quote']=='Synthetic'
            s.ingest([{**DOC,'text':DOC['text']+' Updated.'}])
            stale=await client.call_tool('read_source_span',{'source_id':hit['id'],'expected_hash':hit['hash'],'start':0,'end':9})
            assert stale.is_error and stale.structured_content is None
    asyncio.run(check())


def test_mcp_rejects_invalid_limits_and_never_exposes_mutation_tools(tmp_path):
    async def check():
        async with Client(create_server(store(tmp_path))) as client:
            assert (await client.call_tool('catalog_sources',{'limit':10000})).is_error
            assert (await client.call_tool('search_sources',{'question':'   '})).is_error
            assert (await client.call_tool('approve',{'id':DOC['id']})).is_error
    asyncio.run(check())


def test_mcp_neural_result_rechecks_hash_instead_of_trusting_backend_flag(tmp_path):
    s=store(tmp_path);hash=s.documents()[0]['content_hash']
    def backend(question):
        s.ingest([{**DOC,'text':DOC['text']+' Changed while searching.'}])
        return {'source_versions_current':True,'edges':[{'source_id':DOC['id'],'source_hash':hash,'start':0,'end':9,'text':'Synthetic'}]}
    async def check():
        async with Client(create_server(s,backend)) as client:
            result=await client.call_tool('research_literature',{'question':'retrieval'})
            assert result.is_error and result.structured_content is None
    asyncio.run(check())
