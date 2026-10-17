from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import FastAPI, HTTPException
from src.modules.auth.admin_api import account_router
from src.shared import project_access

@pytest.mark.asyncio
@pytest.mark.parametrize('context', [
    {'auth_type':'service'},
    {'auth_type':'user','user':{'is_active':True,'is_superuser':False}},
    {'auth_type':'user','user':{'is_active':False,'is_superuser':True}},
])
async def test_shared_admin_check_rejects_unprivileged_context(monkeypatch, context):
    monkeypatch.setattr(project_access,'get_auth_context',AsyncMock(return_value=context))
    with pytest.raises(HTTPException) as error:
        await project_access.require_admin(None)
    assert error.value.status_code == 403

@pytest.mark.asyncio
async def test_user_management_cannot_use_client_role_or_edit_self():
    user=SimpleNamespace(id=1,username='admin',is_active=True,is_superuser=False)
    async def current():return user
    service=SimpleNamespace(db_pool=None,_init_db_pool=AsyncMock())
    app=FastAPI();app.include_router(account_router(service,current))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get('/api/admin/users',headers={'X-Role':'admin'})).status_code==403
        assert (await client.patch('/api/admin/users/2',json={'is_active':False,'is_superuser':True})).status_code==403
        user.is_superuser=True
        assert (await client.patch('/api/admin/users/1',json={'is_active':False,'is_superuser':False})).status_code==409
        service._init_db_pool.assert_not_awaited()

@pytest.mark.asyncio
async def test_account_update_requires_current_password():
    user=SimpleNamespace(id=1,username='someone')
    async def current():return user
    service=SimpleNamespace(authenticate_user=AsyncMock(return_value=None),_init_db_pool=AsyncMock())
    app=FastAPI();app.include_router(account_router(service,current))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        response=await client.patch('/api/users/me/',json={'email':'new@example.com','nickname':'Test','current_password':'incorrect'})
        assert response.status_code==403
        service._init_db_pool.assert_not_awaited()

@pytest.mark.asyncio
async def test_admin_import_retry_only_requeues_failed_records(monkeypatch, tmp_path):
    from src.modules.lightraglocal.routes import enterprise_rag_routes as routes
    from src.modules.lightraglocal.services.import_jobs import ImportJobs
    jobs=ImportJobs(tmp_path)
    jobs.projects['p']={'failed-file':{'status':'failed'},'active-file':{'status':'processing'}}
    service=SimpleNamespace(import_jobs=jobs)
    monkeypatch.setattr(project_access,'require_admin',AsyncMock(return_value={'user':{'user_id':'admin'}}))
    monkeypatch.setattr(routes,'get_enterprise_lightrag_service',AsyncMock(return_value=service))
    build=AsyncMock(return_value={'success':True})
    monkeypatch.setattr(routes,'build_rag',build)
    with pytest.raises(HTTPException) as error:
        await routes.admin_retry_import('p','active-file',None)
    assert error.value.status_code==409
    build.assert_not_awaited()
    await routes.admin_retry_import('p','failed-file',None)
    build.assert_awaited_once_with('p',['failed-file'],http_request=None)
