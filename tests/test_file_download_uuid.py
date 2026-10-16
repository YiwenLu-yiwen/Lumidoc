"""UUID 项目中的文件内容与下载回归测试。"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
import pytest
from src.modules.file.routes import file_routes

PROJECT_ID = '2011d7a1-fa0c-4805-b784-4636dbe94906'

@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['download', 'content'])
async def test_file_routes_accept_uuid_projects(monkeypatch, tmp_path, operation):
    path = tmp_path / 'example.txt'
    path.write_text('document content')
    record = {'path': str(path), 'name': 'example.txt', 'file_hash': 'hash', 'type': 'text/plain'}
    connection = AsyncMock()
    connection.fetchrow.side_effect = [record, {'markdown_content': 'document content', 'metadata': None}]
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield connection
    monkeypatch.setattr(file_routes.FileServiceDatabase, 'get_pool', AsyncMock(return_value=Pool()))
    monkeypatch.setenv('STORAGE_TYPE', 'local')
    if operation == 'download':
        response = await file_routes.download_file(PROJECT_ID, 'example.txt', download=True)
        assert response.status_code == 200
        assert b'document content' == b''.join([chunk.encode() if isinstance(chunk, str) else chunk async for chunk in response.body_iterator])
    else:
        response = await file_routes.get_file_content(PROJECT_ID, 'example.txt')
        assert response['content'] == 'document content'
    assert str(connection.fetchrow.call_args_list[0].args[1]) == PROJECT_ID

@pytest.mark.asyncio
async def test_processed_preview_never_falls_back_to_original_binary(monkeypatch, tmp_path):
    from fastapi import HTTPException
    path = tmp_path / 'scan.pdf'
    path.write_bytes(b'%PDF-original scan')
    connection = AsyncMock()
    connection.fetchrow.side_effect = [{'path':str(path),'name':'scan.pdf','file_hash':'hash','type':'application/pdf'}, None]
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield connection
    monkeypatch.setattr(file_routes.FileServiceDatabase, 'get_pool', AsyncMock(return_value=Pool()))
    monkeypatch.setenv('STORAGE_TYPE', 'local')
    with pytest.raises(HTTPException) as error:
        await file_routes.get_file_content(PROJECT_ID, 'hash', processed_only=True)
    assert error.value.status_code == 409
