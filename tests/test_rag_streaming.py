import asyncio
from unittest.mock import AsyncMock, Mock
import pytest
from src.modules.lightraglocal.services.enterprise_lightrag_service import EnterpriseLightRAGService

@pytest.mark.asyncio
async def test_first_chunk_is_available_before_generation_completes():
    release = asyncio.Event()
    async def chunks():
        yield 'first'
        await release.wait()
        yield ' second'
    rag = Mock()
    rag.aquery = AsyncMock(return_value=chunks())
    rag.llm_model_func = AsyncMock()
    service = EnterpriseLightRAGService.__new__(EnterpriseLightRAGService)
    service._get_project_rag = AsyncMock(return_value=rag)
    stream = service.stream_query_project('project', 'question')
    assert (await anext(stream))['stage'] == 'generating'
    assert await asyncio.wait_for(anext(stream), 0.5) == {'content': 'first'}
    assert rag.aquery.call_args.args[1].stream is True
    release.set()
    rest = [event async for event in stream]
    assert rest[0] == {'content': ' second'}
    assert rest[-1]['done'] is True
    assert rest[-1]['timings']['first_token_ms'] is not None

@pytest.mark.asyncio
async def test_cached_answer_and_stream_errors():
    service = EnterpriseLightRAGService.__new__(EnterpriseLightRAGService)
    rag = Mock(llm_model_func=AsyncMock(), aquery=AsyncMock(return_value='cached'))
    service._get_project_rag = AsyncMock(return_value=rag)
    events = [event async for event in service.stream_query_project('p', 'q')]
    assert events[1] == {'content': 'cached'}
    assert events[-1]['done']
    async def broken():
        yield 'partial'
        raise RuntimeError('upstream failed')
    rag.aquery.return_value = broken()
    with pytest.raises(RuntimeError, match='upstream failed'):
        _ = [event async for event in service.stream_query_project('p', 'q')]

@pytest.mark.asyncio
async def test_stream_endpoint_authorizes_before_starting_generation(monkeypatch):
    import httpx
    from fastapi import FastAPI, HTTPException
    from src.modules.lightraglocal.routes import enterprise_rag_routes as routes
    async def denied(*args, **kwargs):
        raise HTTPException(404, 'Project not found')
    monkeypatch.setattr(routes, '_require_project_access', denied)
    factory = AsyncMock()
    monkeypatch.setattr(routes, 'get_enterprise_lightrag_service', factory)
    app = FastAPI()
    app.include_router(routes.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/rag/search/stream', json={'project_id':'other-project','query':'question'})
    assert response.status_code == 404
    factory.assert_not_called()
