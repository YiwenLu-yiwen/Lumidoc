from unittest.mock import AsyncMock
import httpx
import pytest
from src.modules.monitoring.services import container_control as control

@pytest.fixture(autouse=True)
def reset():
    control.operations.clear()
    control.app.dependency_overrides.clear()
    yield
    control.app.dependency_overrides.clear()

async def admin():
    return {'user': {'id': 7}}

@pytest.mark.asyncio
async def test_restart_rejects_ordinary_user_and_arbitrary_targets(monkeypatch):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=control.app), base_url='http://test') as client:
        assert (await client.post('/services/chat/restart')).status_code == 401
        control.app.dependency_overrides[control.require_admin] = admin
        for target in ['db', 'redis', 'container_control', 'unknown']:
            assert (await client.post(f'/services/{target}/restart')).status_code == 404

@pytest.mark.asyncio
async def test_restart_scopes_to_own_project_and_ignores_oneoff(monkeypatch):
    monkeypatch.setenv('HOSTNAME', 'controller')
    posts = []
    def handler(request):
        if request.url.path == '/version': return httpx.Response(200, json={'ApiVersion':'1.51'})
        if request.url.path.endswith('/controller/json'):
            return httpx.Response(200,json={'Config':{'Labels':{'com.docker.compose.project':'our-project'}}})
        if request.url.path.endswith('/containers/json'):
            return httpx.Response(200,json=[
                {'Id':'ours','Labels':{'com.docker.compose.project':'our-project','com.docker.compose.service':'chat_service'}},
                {'Id':'foreign','Labels':{'com.docker.compose.project':'other-project','com.docker.compose.service':'chat_service'}},
                {'Id':'oneoff','Labels':{'com.docker.compose.project':'our-project','com.docker.compose.service':'chat_service','com.docker.compose.oneoff':'True'}},
            ])
        posts.append(request.url.path)
        return httpx.Response(204)
    monkeypatch.setattr(control,'docker_client',lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler),base_url='http://docker'))
    control.app.dependency_overrides[control.require_admin] = admin
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=control.app),base_url='http://test') as client:
        assert (await client.post('/services/chat/restart')).status_code == 202
        assert posts == ['/v1.51/containers/ours/restart']
        assert control.operations['chat']['status'] == 'succeeded'
        assert (await client.post('/services/chat/restart')).status_code == 409
        response = (await client.get('/controls')).json()
        assert response['services'] == ['chat']
        assert 'monotonic' not in response['operations']['chat']

@pytest.mark.asyncio
async def test_failure_reported_and_missing_controller_not_accepted(monkeypatch):
    control.app.dependency_overrides[control.require_admin] = admin
    monkeypatch.setattr(control, 'containers', AsyncMock(side_effect=httpx.ConnectError('socket unavailable')))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=control.app),base_url='http://test') as client:
        assert (await client.post('/services/chat/restart')).status_code == 503
        assert (await client.get('/controls')).status_code == 503
    control.operations['chat'] = {'status': 'restarting'}
    await control.perform_restart('chat', 7)
    assert control.operations['chat']['status'] == 'failed'
