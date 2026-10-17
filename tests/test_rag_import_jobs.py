import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from src.modules.lightraglocal.services.import_jobs import ImportJobs


@pytest.mark.asyncio
async def test_enqueue_returns_before_work_finishes_and_deduplicates(tmp_path):
    release = asyncio.Event()
    async def worker(file_id):
        await release.wait()
    jobs = ImportJobs(tmp_path)
    assert jobs.enqueue('p', ['a', 'a'], worker) == ['a']
    assert jobs.statuses('p')['a']['status'] == 'pending'
    assert jobs.enqueue('p', ['a'], worker) == []
    await asyncio.sleep(0)
    assert jobs.statuses('p')['a']['status'] == 'processing'
    release.set()
    await asyncio.gather(*jobs.tasks)
    assert jobs.statuses('p')['a']['status'] == 'processed'
    assert ImportJobs(tmp_path).statuses('p')['a']['status'] == 'processed'


@pytest.mark.asyncio
async def test_failure_is_retryable_and_restart_is_not_forever_pending(tmp_path):
    jobs = ImportJobs(tmp_path)
    async def broken(file_id):
        raise RuntimeError('No extracted text')
    jobs.enqueue('p', ['a'], broken)
    await asyncio.gather(*jobs.tasks)
    assert jobs.statuses('p')['a']['status'] == 'failed'
    assert jobs.enqueue('p', ['a'], broken) == ['a']
    assert ImportJobs(tmp_path).statuses('p')['a']['stage'] == 'interrupted'
    await asyncio.gather(*jobs.tasks)


@pytest.mark.asyncio
async def test_status_merges_document_and_job_without_duplicates(tmp_path, monkeypatch):
    from src.modules.lightraglocal.routes import enterprise_rag_routes as routes
    from lightrag.base import DocStatus
    doc = SimpleNamespace(file_path='report.txt', chunks_count=2, created_at='', updated_at='', error=None)
    async def documents(state):
        return {'doc-1': doc} if state == DocStatus.PROCESSED else {}
    rag = SimpleNamespace(doc_status=SimpleNamespace(get_docs_by_status=documents))
    jobs = ImportJobs(tmp_path)
    jobs.projects['p'] = {'file-hash': {'doc_id': 'doc-1', 'file_name': 'report.txt', 'status': 'processed'}}
    service = SimpleNamespace(import_jobs=jobs, _get_project_rag=AsyncMock(return_value=rag))
    statuses = await routes._document_statuses(service, 'p')
    assert list(statuses) == ['file-hash']
    assert statuses['file-hash']['chunks_count'] == 2


@pytest.mark.asyncio
async def test_build_accepts_work_without_waiting_for_model(tmp_path, monkeypatch):
    from src.modules.lightraglocal.routes import enterprise_rag_routes as routes
    release = asyncio.Event()
    async def insert(**kwargs):
        await release.wait()
        return {'success': True, 'doc_id': 'doc-1'}
    service = SimpleNamespace(import_jobs=ImportJobs(tmp_path), insert_document=insert)
    monkeypatch.setattr(routes, 'get_enterprise_lightrag_service', AsyncMock(return_value=service))
    monkeypatch.setattr(routes, '_require_project_access', AsyncMock())
    monkeypatch.setattr(routes, 'wait_for_file_processing', AsyncMock())
    monkeypatch.setattr(routes, 'get_file_name_from_service', AsyncMock(return_value='report.txt'))
    monkeypatch.setattr(routes, 'get_file_content_from_service', AsyncMock(return_value='Report content'))
    result = await asyncio.wait_for(routes.build_rag('p', ['file'], object()), 0.2)
    assert result['status'] == 'accepted'
    await asyncio.sleep(0)
    assert service.import_jobs.statuses('p')['file']['stage'] == 'indexing'
    release.set()
    await asyncio.gather(*service.import_jobs.tasks)


@pytest.mark.asyncio
async def test_insert_does_not_report_success_when_lightrag_persists_failure():
    from src.modules.lightraglocal.services.enterprise_lightrag_service import EnterpriseLightRAGService
    rag = SimpleNamespace(ainsert=AsyncMock(), doc_status=SimpleNamespace(
        get_by_id=AsyncMock(return_value={'status': 'failed', 'error': 'Embedding unavailable'})))
    service = EnterpriseLightRAGService.__new__(EnterpriseLightRAGService)
    service._get_project_rag = AsyncMock(return_value=rag)
    result = await service.insert_document('p', 'Test document')
    assert result['success'] is False
    assert 'Embedding unavailable' in result['error']


@pytest.mark.asyncio
async def test_import_waits_for_extraction_and_reports_stage(tmp_path, monkeypatch):
    from src.modules.lightraglocal.routes import enterprise_rag_routes as routes
    from src.shared.service_client import ServiceClient
    call = AsyncMock(side_effect=[{'success':True,'status':'processing'}, {'success':True,'status':'completed'}])
    monkeypatch.setattr(ServiceClient, 'call_service', call)
    sleep = AsyncMock()
    monkeypatch.setattr(routes.asyncio, 'sleep', sleep)
    jobs = ImportJobs(tmp_path)
    jobs.projects['p'] = {'file': {'status':'processing'}}
    await routes.wait_for_file_processing('p', 'file', jobs)
    assert jobs.statuses('p')['file']['stage'] == 'waiting_extraction'
    assert call.await_count == 2
    sleep.assert_awaited_once_with(2)


@pytest.mark.asyncio
async def test_text_pdf_skips_model_rewriting_even_when_headers_repeat(monkeypatch):
    from src.modules.fileproc.processors.llm_post_processor import LLMPostProcessor
    monkeypatch.setenv('ENABLE_LLM_POST_PROCESSING', 'true')
    monkeypatch.delenv('LLM_POST_PROCESS_TEXT_PDF', raising=False)
    processor = LLMPostProcessor()
    processor._llm_process_content = AsyncMock(side_effect=AssertionError('Unnecessary model call'))
    content = 'Repeated header\nDetails\n' * 10
    result = await processor.process_content(content, {'processor':'local_pdf','ocr_enabled':False})
    assert result['content'] == content
    assert result['processed'] is False
    processor._llm_process_content.assert_not_called()

@pytest.mark.asyncio
@pytest.mark.parametrize('success', [True, False])
async def test_delete_updates_index_before_removing_durable_import_status(tmp_path, monkeypatch, success):
    from fastapi import HTTPException
    from src.modules.lightraglocal.routes import enterprise_rag_routes as routes
    jobs = ImportJobs(tmp_path)
    jobs.projects['p'] = {'file': {'doc_id':'doc-1','status':'processed','file_name':'test.txt'}}
    service = SimpleNamespace(import_jobs=jobs, delete_document=AsyncMock(return_value={'success':success,'error':'failed'}))
    monkeypatch.setattr(routes,'_require_project_access',AsyncMock())
    monkeypatch.setattr(routes,'get_enterprise_lightrag_service',AsyncMock(return_value=service))
    monkeypatch.setattr(routes,'_document_statuses',AsyncMock(return_value=jobs.statuses('p')))
    if success:
        assert (await routes.delete_rag_file('p','file',object()))['success']
        assert ImportJobs(tmp_path).statuses('p')=={}
    else:
        with pytest.raises(HTTPException):
            await routes.delete_rag_file('p','file',object())
        assert 'file' in jobs.statuses('p')
    service.delete_document.assert_awaited_once_with('p','doc-1')

@pytest.mark.asyncio
async def test_batch_delete_deduplicates_reports_partial_failure_and_authorizes_first(monkeypatch):
    from fastapi import HTTPException
    from src.modules.lightraglocal.routes import enterprise_rag_routes as routes
    service=object()
    monkeypatch.setattr(routes,'_require_project_access',AsyncMock())
    monkeypatch.setattr(routes,'get_enterprise_lightrag_service',AsyncMock(return_value=service))
    delete=AsyncMock(side_effect=[{'success':True,'file_id':'a'},HTTPException(status_code=404,detail='Missing')])
    monkeypatch.setattr(routes,'_delete_rag_file',delete)
    result=await routes.delete_rag_files('p',object(),['a','a','missing'])
    assert result['success'] is False and len(result['results'])==2
    assert result['results'][1]['status_code']==404
    assert delete.await_count==2
    routes._require_project_access.side_effect=HTTPException(status_code=404)
    with pytest.raises(HTTPException):
        await routes.delete_rag_files('other-project',object(),['a'])
    assert delete.await_count==2


def test_progress_counts_failures_and_uses_project_local_eta(tmp_path):
    from datetime import datetime, timezone, timedelta
    jobs = ImportJobs(tmp_path)
    now = datetime(2026, 10, 18, tzinfo=timezone.utc)
    stamp = (now - timedelta(seconds=1)).isoformat()
    jobs.projects['p'] = {
        'old1': dict(status='processed', duration_seconds=10, created_at=stamp),
        'old2': dict(status='processed', duration_seconds=10, created_at=stamp),
        'a': dict(status='processed', batch_id='new', created_at=stamp),
        'b': dict(status='failed', batch_id='new', created_at=stamp),
        'c': dict(status='processing', stage='indexing', batch_id='new', created_at=stamp, started_at=stamp),
        'd': dict(status='pending', batch_id='new', created_at=stamp),
    }
    progress = jobs.progress('p', now)
    assert (progress['finished'], progress['total'], progress['percent']) == (2, 4, 50)
    assert (progress['succeeded'], progress['failed']) == (1, 1)
    assert progress['estimated_remaining_seconds'] == {'low': 9, 'high': 39}
    assert jobs.progress('other', now) is None
    assert jobs.progress('p', now + timedelta(seconds=30))['estimated_remaining_seconds'] is None
    jobs.projects['p']['c']['status'] = 'pending'
    assert jobs.progress('p', now)['estimated_remaining_seconds'] is None


def test_progress_without_samples_does_not_invent_eta(tmp_path):
    from datetime import datetime, timezone
    jobs = ImportJobs(tmp_path)
    stamp = datetime.now(timezone.utc).isoformat()
    jobs.projects['p'] = {'a': dict(status='processing', batch_id='batch', created_at=stamp, started_at=stamp)}
    assert jobs.progress('p')['estimated_remaining_seconds'] is None
    jobs.projects['p']['a'].update(status='processed', updated_at=stamp)
    jobs._save('p')
    assert ImportJobs(tmp_path).progress('p')['percent'] == 100
