"""会话删除必须保留同项目的其他会话和用户，并先停止后台回复。"""
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.modules.chat import chat_service as service

@pytest.mark.asyncio
async def test_delete_only_selected_conversation_after_stopping_generation(monkeypatch):
    records = [
        {'id':'a','session_id':'one','user_id':'2','role':'user','content':'remove'},
        {'id':'b','session_id':'two','user_id':'2','role':'user','content':'keep'},
        {'id':'c','session_id':'one','user_id':'3','role':'user','content':'keep other user'},
    ]
    cache = MagicMock()
    cache.lrem.return_value = 1
    cache.lrange.return_value = [json.dumps(m) for m in records]
    monkeypatch.setattr(service, 'redis_client', cache)
    auth = AsyncMock(return_value={'auth_type':'user','user':{'user_id':2}})
    monkeypatch.setattr(service, 'require_project_access', auth)
    jobs = MagicMock(stop=AsyncMock())
    monkeypatch.setattr(service, 'response_jobs', jobs)
    db = MagicMock()
    query = db.query.return_value.filter.return_value
    query.filter.return_value = query
    query.all.return_value = [
        MagicMock(meta_data={'session_id':'one'}),
        MagicMock(meta_data={'session_id':'two'}),
    ]
    response = await service.delete_conversation('project', 'one', MagicMock(), db)
    assert response.success
    jobs.stop.assert_awaited_once_with(('project','2','one'))
    cache.lrem.assert_called_once_with('chat:history:project', 0, json.dumps(records[0]))
    db.delete.assert_called_once_with(query.all.return_value[0])
    db.commit.assert_called_once()
    cache.delete.assert_not_called()
