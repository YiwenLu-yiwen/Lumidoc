"""Administrative queue metadata; keep document payloads inside fileproc."""
import json
from fastapi import APIRouter, Depends
from src.shared.project_access import require_admin
from ..services.queue_service import file_processing_queue

router = APIRouter(prefix='/admin', dependencies=[Depends(require_admin)])

@router.get('/tasks')
async def admin_tasks():
    queue = file_processing_queue
    if not await queue._ensure_connection():
        from fastapi import HTTPException
        raise HTTPException(503, 'Processing queue unavailable')
    rows = []
    async for key in queue._redis.scan_iter(match=f'{queue._status_prefix}*', count=100):
        raw = await queue._redis.get(key)
        if not raw:
            continue
        task = json.loads(raw)
        fields = ('task_id', 'status', 'created_at', 'started_at', 'finished_at', 'processing_time_seconds')
        rows.append({field: task.get(field) for field in fields})
        if len(rows) >= 500:
            break
    rows.sort(key=lambda row: row.get('created_at') or '', reverse=True)
    return {'tasks': rows[:200], 'sampled': len(rows), 'stats': await queue.get_queue_stats()}
