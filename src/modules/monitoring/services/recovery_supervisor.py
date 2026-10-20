"""Bounded automatic recovery; state and interruptions survive controller restarts."""
import asyncio
import time
import os
from src.shared.operation_journal import journal

MAX_RESTARTS = int(os.getenv("AUTO_RESTART_MAX_ATTEMPTS", "3"))
WINDOW = int(os.getenv("AUTO_RESTART_WINDOW_SECONDS", "900"))
STABLE_SECONDS = 120


def decide(name, state, now=None):
    now = now or time.time()
    record = journal().get('recovery:' + name, {'attempts': [], 'failures': 0, 'blocked': False})
    record['state'] = state
    if state == 'healthy':
        record['failures'] = 0
        record.setdefault('healthy_since', now)
        if now - record['healthy_since'] >= STABLE_SECONDS and not record['blocked']:
            record['attempts'] = []
    elif state in ('unhealthy', 'exited', 'dead', 'created'):
        record.pop('healthy_since', None)
        record['failures'] += 1
    else:
        record['failures'] = 0  # Docker's startup grace is respected.
    attempts = [stamp for stamp in record['attempts'] if now-stamp < WINDOW]
    should_restart = False
    if record['failures'] >= 2 and not record['blocked'] and now-record.get('last_restart', 0) >= 60:
        if len(attempts) >= MAX_RESTARTS:
            record['blocked'] = True
            journal().event('service.recovery_exhausted', name, 'needs_attention')
        else:
            should_restart = True
            attempts.append(now)
            record.update(last_restart=now, failures=0)
            journal().event('service.interrupted', name, 'recovering')
    record['attempts'] = attempts
    record['restart_count'] = len(attempts)
    record['phase'] = 'needs_attention' if record['blocked'] else 'healthy' if state == 'healthy' else 'recovering'
    journal().put('recovery:' + name, record)
    return should_restart, record


async def supervise(control):
    while True:
        try:
            if os.getenv('AUTO_RESTART_ENABLED', 'true').lower() != 'true':
                await asyncio.sleep(10)
                continue
            async with control.docker_client() as client:
                prefix, rows = await control.containers(client)
                for name, service in control.SERVICES.items():
                    targets = [row for row in rows if row['Labels'].get('com.docker.compose.service') == service]
                    if not targets: continue
                    states = []
                    for target in targets:
                        result = await client.get(f'{prefix}/containers/{target["Id"]}/json')
                        result.raise_for_status()
                        state = result.json()['State']
                        states.append(state.get('Health', {}).get('Status', 'healthy') if state['Status'] == 'running' else state['Status'])
                    state = next((value for value in states if value != 'healthy'), 'healthy')
                    async with control.lock:
                        previous = control.operations.get(name, {})
                        if previous.get('status') == 'restarting': continue
                        restart, _ = decide(name, state)
                        if restart:
                            control.begin_restart(name, 'automatic')
                    if restart:
                        await control.perform_restart(name, 'automatic')
        except asyncio.CancelledError:
            raise
        except Exception:
            # Loss of the daemon must not trigger a restart storm or erase history.
            pass
        await asyncio.sleep(10)
