"""浏览器断开后仍生成、保存回复，保存完成后才报告任务结束。"""
import asyncio
import pytest
from src.modules.chat.response_jobs import ResponseJobs

@pytest.mark.asyncio
async def test_disconnected_consumer_does_not_cancel_generation():
    jobs = ResponseJobs()
    release = asyncio.Event()
    saved = []
    async def generate():
        yield 'first '
        await release.wait()
        yield 'answer'
    async def persist(text):
        saved.append(text)
    job = jobs.start(('project', 'user'), generate(), persist)
    consumer = job.events()
    assert await anext(consumer) == {'content': 'first '}
    await consumer.aclose()
    assert jobs.pending(('project', 'user'))
    release.set()
    await job.task
    assert saved == ['first answer']
    assert not jobs.pending(('project', 'user'))

@pytest.mark.asyncio
async def test_completion_is_sent_after_persistence():
    jobs = ResponseJobs()
    saved = []
    async def generate():
        yield 'answer'
    async def persist(text):
        await asyncio.sleep(0)
        saved.append(text)
    job = jobs.start(('project', 'user'), generate(), persist)
    async for event in job.events():
        if event.get('done'):
            assert saved == ['answer']

@pytest.mark.asyncio
async def test_stop_cancels_producer_and_preserves_partial_reply():
    jobs = ResponseJobs()
    closed = asyncio.Event()
    saved = []
    async def generate():
        try:
            yield '已生成的内容'
            await asyncio.Event().wait()
            yield '不应继续生成'
        finally:
            closed.set()
    async def persist(text):
        saved.append(text)
    key = ('project', 'user', 'conversation')
    job = jobs.start(key, generate(), persist)
    events = job.events()
    assert await anext(events) == {'content':'已生成的内容'}
    assert await jobs.stop(key) == 1
    assert closed.is_set()
    assert saved == ['已生成的内容']
    assert not jobs.pending(key)
    remaining = [event async for event in events]
    assert any(event.get('stopped') for event in remaining)
    assert await jobs.stop(key) == 0

@pytest.mark.asyncio
async def test_stop_before_first_token_is_saved_and_other_conversations_continue():
    jobs = ResponseJobs()
    entered = asyncio.Event()
    saved = []
    async def generate():
        entered.set()
        await asyncio.Event().wait()
        yield 'unused'
    async def persist(text):
        saved.append(text)
    first = jobs.start(('p','u','a'), generate(), persist)
    other = jobs.start(('p','u','b'), generate(), persist)
    await entered.wait()
    await jobs.stop(('p','u','a'))
    assert saved == ['已停止生成。']
    assert jobs.pending(('p','u','b'))
    await jobs.stop(('p','u','b'))

@pytest.mark.asyncio
@pytest.mark.parametrize('stop', [True, False])
async def test_thinking_is_persisted_separately_after_disconnect_or_stop(stop):
    jobs = ResponseJobs()
    release = asyncio.Event()
    saved = []
    async def generate():
        yield {'thinking': 'reasoning'}
        await release.wait()
        yield {'content': 'answer'}
    async def persist(text, thinking=''):
        saved.append((text, thinking))
    key = ('p', 'u', 'thinking')
    job = jobs.start(key, generate(), persist)
    events = job.events()
    assert await anext(events) == {'thinking':'reasoning'}
    await events.aclose()
    if stop:
        await jobs.stop(key)
    else:
        release.set()
        await job.task
    assert saved == [('已停止生成。' if stop else 'answer', 'reasoning')]
