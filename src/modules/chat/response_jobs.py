"""将回复生成任务与浏览器连接分离，断开连接后仍完成持久化。"""
import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable


class ResponseJob:
    def __init__(self, source: AsyncIterator[str], persist: Callable[[str], Awaitable[None]]):
        self.queue = asyncio.Queue()
        self.task = asyncio.create_task(self._run(source, persist))

    async def _run(self, source, persist):
        parts = []
        thoughts = []
        async def save(text):
            if thoughts:
                await persist(text, thinking="".join(thoughts))
            else:
                await persist(text)
        try:
            async for chunk in source:
                event = chunk if isinstance(chunk, dict) else {'content': chunk}
                if event.get('content'):
                    parts.append(event['content'])
                if event.get('thinking'):
                    thoughts.append(event['thinking'])
                self.queue.put_nowait(event)
            text = ''.join(parts).strip() or '未生成有效回复，请重试。'
            await save(text)
        except asyncio.CancelledError:
            # 主动停止仍保存已有正文；断开页面连接不会触发此分支。
            await save(''.join(parts).strip() or '已停止生成。')
            self.queue.put_nowait({'stopped': True})
        except Exception as exc:
            self.queue.put_nowait({'error': str(exc)})
        finally:
            self.queue.put_nowait({'content': '', 'done': True})

    async def events(self):
        while True:
            event = await self.queue.get()
            yield event
            if event.get('done'):
                return


class ResponseJobs:
    def __init__(self):
        self.tasks = defaultdict(set)

    def start(self, key, source, persist):
        job = ResponseJob(source, persist)
        self.tasks[key].add(job.task)
        def finished(task):
            self.tasks[key].discard(task)
            if not self.tasks[key]:
                del self.tasks[key]
        job.task.add_done_callback(finished)
        return job

    def pending(self, key):
        return any(not task.done() for task in self.tasks.get(key, ()))

    async def stop(self, key):
        # 让刚创建的生成器进入受保护的执行区，再取消该会话的任务。
        await asyncio.sleep(0)
        tasks = [task for task in self.tasks.get(key, ()) if not task.done()]
        for task in tasks:
            if not task.cancelling():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks)
        return len(tasks)
