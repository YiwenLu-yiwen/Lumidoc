"""检索只返回资料，当前问题不能被历史或再次生成的答案覆盖。"""
import json
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from src.modules.chat.chat_engine import ChatEngine

@pytest.mark.asyncio
@pytest.mark.parametrize('question', ['职位是什么？', '7加8是多少？'])
async def test_current_question_and_raw_context_are_streamed(question):
    captured = {}
    class LLM:
        async def stream_generate(self, prompt, **kwargs):
            captured.update(prompt=prompt, **kwargs)
            yield '针对问题的回答'
        async def process_general(self, **kwargs):
            raise AssertionError('必须直接流式生成，不能等待整篇回答')
    def handle(request):
        captured['retrieval'] = json.loads(request.content)
        return httpx.Response(200, json={'success': True, 'result': '来源：招聘.txt\n职位：软件工程师'})
    original = httpx.AsyncClient
    with patch('src.modules.chat.chat_engine.httpx.AsyncClient', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs)):
        result = ''.join([chunk async for chunk in ChatEngine(LLM()).chat_stream(question, project_id='project', model='qwen3:1.7b')])
    assert result == '针对问题的回答'
    assert captured['retrieval']['only_need_context'] is True
    assert captured['prompt'].rstrip().endswith(question)
    assert '招聘.txt' in captured['system_prompt']
    assert captured['history'] == []
    assert captured['model'] == 'qwen3:1.7b'
    assert captured['max_tokens'] <= 1024

@pytest.mark.asyncio
async def test_conversation_roles_are_isolated_and_current_question_not_duplicated():
    from unittest.mock import Mock
    question = '小红书：给我一个房产中介模版，不需要引用'
    captured = {}
    class LLM:
        async def stream_generate(self, prompt, **kwargs):
            captured.update(prompt=prompt, **kwargs)
            yield '标题：找到理想的家'
    messages = [
        {'id':'current','role':'user','content':question,'user_id':'u','session_id':'new','timestamp':'3'},
        {'id':'other','role':'assistant','content':'不应该带入的新会话历史','user_id':'u','session_id':'old','timestamp':'2'},
        {'id':'own','role':'user','content':'想要温馨的风格','user_id':'u','session_id':'new','timestamp':'1'},
    ]
    redis = Mock()
    redis.type.return_value = 'list'
    redis.lrange.return_value = [json.dumps(m) for m in messages]
    original = httpx.AsyncClient
    with patch('redis.Redis', return_value=redis), patch('src.modules.chat.chat_engine.httpx.AsyncClient', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(lambda req: httpx.Response(200,json={'success':True,'result':''})), **kwargs)):
        result = ''.join([part async for part in ChatEngine(LLM()).chat_stream(question, project_id='p',user_id='u',conversation_id='new')])
    assert '标题' in result
    assert captured['prompt'] == question
    assert captured['history'] == [{'role':'user','content':'想要温馨的风格'}]
    assert '写作' in captured['system_prompt']
