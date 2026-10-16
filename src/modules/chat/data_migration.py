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
    """
    将Redis中超过指定天数的聊天记录迁移到PostgreSQL数据库
    
    Args:
        db: 数据库会话
        days: 迁移超过多少天的记录，默认30天
        
    Returns:
        Dict: 包含迁移结果统计信息
    """
    logger.info(f"开始迁移超过{days}天的聊天记录到PostgreSQL")
    
    # 计算截止日期
    cutoff_date = utc_now_naive() - timedelta(days=days)
    logger.info(f"截止日期: {cutoff_date.isoformat()}")
    
    # 用于保存统计信息
    stats = {
        "projects_processed": 0,
        "messages_migrated": 0,
        "messages_skipped": 0,
        "errors": 0,
        "projects": {}
    }
    
    try:
        # 获取所有项目的聊天历史键
        chat_keys = redis_client.keys("chat:history:*")
        logger.info(f"找到{len(chat_keys)}个项目的聊天历史")
        
        # 如果没有项目聊天历史，直接返回
        if not chat_keys:
            logger.info("没有找到任何聊天历史，迁移终止")
            return stats
        
        # 检查数据库连接
        try:
            # 简单测试数据库连接
            db.execute(text("SELECT 1"))
            logger.info("数据库连接正常")
        except Exception as e:
            logger.error(f"数据库连接测试失败: {str(e)}")
            stats["errors"] += 1
            return stats
            
        for key in chat_keys:
            # 处理键的解码问题，确保key是字节或字符串
            if isinstance(key, bytes):
                project_id = key.decode('utf-8').split(':')[-1]
            else:
                project_id = str(key).split(':')[-1]
                
            stats["projects_processed"] += 1
            
            # 为每个项目创建统计信息
            project_stats = {
                "messages_total": 0,
                "messages_migrated": 0,
                "messages_skipped": 0,
                "errors": 0
            }
            
            try:
                # 获取所有消息
                raw_messages = redis_client.lrange(key, 0, -1)
                project_stats["messages_total"] = len(raw_messages)
                logger.info(f"项目 {project_id} 共有 {len(raw_messages)} 条消息")
                
                # 处理每条消息
                for raw_msg in raw_messages:
                    try:
                        msg_data = json.loads(raw_msg)
                        
                        # 解析时间戳
                        if 'timestamp' in msg_data and msg_data['timestamp']:
                            try:
                                # 假设时间戳是ISO格式
                                msg_timestamp = as_utc_naive(
                                    datetime.fromisoformat(msg_data['timestamp'].replace('Z', '+00:00'))
                                )
                            except ValueError:
                                # 时间戳格式无效，使用当前时间
                                logger.warning(f"无效的时间戳格式: {msg_data['timestamp']}")
                                msg_timestamp = utc_now_naive()
                        else:
                            msg_timestamp = utc_now_naive()
                        
                        # 检查消息是否超过截止日期
                        if msg_timestamp < cutoff_date:
                            # 创建数据库记录
                            chat_history = ChatHistory(
                                id=msg_data.get('id', str(uuid.uuid4())),
                                project_id=project_id,
                                user_id=msg_data.get('user_id', 'unknown'),
                                role=msg_data.get('role', 'unknown'),
                                content=msg_data.get('content', ''),
                                timestamp=msg_timestamp,
                                meta_data={"source": "redis_migration", "migrated_at": utc_now().isoformat(), "session_id": msg_data.get("session_id", "legacy")}
                            )
                            
                            # 保存到数据库
                            db.add(chat_history)
                            stats["messages_migrated"] += 1
                            project_stats["messages_migrated"] += 1
                            
                            # 从Redis中删除已迁移的消息
                            redis_client.lrem(key, 1, raw_msg)
                            logger.debug(f"项目 {project_id} 的消息 {chat_history.id} 已迁移并从Redis移除")
                        else:
                            stats["messages_skipped"] += 1
                            project_stats["messages_skipped"] += 1
                            
                    except json.JSONDecodeError:
                        logger.error(f"解析聊天消息JSON失败: {raw_msg}")
                        stats["errors"] += 1
                        project_stats["errors"] += 1
                        continue
                    except Exception as e:
                        logger.error(f"处理消息时出错: {str(e)}")
                        stats["errors"] += 1
                        project_stats["errors"] += 1
                        continue
                
                # 提交数据库事务
                db.commit()
                
                # 更新项目统计信息
                stats["projects"][project_id] = project_stats
                
                logger.info(f"项目 {project_id} 迁移完成: 迁移 {project_stats['messages_migrated']} 条, 跳过 {project_stats['messages_skipped']} 条, 错误 {project_stats['errors']} 条")
                
            except Exception as e:
                logger.error(f"处理项目{project_id}的聊天历史时出错: {str(e)}")
                db.rollback()
                stats["errors"] += 1
                project_stats["errors"] += 1
                stats["projects"][project_id] = project_stats
                continue
        
        logger.info(f"迁移完成: 处理了{stats['projects_processed']}个项目，迁移了{stats['messages_migrated']}条消息，跳过了{stats['messages_skipped']}条，发生{stats['errors']}个错误")
        return stats
    
    except Exception as e:
        logger.error(f"迁移过程中出错: {str(e)}")
        db.rollback()
        stats["errors"] += 1
        return stats


def fetch_chat_history(db: Session, project_id: str, user_id: Optional[str] = None, 
                       limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
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
    
    # 按时间戳倒序排序并分页
    messages = query.order_by(ChatHistory.timestamp.desc()).offset(offset).limit(limit).all()
    
    # 转换为字典列表
    return [msg.to_dict() for msg in messages]
