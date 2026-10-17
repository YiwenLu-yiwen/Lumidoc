"""Narrow Docker control API, deployed separately from the web-facing monitor.

Only this process receives the Docker socket. Never accepts container IDs, shell
commands, images, or caller-selected Compose projects.
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from src.shared.project_access import require_admin

app = FastAPI(docs_url=None, redoc_url=None)
logger = logging.getLogger(__name__)
SERVICES = {name: f'{name}_service' for name in (
    'auth', 'project', 'file', 'fileproc', 'rag', 'chat', 'llm',
    'graph', 'question', 'monitoring',
)}
operations = {}
lock = asyncio.Lock()


def docker_client():
    return httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds='/var/run/docker.sock'),
                             base_url='http://docker', timeout=40)


async def containers(client):
    version = await client.get('/version')
    version.raise_for_status()
    prefix = '/v' + version.json()['ApiVersion']
    own = await client.get(f'{prefix}/containers/{os.environ["HOSTNAME"]}/json')
    own.raise_for_status()
    project = own.json()['Config']['Labels'].get('com.docker.compose.project')
    if not project:
        raise ValueError('Controller has no Compose project')
    result = await client.get(f'{prefix}/containers/json', params={
        'all': 'true', 'filters': json.dumps({'label': [f'com.docker.compose.project={project}']})})
    result.raise_for_status()
    # Revalidate labels even if the daemon ignored filters; exclude one-off jobs.
    rows = [row for row in result.json() if row.get('Labels', {}).get('com.docker.compose.project') == project
            and row.get('Labels', {}).get('com.docker.compose.oneoff', '').lower() != 'true']
    return prefix, rows


@app.get('/healthz')
async def health():
    return {'status': 'ok'}


@app.get('/controls', dependencies=[Depends(require_admin)])
async def controls():
    try:
        async with docker_client() as client:
            _, rows = await containers(client)
        present = {row['Labels'].get('com.docker.compose.service') for row in rows}
        return {'available': True, 'services': [name for name, service in SERVICES.items() if service in present],
                'operations': {name: {key: value for key, value in op.items() if key != 'monotonic'} for name, op in operations.items()}}
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(503, 'Container control unavailable')


async def perform_restart(name, actor):
    try:
        async with docker_client() as client:
            prefix, rows = await containers(client)
            targets = [row for row in rows if row['Labels'].get('com.docker.compose.service') == SERVICES[name]]
            if not targets:
                raise ValueError('Service container missing')
            for target in targets:
                response = await client.post(f'{prefix}/containers/{target["Id"]}/restart', params={'t': 10})
                response.raise_for_status()
        operations[name]['status'] = 'succeeded'
        logger.warning('service_restart actor=%s service=%s result=succeeded', actor, name)
    except (httpx.HTTPError, KeyError, ValueError):
        operations[name]['status'] = 'failed'
        logger.warning('service_restart actor=%s service=%s result=failed', actor, name)
    finally:
        operations[name]['finished_at'] = datetime.now(timezone.utc).isoformat()


@app.post('/services/{name}/restart', status_code=202)
async def restart(name: str, background: BackgroundTasks, context=Depends(require_admin)):
    if name not in SERVICES:
        raise HTTPException(404, 'Service is not restartable')
    async with lock:
        previous = operations.get(name)
        if previous and (previous['status'] == 'restarting' or time.monotonic() - previous['monotonic'] < 60):
            raise HTTPException(409, 'Restart in progress or cooling down')
        # Check the socket and target before acknowledging acceptance.
        try:
            async with docker_client() as client:
                _, rows = await containers(client)
            if not any(row['Labels'].get('com.docker.compose.service') == SERVICES[name] for row in rows):
                raise HTTPException(404, 'Service container missing')
        except (httpx.HTTPError, KeyError, ValueError):
            raise HTTPException(503, 'Container control unavailable')
        actor = context['user'].get('user_id') or context['user'].get('id')
        operations[name] = {'status': 'restarting', 'started_at': datetime.now(timezone.utc).isoformat(), 'monotonic': time.monotonic()}
        logger.warning('service_restart actor=%s service=%s result=accepted', actor, name)
        background.add_task(perform_restart, name, actor)
    return {'accepted': True, 'service': name}
