#!/usr/bin/env python3
"""强制清空Redis所有数据库"""

import redis

def force_clear_redis():
    try:
        r = redis.Redis(host='localhost', port=6379, password='123456789')
        
        # 清空所有数据库
        r.flushall()
        print("✅ Redis所有数据库已强制清空")
        
        # 验证结果
        key_count = r.dbsize()
        print(f"清空后: Redis中有 {key_count} 个键")
        
        return True
        
    except Exception as e:
        print(f"❌ Redis强制清空失败: {e}")
        return False

if __name__ == "__main__":
    force_clear_redis()