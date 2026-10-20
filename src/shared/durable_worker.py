"""At-least-once worker. Domain handlers must use idempotent side effects."""
import asyncio
from uuid import uuid4
from src.shared.operation_journal import journal


class DurableWorker:
    def __init__(self, lane, handler, cleanup=None, concurrency=1):
        self.lane, self.handler = lane, handler
        self.cleanup = cleanup
        self.concurrency = max(1, concurrency)
        self.owner = str(uuid4())
        self.task = None

    def start(self):
        if not self.task or self.task.done(): self.task = asyncio.create_task(self.run_workers())

    async def run_workers(self):
        await asyncio.gather(*(self.run() for _ in range(self.concurrency)))

    async def run(self):
        while True:
            try:
                record = journal().claim(self.lane, self.owner)
                if not record:
                    await asyncio.sleep(1)
                    continue
                async def heartbeat():
                    while True:
                        journal().heartbeat(record['id'], self.owner)
                        await asyncio.sleep(10)
                beat = asyncio.create_task(heartbeat())
                try:
                    result = await self.handler(record['payload'], record['id'])
                    if journal().finish(record['id'], self.owner, result):
                        journal().event('task.completed', self.lane, 'completed', operation_id=record['id'])
                        if self.cleanup: self.cleanup(record['payload'])
                except asyncio.CancelledError:
                    journal().retry(record['id'], self.owner, record['attempts'])
                    raise
                except Exception:
                    journal().retry(record['id'], self.owner, record['attempts'])
                finally:
                    beat.cancel()
                    await asyncio.gather(beat, return_exceptions=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(5)

    async def wait(self, identifier):
        self.start()
        while True:
            record = journal().work(identifier)
            if record['status'] == 'completed': return record['result']
            if record['status'] in ('failed','cancelled'): raise RuntimeError('Operation recovery limit reached or cancelled')
            await asyncio.sleep(.25)
