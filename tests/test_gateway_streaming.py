"""网关必须在流读完前返回响应，并在客户端断开时关闭上游。"""
import httpx
import pytest
from src.modules.gateway.services.proxy import RequestProxy

@pytest.mark.asyncio
async def test_proxy_does_not_buffer_sse():
    class Stream(httpx.AsyncByteStream):
        read = False
        closed = False
        async def __aiter__(self):
            self.read = True
            yield b'data: {"content":"first"}\n\n'
        async def aclose(self):
            self.closed = True
    stream = Stream()
    proxy = RequestProxy.__new__(RequestProxy)
    proxy.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers={'content-type':'text/event-stream'}, stream=stream)))
    response = await proxy._send_request('POST','http://chat/stream',{},b'{}',30)
    assert not stream.read, '网关在返回响应之前已经消耗整个流'
    forwarded = await proxy._handle_streaming_response(response, {})
    reader = forwarded.body_iterator
    await anext(reader)
    await reader.aclose()
    assert stream.closed
    await proxy.close()
