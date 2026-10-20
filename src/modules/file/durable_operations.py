"""Persist upload bytes and deletion intents before performing side effects."""
import io
import os
from pathlib import Path
from uuid import uuid4, UUID
from hashlib import sha256
from starlette.datastructures import UploadFile, Headers
from fastapi import HTTPException
from src.shared.operation_journal import journal
from src.shared.durable_worker import DurableWorker


async def execute(payload, identifier):
    from .file_processor_service import FileProcessorService
    service = FileProcessorService()
    if payload['kind'] == 'batch_delete':
        for file_hash in payload['file_hashes']:
            await service._delete_file_once(file_hash, payload['project_id'])
        return {'success': True, 'message': 'Files deleted', 'deleted': payload['file_hashes'], 'failed': []}
    if payload['kind'] == 'delete':
        return await service._delete_file_once(payload['file_hash'], payload['project_id'])
    upload = UploadFile(io.BytesIO(Path(payload['path']).read_bytes()), filename=payload['filename'],
                        headers=Headers({'content-type': payload['content_type']}))
    result = await service._upload_file_once(upload, payload['project_id'], payload['process'])
    if not result.success: raise RuntimeError('Upload commit interrupted')
    return result.model_dump(mode='json')


def cleanup(payload):
    if payload['kind'] == 'upload': Path(payload['path']).unlink(missing_ok=True)


worker = DurableWorker('file.operations', execute, cleanup)


def start():
    with journal().connection() as db:
        rows = db.execute("SELECT payload FROM work WHERE lane='file.operations' AND status='completed'").fetchall()
    import json
    for row in rows: cleanup(json.loads(row['payload']))
    worker.start()


def operation_id(project, supplied, kind):
    try:
        token = str(UUID(supplied)) if supplied else str(uuid4())
    except ValueError as exc:
        raise HTTPException(400, 'X-Operation-Id must be a UUID') from exc
    return sha256(f'{kind}:{project}:{token}'.encode()).hexdigest()


async def upload(file, project_id, process, supplied=None):
    identifier = operation_id(project_id, supplied, 'upload')
    if journal().work(identifier): return await worker.wait(identifier)
    content = await file.read()
    directory = Path(journal().path).parent / 'upload_staging'
    directory.mkdir(exist_ok=True)
    path = directory / identifier
    with path.open('wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    journal().enqueue('file.operations', {'kind':'upload', 'path':str(path), 'filename':file.filename,
                      'content_type':file.content_type or 'application/octet-stream', 'project_id':project_id, 'process':process}, identifier)
    return await worker.wait(identifier)


async def delete(file_hash, project_id, supplied=None):
    identifier = journal().enqueue('file.operations', {'kind':'delete','file_hash':file_hash,'project_id':project_id}, operation_id(project_id, supplied, 'delete'))
    return await worker.wait(identifier)


async def batch_delete(file_hashes, project_id):
    identifier = journal().enqueue('file.operations', {'kind': 'batch_delete',
        'file_hashes': list(dict.fromkeys(file_hashes)), 'project_id': str(project_id)})
    return await worker.wait(identifier)
