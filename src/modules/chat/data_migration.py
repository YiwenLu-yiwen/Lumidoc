import json
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import uuid
from sqlalchemy import text

from .models import ChatHistory
from src.shared.config import ChatServiceSettings
from src.shared.database import get_redis_client
from src.shared.time_utils import as_utc_naive, utc_now, utc_now_naive

settings = ChatServiceSettings()

# 配置日志
logger = logging.getLogger(__name__)

# 获取Redis客户端
redis_client = get_redis_client()

def migrate_old_messages_to_db(db: Session, days: int = 30) -> Dict[str, Any]:
    """Archive whole inactive conversations; commit before removing Redis copies."""
    from collections import defaultdict
    from .conversations import session_id
    cutoff = utc_now_naive() - timedelta(days=days)
    stats = dict(projects_processed=0, conversations_migrated=0, messages_migrated=0,
                 messages_skipped=0, errors=0, projects={})
    for key in redis_client.scan_iter(match="chat:history:*"):
        # Cold conversations must survive until the database commit succeeds.
        redis_client.persist(key)
        project = (key.decode() if isinstance(key, bytes) else key).split(':', 2)[2]
        stats['projects_processed'] += 1
        groups = defaultdict(list)
        for raw in redis_client.lrange(key, 0, -1):
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                stats['errors'] += 1
                continue
            try:
                timestamp = as_utc_naive(datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00')))
            except (ValueError, TypeError, KeyError, AttributeError):
                # Unknown age keeps the entire conversation active.
                timestamp = utc_now_naive()
                stats['errors'] += 1
            groups[(str(msg.get('user_id', 'unknown')), session_id(msg))].append((raw, msg, timestamp))
        for (user, conversation), records in groups.items():
            if max(record[2] for record in records) >= cutoff:
                stats['messages_skipped'] += len(records)
                continue
            try:
                for raw, msg, timestamp in records:
                    stable_id = msg.get('id') or str(uuid.uuid5(uuid.NAMESPACE_URL, project + str(raw)))
                    db.merge(ChatHistory(
                        id=stable_id, project_id=project, user_id=user,
                        role=msg.get('role', 'unknown'), content=msg.get('content', ''),
                        timestamp=timestamp,
                        meta_data={'source': 'automatic_archive', 'session_id': conversation,
                                   'thinking': msg.get('thinking', ''), 'migrated_at': utc_now().isoformat()},
                    ))
                db.commit()
            except Exception:
                db.rollback()
                stats['errors'] += 1
                logger.exception('Conversation archive failed; Redis records retained')
                continue
            # Exact-value removal preserves any new messages arriving during the commit.
            for raw, _, _ in records:
                redis_client.lrem(key, 1, raw)
            stats['conversations_migrated'] += 1
            stats['messages_migrated'] += len(records)
    return stats


def archive_inactive_conversations():
    """Own the synchronous SQLAlchemy session inside the background worker thread."""
    from src.database import get_db
    sessions = get_db()
    try:
        return migrate_old_messages_to_db(next(sessions))
    finally:
        sessions.close()


def fetch_chat_history(db: Session, project_id: str, user_id: Optional[str] = None, 
                       limit: int = 100, offset: int = 0, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    从PostgreSQL数据库获取历史聊天记录
    
    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID（可选）
        limit: 返回的最大记录数
        offset: 分页偏移量
        
    Returns:
        List[Dict]: 聊天记录列表
    """
    query = db.query(ChatHistory).filter(ChatHistory.project_id == project_id)
    
    # 如果指定了用户ID，则添加筛选条件
    if user_id:
        query = query.filter(ChatHistory.user_id == user_id)
    
    if session_id is not None:
        from sqlalchemy import func
        query = query.filter(func.coalesce(ChatHistory.meta_data['session_id'].as_string(), 'legacy') == session_id)

    # 按时间戳倒序排序并分页
    messages = query.order_by(ChatHistory.timestamp.desc()).offset(offset).limit(limit).all()
    
    # 转换为字典列表
    return [msg.to_dict() for msg in messages]
