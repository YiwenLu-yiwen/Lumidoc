"""Durable import status for the single-worker RAG deployment.

Browser requests enqueue work; they never own its lifetime. Interrupted jobs are
resumed after a service restart, with bounded retries and persisted attempts.
"""
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import logging
from pathlib import Path
from time import perf_counter
from statistics import median
from uuid import uuid4
import math

logger = logging.getLogger(__name__)


class ImportJobs:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.projects = {}
        self.tasks = set()
        self.active = set()
        self.retry_delay = 2
        self.capacity = asyncio.Semaphore(1)

    def _path(self, project):
        return self.directory / (sha256(project.encode()).hexdigest() + '.json')

    def statuses(self, project):
        if project not in self.projects:
            path = self._path(project)
            records = json.loads(path.read_text()) if path.exists() else {}
            self.projects[project] = records
        return self.projects[project]

    def _save(self, project):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(project)
        temporary = path.with_suffix('.tmp')
        with temporary.open('w') as stream:
            stream.write(json.dumps(self.projects[project], ensure_ascii=False))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)

    def update(self, project, file_id, **values):
        self.statuses(project)[file_id].update(values, updated_at=datetime.now(timezone.utc).isoformat())
        self._save(project)

    def progress(self, project, now=None):
        """File-count progress with a deliberately approximate, project-local ETA."""
        records = list(self.statuses(project).values())
        batches = [row for row in records if row.get('batch_id')]
        if not batches:
            return None
        newest = max(batches, key=lambda row: row['created_at'])
        batch = [row for row in batches if row['batch_id'] == newest['batch_id']]
        succeeded = sum(row['status'] == 'processed' for row in batch)
        failed = sum(row['status'] == 'failed' for row in batch)
        finished = succeeded + failed
        remaining = len(batch) - finished
        active = next((row for row in batch if row['status'] == 'processing'), None)
        now = now or datetime.now(timezone.utc)
        samples = [row['duration_seconds'] for row in sorted(records, key=lambda row: row.get('updated_at', row.get('created_at', '')))[-20:]
                   if row['status'] == 'processed' and isinstance(row.get('duration_seconds'), (int, float)) and row['duration_seconds'] > 0]
        estimate = None
        # A pending batch may be queued behind other work. Do not guess that wait.
        if remaining and active and active.get('started_at') and len(samples) >= 2:
            typical = median(samples)
            elapsed = max(0, (now - datetime.fromisoformat(active['started_at'])).total_seconds())
            # A slow OCR/model call invalidates the previous rate rather than reaching zero early.
            if elapsed < typical * 2:
                estimate = {'low': max(1, math.ceil(typical * .5 * remaining - elapsed)),
                            'high': max(1, math.ceil(typical * 2 * remaining - elapsed))}
        end = now if remaining else max(datetime.fromisoformat(row.get('updated_at', row['created_at'])) for row in batch)
        return {'batch_id': newest['batch_id'], 'total': len(batch), 'finished': finished,
                'succeeded': succeeded, 'failed': failed,
                'percent': math.floor(finished * 100 / len(batch)),
                'stage': active.get('stage') if active else ('queued' if remaining else 'completed'),
                'active_file': active.get('file_name') if active else None,
                'estimated_remaining_seconds': estimate,
                'elapsed_seconds': round(max(0, (end - datetime.fromisoformat(newest['created_at'])).total_seconds()))}

    def remove(self, project, file_id, doc_id=None):
        records = self.statuses(project)
        for identifier in list(records):
            if identifier == file_id or (doc_id and records[identifier].get('doc_id') == doc_id):
                del records[identifier]
        self._save(project)

    def enqueue(self, project, file_ids, worker):
        records = self.statuses(project)
        accepted = []
        batch_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        for file_id in dict.fromkeys(file_ids):
            if records.get(file_id, {}).get('status') in ('pending', 'processing', 'recovering', 'processed'):
                continue
            records[file_id] = dict(project_id=project, status='pending', stage='queued', file_name=file_id,
                                    created_at=created_at, batch_id=batch_id)
            accepted.append(file_id)
        self._save(project)
        for file_id in accepted:
            self.schedule(project, file_id, worker)
        return accepted

    def schedule(self, project, file_id, worker):
        key = (project, file_id)
        if key in self.active: return
        self.active.add(key)
        task = asyncio.create_task(self._run(project, file_id, worker))
        self.tasks.add(task)
        def finished(task):
            self.tasks.discard(task)
            self.active.discard(key)
        task.add_done_callback(finished)

    def recover(self, worker):
        for path in self.directory.glob('*.json'):
            records = json.loads(path.read_text())
            for file_id, record in records.items():
                project = record.get('project_id')
                if project and record['status'] in ('pending', 'processing', 'recovering'):
                    self.statuses(project)
                    self.update(project, file_id, status='pending', stage='recovering')
                    from src.shared.operation_journal import journal
                    journal().event('task.interrupted', 'rag', 'recovering', operation_id=f'{project}/{file_id}')
                    self.schedule(project, file_id, lambda identifier, project=project: worker(project, identifier))

    async def _run(self, project, file_id, worker):
        from src.shared.operation_journal import journal
        while True:
            record = self.statuses(project)[file_id]
            attempts = record.get('attempts', 0)
            if attempts >= 5:
                self.update(project, file_id, status='failed', stage='failed', error='Automatic recovery limit reached')
                journal().event('task.recovery_exhausted', 'rag', 'needs_attention', operation_id=f'{project}/{file_id}')
                return
            try:
                async with self.capacity:
                    started = perf_counter()
                    self.update(project, file_id, status='processing', stage='reading', attempts=attempts+1,
                                started_at=datetime.now(timezone.utc).isoformat())
                    await worker(file_id)
                    self.update(project, file_id, status='processed', stage='completed', error=None,
                                duration_seconds=round(perf_counter()-started, 3))
                return
            except asyncio.CancelledError:
                self.update(project, file_id, status='pending', stage='recovering')
                raise
            except Exception:
                self.update(project, file_id, status='pending', stage='recovering')
                journal().event('task.retry', 'rag', 'recovering', operation_id=f'{project}/{file_id}')
                await asyncio.sleep(min(self.retry_delay**(attempts+1), 30))
