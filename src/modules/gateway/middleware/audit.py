"""Record request lifecycle without reading bodies, credentials or query strings."""
from uuid import uuid4
from src.shared.operation_journal import journal


class AuditMiddleware:
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] == 'OPTIONS' or scope['path'] in ('/', '/healthz', '/health'):
            return await self.app(scope, receive, send)
        identifier = str(uuid4())
        action = scope['method']
        target = scope['path'][:512]
        journal().event('request.started', target, action, actor='unverified', operation_id=identifier)
        status = 500
        complete = False
        async def audited_send(message):
            nonlocal status, complete
            if message['type'] == 'http.response.start':
                status = message['status']
                message.setdefault('headers', []).append((b'x-operation-id', identifier.encode()))
            if message['type'] == 'http.response.body' and not message.get('more_body', False): complete = True
            await send(message)
        try:
            await self.app(scope, receive, audited_send)
        finally:
            user = scope.get('state', {}).get('user') or {}
            journal().event('request.finished', target, str(status) if complete else 'interrupted',
                            actor=user.get('user_id') or user.get('id') or 'anonymous', operation_id=identifier)
