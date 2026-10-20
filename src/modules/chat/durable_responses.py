"""Recover accepted chat requests without duplicating turns or storing tokens."""
import asyncio
import json
import os
from datetime import datetime, timezone
from uuid import uuid4
from src.shared.durable_worker import DurableWorker
from src.shared.operation_journal import journal


class DurableResponses:
    def __init__(self, manager, redis):
        self.manager, self.redis = manager, redis
        self.queues = {}
        self.active = {}
        self.worker = DurableWorker('chat.responses', self.execute, concurrency=int(os.getenv('CHAT_RECOVERY_WORKERS', '4')))

    def persist(self, identifier, payload, role, content, thinking=''):
        record = {'id': identifier+':'+role, 'role':role, 'content':content, 'thinking':thinking,
                  'project_id':payload['project_id'], 'user_id':payload['user_id'],
                  'session_id':payload['conversation_id'], 'timestamp':datetime.now(timezone.utc).isoformat()}
        self.redis.eval("""
          if redis.call('SETNX', KEYS[1], '1') == 1 then
            redis.call('LPUSH', KEYS[2], ARGV[1]); redis.call('PERSIST', KEYS[2]); return 1
          end
          return 0
        """, 2, 'chat:turn:'+record['id'], 'chat:history:'+str(payload['project_id']), json.dumps(record))

    async def execute(self, payload, identifier):
        queue = self.queues.get(identifier)
        self.persist(identifier, payload, 'user', payload['message'])
        if queue: await queue.put({'reset':True, 'recovering':True})
        parts, thoughts = [], []
        async def generate():
            async for chunk in self.manager.process_message_stream(**payload, auth_header='Service '+os.environ['SERVICE_AUTH_TOKEN']):
                event = chunk if isinstance(chunk, dict) else {'content':chunk}
                if event.get('error'): raise RuntimeError('Model generation interrupted')
                parts.append(event.get('content',''))
                thoughts.append(event.get('thinking',''))
                if queue: await queue.put(event)
        task = asyncio.create_task(generate())
        self.active[identifier] = task
        try:
            await task
            text = ''.join(parts).strip()
            if not text: raise RuntimeError('Empty model response')
            self.persist(identifier, payload, 'assistant', text, ''.join(thoughts))
            if queue: await queue.put({'done':True})
            return {'saved':True}
        except asyncio.CancelledError:
            if journal().work(identifier)['status'] == 'cancelled':
                self.persist(identifier, payload, 'assistant', ''.join(parts) or '已停止生成。', ''.join(thoughts))
                if queue:
                    await queue.put({'stopped':True})
                    await queue.put({'done':True})
                return {'stopped':True}
            raise
        except Exception:
            if queue: await queue.put({'reset':True, 'recovering':True})
            raise
        finally:
            self.active.pop(identifier, None)

    def start(self, payload):
        identifier = journal().enqueue('chat.responses', payload)
        self.persist(identifier, payload, 'user', payload['message'])
        self.queues[identifier] = asyncio.Queue()
        self.worker.start()
        parent = self
        class Stream:
            async def events(self):
                try:
                    while True:
                        try:
                            event = await asyncio.wait_for(parent.queues[identifier].get(), 2)
                        except asyncio.TimeoutError:
                            state = journal().work(identifier)['status']
                            if state == 'failed':
                                yield {'error':'Automatic recovery limit reached', 'done':True}
                                return
                            if state in ('completed','cancelled'):
                                yield {'done':True}
                                return
                            yield {'recovering':state in ('pending','recovering')}
                            continue
                        yield event
                        if event.get('done'): return
                finally:
                    parent.queues.pop(identifier, None)
        return Stream()

    def matching(self, key):
        matches = []
        for identifier in journal().unfinished('chat.responses'):
            payload = journal().work(identifier)['payload']
            if (str(payload['project_id']),str(payload['user_id']),payload['conversation_id']) == key:
                matches.append(identifier)
        return matches

    def pending(self, key): return bool(self.matching(key))

    def recovery_failed(self, key):
        with journal().connection() as db:
            rows = db.execute("SELECT payload,status FROM work WHERE lane='chat.responses' ORDER BY updated DESC").fetchall()
        for row in rows:
            payload = json.loads(row['payload'])
            if (str(payload['project_id']), str(payload['user_id']), payload['conversation_id']) == key:
                return row['status'] == 'failed'
        return False

    async def stop(self, key):
        matches = self.matching(key)
        tasks = []
        for identifier in matches:
            record = journal().work(identifier)
            journal().cancel(identifier)
            task = self.active.get(identifier)
            if task:
                task.cancel(); tasks.append(task)
            else:
                self.persist(identifier, record['payload'], 'assistant', '已停止生成。')
            journal().event('chat.stopped', str(key[0]), 'cancelled', actor=key[1], operation_id=identifier)
        if tasks: await asyncio.gather(*tasks, return_exceptions=True)
        return len(matches)
