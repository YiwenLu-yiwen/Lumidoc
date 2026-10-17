import json
from datetime import timedelta
from unittest.mock import Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.modules.chat import data_migration as migration
from src.modules.chat.models import ChatHistory
from src.shared.time_utils import utc_now_naive

class Messages:
    def __init__(self, records):
        self.records = [json.dumps(record) for record in records]
    def scan_iter(self, **kwargs):
        return ['chat:history:project']
    def persist(self, key):
        pass
    def lrange(self, *args):
        return list(self.records)
    def lrem(self, key, count, raw):
        self.records.remove(raw)

def message(identifier, conversation, age):
    return dict(id=identifier, session_id=conversation, user_id='u', role='user',
                content=identifier, thinking='saved reasoning',
                timestamp=(utc_now_naive()-timedelta(days=age)).isoformat())

def test_archive_groups_by_last_activity_and_keeps_full_conversation(monkeypatch):
    cache = Messages([message('1','old',40),message('2','old',35),
                      message('3','active',40),message('4','active',1)])
    monkeypatch.setattr(migration,'redis_client',cache)
    engine=create_engine('sqlite://')
    ChatHistory.__table__.create(engine)
    with Session(engine) as db:
        result=migration.migrate_old_messages_to_db(db)
        assert result['conversations_migrated']==1
        assert {json.loads(row)['id'] for row in cache.records}=={'3','4'}
        archived=migration.fetch_chat_history(db,'project','u',session_id='old')
        assert {row['id'] for row in archived}=={'1','2'}
        assert all(row['thinking']=='saved reasoning' for row in archived)
        assert migration.migrate_old_messages_to_db(db)['conversations_migrated']==0

def test_commit_failure_does_not_remove_cache(monkeypatch):
    cache=Messages([message('1','old',40),message('2','old',35)])
    monkeypatch.setattr(migration,'redis_client',cache)
    db=Mock()
    db.commit.side_effect=RuntimeError('database unavailable')
    result=migration.migrate_old_messages_to_db(db)
    assert result['errors']==1
    assert len(cache.records)==2
    db.rollback.assert_called_once()
