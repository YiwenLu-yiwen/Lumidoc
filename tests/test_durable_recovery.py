import json
import time
from unittest.mock import AsyncMock
import pytest
import httpx
from src.shared import operation_journal as operations
from src.modules.monitoring.services import recovery_supervisor as supervisor

@pytest.fixture
def ledger(tmp_path, monkeypatch):
    store = operations.OperationJournal(tmp_path / 'operations.db')
    monkeypatch.setattr(operations, '_journal', store)
    return store


def test_work_survives_reopen_reclaims_expired_owner_and_fences_old_completion(ledger):
    identifier = ledger.enqueue('test', {'project': 'a'}, 'same-request')
    ledger.enqueue('test', {'project':'b'}, 'same-request')
    first = ledger.claim('test','old')
    assert first['payload']['project'] == 'a'
    assert ledger.claim('test','new') is None
    with ledger.connection() as db: db.execute('UPDATE work SET updated=? WHERE id=?',(time.time()-100,identifier))
    reopened = operations.OperationJournal(ledger.path)
    recovered = reopened.claim('test','new')
    assert recovered['id'] == identifier and recovered['attempts'] == 2
    assert ledger.finish(identifier,'old',{}) == 0
    assert reopened.finish(identifier,'new',{'ok':True}) == 1
    assert reopened.work(identifier)['result'] == {'ok':True}
    assert any(event['action']=='task.interrupted' for event in reopened.events())


def test_cancelled_work_is_never_revived_by_a_late_retry(ledger):
    identifier=ledger.enqueue('test',{})
    ledger.claim('test','worker')
    ledger.cancel(identifier)
    ledger.retry(identifier,'worker',1)
    assert ledger.work(identifier)['status']=='cancelled'
    assert ledger.claim('test','worker') is None


def test_restart_budget_survives_controller_restart_and_stops_a_restart_loop(ledger, monkeypatch):
    for now in (1000,1061,1122):
        assert not supervisor.decide('chat','exited',now)[0]
        assert supervisor.decide('chat','exited',now+1)[0]
    monkeypatch.setattr(operations,'_journal',operations.OperationJournal(ledger.path))
    supervisor.decide('chat','unhealthy',1184)
    restart,state=supervisor.decide('chat','unhealthy',1185)
    assert not restart and state['blocked']
    assert state['phase']=='needs_attention'
    assert not supervisor.decide('chat','exited',3000)[0]
    assert sum(event['action']=='service.interrupted' for event in ledger.events())==3


def test_short_health_blips_do_not_reset_budget_but_sustained_health_does(ledger):
    supervisor.decide('fileproc','exited',1000)
    supervisor.decide('fileproc','exited',1001)
    assert supervisor.decide('fileproc','healthy',1002)[1]['restart_count']==1
    assert supervisor.decide('fileproc','healthy',1123)[1]['restart_count']==0


@pytest.mark.asyncio
async def test_audit_tracks_verified_actor_without_bodies_tokens_or_query_strings(ledger):
    from src.modules.gateway.middleware.audit import AuditMiddleware
    async def inner(scope, receive, send):
        scope.setdefault('state',{})['user']={'id':42}
        await send({'type':'http.response.start','status':200,'headers':[]})
        await send({'type':'http.response.body','body':b'{}'})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=AuditMiddleware(inner)),base_url='http://test') as client:
        response=await client.post('/api/file/upload/project?token=QUERY_SECRET',headers={'Authorization':'Bearer HEADER_SECRET'},json={'password':'BODY_SECRET'})
    events=ledger.events()
    assert events[0]['actor']=='42'
    assert events[0]['operation_id']==response.headers['x-operation-id']
    assert not any(secret in json.dumps(events) for secret in ('QUERY_SECRET','HEADER_SECRET','BODY_SECRET'))


@pytest.mark.asyncio
async def test_rag_import_resumes_after_process_replacement(ledger,tmp_path):
    from src.modules.lightraglocal.services.import_jobs import ImportJobs
    original=ImportJobs(tmp_path/'rag')
    original.projects['project']={'file':{'project_id':'project','status':'processing','attempts':1,'created_at':'2026-10-20T00:00:00+00:00'}}
    original._save('project')
    resumed=ImportJobs(tmp_path/'rag');work=AsyncMock()
    resumed.recover(work)
    import asyncio
    await asyncio.gather(*resumed.tasks)
    work.assert_awaited_once_with('project','file')
    assert resumed.statuses('project')['file']['status']=='processed'
    assert resumed.statuses('project')['file']['attempts']==2


@pytest.mark.asyncio
async def test_independent_jobs_can_run_concurrently_and_commit_once(ledger):
    import asyncio
    from src.shared.durable_worker import DurableWorker
    entered = set()
    ready = asyncio.Event()
    async def handle(payload, identifier):
        entered.add(identifier)
        if len(entered) == 2: ready.set()
        await asyncio.wait_for(ready.wait(), 3)
        return {'saved': payload['number']}
    ids = [ledger.enqueue('parallel', {'number': n}) for n in range(2)]
    worker = DurableWorker('parallel', handle, concurrency=2)
    try:
        result = await asyncio.wait_for(asyncio.gather(*(worker.wait(i) for i in ids)), 5)
        assert result == [{'saved': 0}, {'saved': 1}]
        assert all(ledger.work(i)['attempts'] == 1 for i in ids)
    finally:
        worker.task.cancel()
        await asyncio.gather(worker.task, return_exceptions=True)


def test_recovery_exhaustion_is_recorded_and_not_retried(ledger):
    identifier = ledger.enqueue('test', {})
    for attempt in range(1, 6):
        assert ledger.claim('test', 'worker')['attempts'] == attempt
        ledger.retry(identifier, 'worker', attempt)
        with ledger.connection() as db:
            db.execute('UPDATE work SET available=0 WHERE id=?', (identifier,))
    assert ledger.work(identifier)['status'] == 'failed'
    assert ledger.claim('test', 'worker') is None
    assert ledger.events()[0]['action'] == 'task.recovery_exhausted'

@pytest.mark.asyncio
async def test_batch_deletion_replays_entire_uuid_selection_after_interruption(monkeypatch):
    from types import SimpleNamespace
    from src.modules.file import file_processor_service as files
    from src.modules.file import durable_operations
    remaining = {'a', 'b'}
    fail_once = True
    async def remove(file_hash, project):
        nonlocal fail_once
        assert project == '2011d7a1-fa0c-4805-b784-4636dbe94906'
        if file_hash == 'b' and fail_once:
            fail_once = False
            raise ConnectionError('simulated storage interruption')
        remaining.discard(file_hash)
        return True
    monkeypatch.setattr(files, 'FileProcessorService', lambda: SimpleNamespace(_delete_file_once=remove))
    payload = {'kind': 'batch_delete', 'file_hashes': ['a', 'b'], 'project_id': '2011d7a1-fa0c-4805-b784-4636dbe94906'}
    with pytest.raises(ConnectionError):
        await durable_operations.execute(payload, 'operation')
    assert remaining == {'b'}
    result = await durable_operations.execute(payload, 'operation')
    assert not remaining and result['deleted'] == ['a', 'b'] and result['success']


@pytest.mark.asyncio
async def test_rag_batch_selection_is_durable_before_execution(ledger, monkeypatch):
    from types import SimpleNamespace
    from src.modules.lightraglocal.routes import enterprise_rag_routes as routes
    async def wait(identifier):
        row = ledger.work(identifier)
        assert row['lane'] == 'rag.batch_deletions'
        assert row['payload'] == {'project_id': 'project', 'file_ids': ['a', 'b']}
        return {'success': True}
    service = SimpleNamespace(batch_delete_worker=SimpleNamespace(wait=wait))
    monkeypatch.setattr(routes, '_require_project_access', AsyncMock())
    monkeypatch.setattr(routes, 'get_enterprise_lightrag_service', AsyncMock(return_value=service))
    assert (await routes.delete_rag_files('project', object(), ['a', 'b', 'a']))['success']
