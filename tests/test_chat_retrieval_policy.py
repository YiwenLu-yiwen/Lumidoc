from unittest.mock import patch
import pytest
from src.modules.chat.retrieval_policy import should_retrieve, bounded_history
from src.modules.chat.chat_engine import ChatEngine

@pytest.mark.parametrize('message', ['你好', 'Hello!', '小红书：给我一个房产中介模版，不需要引用', 'Write a property listing template'])
@pytest.mark.asyncio
async def test_general_requests_never_wait_for_rag(message):
    class LLM:
        async def stream_generate(self, **kwargs):
            yield 'answer'
    with patch('src.modules.chat.chat_engine.httpx.AsyncClient', side_effect=AssertionError('RAG must be skipped')):
        result = [part async for part in ChatEngine(LLM()).chat_stream(message, project_id='p')]
    assert result == ['answer']

@pytest.mark.parametrize('message', ['职位是什么？', 'Summarize my uploaded file', '根据文档写一篇文案', 'Who is responsible?'])
def test_document_and_ambiguous_questions_keep_retrieval(message):
    assert should_retrieve(message, [])


def test_explicit_policy_and_followup():
    assert not should_retrieve('summarize my document', [], 'off')
    assert should_retrieve('hello', [], 'always')
    assert should_retrieve('Rewrite it', [{'content': 'The uploaded document discusses rent'}])


def test_history_budget_keeps_recent_roles():
    history = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': str(i)*3000} for i in range(8)]
    limited = bounded_history(history)
    assert sum(len(m['content']) for m in limited) <= 6000
    assert limited[-1]['content'].startswith('7')
    assert limited[-1]['role'] == 'assistant'
