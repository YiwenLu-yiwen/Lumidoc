"""S3 的读写使用同一相对路径，服务重启后仍能恢复项目索引。"""
import json
from unittest.mock import AsyncMock, Mock
import pytest
from src.modules.lightraglocal.storage.rag_storage_adapter import RAGStorageAdapter
from src.modules.lightraglocal.routes import enterprise_rag_routes as routes

class MemoryStorage:
    def __init__(self):
        self.objects = {}
    async def save_file(self, key, data):
        self.objects[key] = data
    async def get_file(self, key):
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key]

@pytest.mark.asyncio
async def test_indexes_survive_a_fresh_local_cache(tmp_path, monkeypatch):
    storage = MemoryStorage()
    monkeypatch.setenv('RAG_CACHE_DIR', str(tmp_path / 'first'))
    first = RAGStorageAdapter('test', 's3')
    first.storage = storage
    first._project_data_dir().mkdir(parents=True)
    payload = {'data':[{'__id__':'chunk-1','full_doc_id':'doc-1','content':'Saved content'}]}
    (first._project_data_dir() / 'vdb_chunks.json').write_text(json.dumps(payload))
    await first.sync_to_s3()
    monkeypatch.setenv('RAG_CACHE_DIR', str(tmp_path / 'second'))
    restored = RAGStorageAdapter('test', 's3')
    restored.storage = storage
    await restored.sync_from_s3()
    assert json.loads((restored._project_data_dir() / 'vdb_chunks.json').read_text()) == payload

@pytest.mark.asyncio
async def test_file_list_uses_document_status_not_vector_files(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from lightrag.base import DocStatus
    doc = SimpleNamespace(file_path='report.txt', chunks_count=1,
                          created_at='', updated_at='', error=None)
    async def get_docs(state):
        return {'doc-1':doc} if state == DocStatus.PROCESSED else {}
    rag = SimpleNamespace(doc_status=SimpleNamespace(get_docs_by_status=get_docs))
    service = SimpleNamespace(base_storage_dir=str(tmp_path), _get_project_rag=AsyncMock(return_value=rag))
    monkeypatch.setenv('RAG_DIR', str(tmp_path))
    monkeypatch.setattr(routes, 'get_enterprise_lightrag_service', AsyncMock(return_value=service))
    monkeypatch.setattr(routes, '_require_project_access', AsyncMock())
    result = await routes.get_rag_files('test', Mock())
    assert result['success']
    assert result['files'][0]['filename'] == 'report.txt'
    assert result['files'][0]['status'] == 'processed'

@pytest.mark.asyncio
async def test_strict_sync_propagates_failure_for_deletion(tmp_path, monkeypatch):
    monkeypatch.setenv('RAG_CACHE_DIR', str(tmp_path))
    adapter = RAGStorageAdapter('strict-delete', 's3')
    adapter.storage = Mock(save_file=AsyncMock(side_effect=RuntimeError('storage unavailable')))
    adapter._project_data_dir().mkdir(parents=True, exist_ok=True)
    (adapter._project_data_dir() / 'kv_store_doc_status.json').write_text('{}')
    with pytest.raises(RuntimeError, match='storage unavailable'):
        await adapter.sync_to_s3(strict=True)
