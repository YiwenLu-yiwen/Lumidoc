"""验证文本提取结果可以继续完成文件登记，而非被误判为空内容。"""
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.modules.fileproc.services import file_processor
from src.shared import service_discovery

@pytest.mark.asyncio
async def test_text_processing_retains_content_for_registration(monkeypatch, tmp_path):
    processor = file_processor.FileProcessor.__new__(file_processor.FileProcessor)
    processor.queue = MagicMock(update_task_status=AsyncMock())
    processor.s3_client = MagicMock()
    processor.bucket_name = 'test'
    storage = MagicMock(save_file=AsyncMock(return_value='content/hash.txt'))
    monkeypatch.setattr(file_processor, 'get_storage', AsyncMock(return_value=storage))
    call = AsyncMock(return_value={'success': True})
    monkeypatch.setattr(file_processor, 'call_service', call)
    monkeypatch.setattr(service_discovery, 'call_service', call)
    monkeypatch.setenv('STORAGE_TYPE', 'local')
    path = tmp_path / 'sample.txt'
    path.write_text('Sydney is in Australia.')
    metadata = {'file_id': 'hash', 'project_id': '2011d7a1-fa0c-4805-b784-4636dbe94906'}
    result = await processor._get_processor_for_file_type('text/plain', str(path), metadata, 'task-1')
    assert await processor._register_file_to_service(metadata, result, 'task-1')
    registrations = [c.kwargs for c in call.call_args_list if c.kwargs['endpoint'] == 'api/file/register/content']
    assert len(registrations) == 1
    assert registrations[0]['json_data']['markdown_content'] == 'Sydney is in Australia.'
    statuses = [c.kwargs['json_data']['status'] for c in call.call_args_list if c.kwargs['endpoint'] == 'api/file/update/status']
    assert statuses == ['completed']
