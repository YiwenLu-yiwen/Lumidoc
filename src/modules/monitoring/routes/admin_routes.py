"""Operational metadata only: service probes and task lifecycle, never task inputs."""
import asyncio
import os
import time
from datetime import datetime, timezone
import httpx
import psutil
from fastapi import APIRouter, Depends, Request, HTTPException
from src.shared.project_access import require_admin
from src.shared.task_manager import get_task_manager
from src.shared.service_discovery import get_service_url

router = APIRouter(prefix='/admin', dependencies=[Depends(require_admin)])

@router.get('/status')
async def status(request: Request):
    authorization = request.headers.get("authorization", "")
    names = ['auth', 'project', 'file', 'fileproc', 'rag', 'chat', 'llm', 'graph', 'question', 'monitoring']
    async with httpx.AsyncClient(timeout=3) as client:
        async def probe(name):
            target = os.getenv(f'{name.upper()}_SERVICE_URL') or await get_service_url(name, healthy_only=False)
            if not target:
                return {'name': name, 'status': 'not_configured', 'latency_ms': None}
            started = time.perf_counter()
            try:
                response = await client.get(target.rstrip('/') + '/healthz')
                return {'name': name, 'status': 'healthy' if response.status_code == 200 else 'unhealthy', 'latency_ms': round((time.perf_counter()-started)*1000)}
            except httpx.HTTPError:
                return {'name': name, 'status': 'unreachable', 'latency_ms': None}
        services = await asyncio.gather(*(probe(name) for name in names))
        controls = {'available': False, 'services': [], 'operations': {}}
        control_url = os.getenv('CONTAINER_CONTROL_URL')
        if control_url:
            try:
                result = await client.get(control_url + '/controls', headers={'Authorization': authorization})
                result.raise_for_status()
                controls = result.json()
            except (httpx.HTTPError, ValueError):
                pass
        models = None
        try:
            target = await get_service_url('llm', healthy_only=False)
            if target:
                response = await client.get(target.rstrip('/') + '/api/v1/llm/admin/runtime', headers={'Authorization': authorization})
                response.raise_for_status()
                models = response.json().get('models')
        except (httpx.HTTPError, ValueError):
            pass
    return {'controls': controls, 'services': services, 'models': models, 'resources': {'scope': 'monitoring container', 'cpu_percent': psutil.cpu_percent(), 'memory_percent': psutil.virtual_memory().percent}, 'checked_at': datetime.now(timezone.utc).isoformat()}

@router.get('/tasks')
async def tasks():
    manager = await get_task_manager()
    records = await manager.get_active_tasks()
    # Exclude params/results/errors: they may contain credentials or document text.
    fields = ('task_id', 'task_name', 'status', 'created_at', 'updated_at', 'started_at', 'completed_at', 'retry_count')
    rows = [{key: task.get(key) for key in fields} for task in records]
    rows.sort(key=lambda row: str(row.get('updated_at') or row.get('created_at') or ''), reverse=True)
    return {'tasks': rows[:200], 'total': len(rows)}


@router.post('/services/{name}/restart', status_code=202)
async def restart_service(name: str, request: Request):
    from src.modules.monitoring.services.container_control import SERVICES
    if name not in SERVICES:
        raise HTTPException(404, 'Service is not restartable')
    target = os.getenv('CONTAINER_CONTROL_URL')
    if not target:
        raise HTTPException(503, 'Container control unavailable')
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f'{target}/services/{name}/restart', headers={'Authorization': request.headers.get('authorization', '')})
        if response.status_code != 202:
            raise HTTPException(response.status_code if response.status_code in (401, 403, 404, 409) else 503, 'Restart unavailable or cooling down')
        return response.json()
    except httpx.HTTPError:
        raise HTTPException(503, 'Container control unavailable')
