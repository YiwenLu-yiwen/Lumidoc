from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import FastAPI, Depends, Request, HTTPException
from src.modules.chat import authorization as auth

@pytest.mark.asyncio
async def test_chat_requires_ownership_and_rejects_forged_user(monkeypatch):
    monkeypatch.setattr(auth,'get_auth_context',AsyncMock(return_value={'auth_type':'user','user':{'user_id':'alice'}}))
    async def access(request,project_id,**kwargs):
        if project_id != 'alice-project':
            raise HTTPException(status_code=404,detail='Project not found')
    monkeypatch.setattr(auth,'require_project_access',access)
    app=FastAPI()
    @app.post('/chat',dependencies=[Depends(auth.authorize_chat_request)])
    async def chat(request:Request):
        return await request.json()
    @app.get('/history/{project_id}',dependencies=[Depends(auth.authorize_chat_request)])
    async def history(project_id:str):
        return {'secret':'own records'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get('/history/bob-project')).status_code==404
        assert (await client.get('/history/alice-project?user_id=bob')).status_code==403
        assert (await client.post('/chat',json={'project_id':'bob-project'})).status_code==404
        result=await client.post('/chat',json={'project_id':'alice-project'})
        assert result.status_code==200 and result.json()['user_id']=='alice'
        assert (await client.post('/chat',json={})).status_code==403

@pytest.mark.asyncio
async def test_repeated_ownership_reads_return_404_without_task_queue():
    from unittest.mock import Mock
    from src.modules.project.project_service import ProjectService
    service=ProjectService.__new__(ProjectService)
    service.db=Mock()
    service.db.query.return_value.filter.return_value.first.return_value=None
    for _ in range(3):
        with pytest.raises(HTTPException) as exc:
            await service.get_project('00000000-0000-0000-0000-000000000001',42)
        assert exc.value.status_code==404
    assert service.db.query.call_count==3

@pytest.mark.asyncio
async def test_project_parameter_cannot_unlock_global_maintenance(monkeypatch):
    monkeypatch.setattr(auth,'get_auth_context',AsyncMock(return_value={'auth_type':'user','user':{'user_id':'alice'}}))
    access=AsyncMock()
    monkeypatch.setattr(auth,'require_project_access',access)
    app=FastAPI()
    @app.post('/chat/migrate',dependencies=[Depends(auth.authorize_chat_request)])
    async def migrate():
        return {'success':True}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post('/chat/migrate?project_id=alice-project')
    assert response.status_code==403
    access.assert_not_awaited()

@pytest.mark.asyncio
async def test_owned_project_cannot_mask_another_users_history_id(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    import src.database
    monkeypatch.setattr(auth,'get_auth_context',AsyncMock(return_value={'auth_type':'user','user':{'user_id':'alice'}}))
    access=AsyncMock()
    monkeypatch.setattr(auth,'require_project_access',access)
    db=Mock()
    db.get.return_value=SimpleNamespace(user_id='bob',project_id='bob-project')
    def session():
        yield db
    monkeypatch.setattr(src.database,'get_db',session)
    app=FastAPI()
    @app.post('/chat',dependencies=[Depends(auth.authorize_chat_request)])
    async def chat():
        return {'secret':'should not be returned'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post('/chat',json={'project_id':'alice-project','chat_history_id':'bob-history'})
    assert response.status_code==404
    access.assert_not_awaited()
