"""验证统一生成参数被转换成 Ollama 实际接受的 options。"""
import json
from unittest.mock import patch
import httpx
import pytest
from src.shared.llm.adapters.ollama import OllamaAdapter

@pytest.mark.asyncio
@pytest.mark.parametrize('threads', [None, '4'])
@pytest.mark.parametrize('method', ['chat', 'generate', 'chat_stream', 'generate_stream'])
async def test_generation_parameters_reach_ollama_options(method, threads, monkeypatch):
    if threads:
        monkeypatch.setenv('OLLAMA_NUM_THREADS', threads)
    else:
        monkeypatch.delenv('OLLAMA_NUM_THREADS', raising=False)
    requests = []
    def handle(request):
        requests.append(json.loads(request.content))
        body = {'message': {'content': 'OK'}, 'response': 'OK', 'done': True}
        return httpx.Response(200, json=body)
    transport = httpx.MockTransport(handle)
    original = httpx.AsyncClient
    with patch('src.shared.llm.adapters.ollama.httpx.AsyncClient', side_effect=lambda **kwargs: original(transport=transport, **kwargs)):
        adapter = OllamaAdapter('http://ollama:11434', 'qwen3:1.7b')
        value = [{'role': 'user', 'content': 'hello'}] if method.startswith('chat') else 'hello'
        result = getattr(adapter, method)(value, max_tokens=32, temperature=0.2, stop_sequences=['END'])
        if method.endswith('stream'):
            assert [part async for part in result] == ['OK']
        else:
            assert await result == 'OK'
    expected = {'num_predict': 32, 'temperature': 0.2, 'stop': ['END']}
    if threads:
        expected['num_thread'] = int(threads)
    assert requests[0]['options'] == expected
    assert requests[0]['think'] is False
    assert requests[0]['keep_alive'] == '15m'
    assert 'max_tokens' not in requests[0]

@pytest.mark.asyncio
@pytest.mark.parametrize('think', [True, False])
async def test_native_thinking_is_separate_from_answer(think):
    requests = []
    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, text='\n'.join(json.dumps(event) for event in [
            {'message': {'thinking': 'reasoning'}},
            {'message': {'content': 'answer'}, 'done': True},
        ]))
    original = httpx.AsyncClient
    with patch('src.shared.llm.adapters.ollama.httpx.AsyncClient', side_effect=lambda **kw: original(transport=httpx.MockTransport(handle), **kw)):
        adapter = OllamaAdapter('http://ollama:11434', 'model')
        events = [event async for event in adapter.chat_stream([{'role':'user','content':'question'}], think=think, stream_events=True)]
    assert events == ([{'thinking':'reasoning'}] if think else []) + [{'content':'answer'}]
    assert requests[0]['think'] is think
    assert 'stream_events' not in requests[0]
