"""Durable import status for the single-worker RAG deployment.

Browser requests enqueue work; they never own its lifetime. Interrupted jobs are
reported as retryable failures after a service restart instead of staying pending.
"""
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
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
        self.capacity = asyncio.Semaphore(1)

    def _path(self, project):
        return self.directory / (sha256(project.encode()).hexdigest() + '.json')

    def statuses(self, project):
        if project not in self.projects:
            path = self._path(project)
            records = json.loads(path.read_text()) if path.exists() else {}
            self.projects[project] = records
            for record in records.values():
                if record['status'] in ('pending', 'processing'):
                    record.update(status='failed', stage='interrupted',
                                  error='Service restarted during import; please retry.')
            if records:
                self._save(project)
        return self.projects[project]

    def _save(self, project):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(project)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.projects[project], ensure_ascii=False))
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
            if records.get(file_id, {}).get('status') in ('pending', 'processing', 'processed'):
                continue
            records[file_id] = dict(project_id=project, status='pending', stage='queued', file_name=file_id,
                                    created_at=created_at, batch_id=batch_id)
            accepted.append(file_id)
        self._save(project)
        for file_id in accepted:
            task = asyncio.create_task(self._run(project, file_id, worker))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
        return accepted

    async def _run(self, project, file_id, worker):
        try:
            async with self.capacity:
                started = perf_counter()
                self.update(project, file_id, status='processing', stage='reading',
                            started_at=datetime.now(timezone.utc).isoformat())
                await worker(file_id)
                self.update(project, file_id, status='processed', stage='completed',
                            duration_seconds=round(perf_counter() - started, 3))
                logger.info('rag_import_complete duration_ms=%d', (perf_counter() - started) * 1000)
        except asyncio.CancelledError:
            self.update(project, file_id, status='failed', stage='interrupted', error='Import interrupted; please retry.')
            raise
        except Exception as exc:
            logger.exception('RAG import failed')
            self.update(project, file_id, status='failed', stage='failed', error=str(exc))
