"""流式调用保留模型、token 限制和消息，且不把 SSE 心跳当正文。"""
import json
from unittest.mock import patch
import httpx
import pytest
from src.modules.llm_chat import LLMToolService
from src.shared.clients.llm_service_client import LLMServiceClient

@pytest.mark.asyncio
async def test_stream_preserves_request_and_ignores_heartbeat(monkeypatch):
    monkeypatch.setenv('SERVICE_AUTH_TOKEN','unit-test')
    seen = []
    def handle(request):
        seen.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, text=': connection established\n\ndata: {"content":"软件"}\n\ndata: {"content":"工程师"}\n\n')
    original = httpx.AsyncClient
    tool = LLMToolService()
    tool.llm_client = LLMServiceClient()
    with patch('src.shared.clients.llm_service_client.httpx.AsyncClient', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs)):
        output = ''.join([part async for part in tool.stream_generate('职位是什么？', model='chosen-model', max_tokens=128)])
    assert output == '软件工程师'
    path, payload = seen[0]
    assert path.endswith('/chat')
    assert payload['model'] == 'chosen-model'
    assert payload['max_tokens'] == 128
    assert payload['messages'][-1]['content'] == '职位是什么？'
