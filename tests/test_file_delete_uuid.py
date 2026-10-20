from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.modules.file.file_processor_service import FileProcessorService
from src.modules.file.routes import file_routes
from src.modules.file.config.database import FileServiceDatabase

@pytest.mark.asyncio
async def test_delete_uuid_project_preserves_other_projects(monkeypatch):
    project='2011d7a1-fa0c-4805-b784-4636dbe94906'
    conn=AsyncMock()
    conn.fetchrow.return_value={'id':17, 'path':'legacy-global.txt'}
    @asynccontextmanager
    async def transaction(): yield
    conn.transaction=MagicMock(side_effect=transaction)
    conn.fetchval.return_value=1
    class Pool:
        @asynccontextmanager
        async def acquire(self): yield conn
    monkeypatch.setattr(FileServiceDatabase,'get_pool',AsyncMock(return_value=Pool()))
    service=FileProcessorService.__new__(FileProcessorService)
    assert await service._delete_file_once('hash',project) is True
    deletion=conn.execute.call_args_list[0]
    assert deletion.args[1:] == (17,)
    assert conn.fetchrow.call_args.args[1:] == ('hash', project)
    assert 'project_id::text' in conn.fetchrow.call_args.args[0]
    assert len(conn.execute.call_args_list)==1

@pytest.mark.asyncio
async def test_delete_endpoint_reports_failures(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(file_routes.file_service,'delete_file',AsyncMock(side_effect=RuntimeError('database unavailable')))
    with pytest.raises(HTTPException) as error:
        await file_routes.delete_file('project','hash',MagicMock(headers={}))
    assert error.value.status_code==500
