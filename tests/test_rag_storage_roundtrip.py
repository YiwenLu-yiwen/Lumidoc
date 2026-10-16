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
async def test_file_list_reads_the_workspace_subdirectory(tmp_path, monkeypatch):
    monkeypatch.setenv('RAG_DIR', str(tmp_path))
    adapter = RAGStorageAdapter('test', 'local')
    adapter._project_data_dir().mkdir(parents=True)
    (adapter._project_data_dir() / 'vdb_chunks.json').write_text(json.dumps({'data':[{'full_doc_id':'doc-1','file_path':'report.txt'}]}))
    service = Mock(_project_adapters={'test':adapter})
    monkeypatch.setattr(routes, 'get_enterprise_lightrag_service', AsyncMock(return_value=service))
    monkeypatch.setattr(routes, '_require_project_access', AsyncMock())
    result = await routes.get_rag_files('test', Mock())
    assert result['success']
    assert any(f['filename']=='report.txt' for f in result['files'])
