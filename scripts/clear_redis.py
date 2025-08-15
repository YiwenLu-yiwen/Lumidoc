#!/usr/bin/env python3
"""清空Redis缓存脚本"""

import redis
import sys

def clear_redis():
    try:
        r = redis.Redis(host='localhost', port=6379, password='123456789', db=0)
        
        # 获取所有键的数量
        key_count = r.dbsize()
        print(f"清空前: Redis中有 {key_count} 个键")
        
        if key_count > 0:
            # 清空所有数据
            r.flushall()
            print("✅ Redis缓存已清空")
        else:
            print("✅ Redis缓存已经是空的")
        
        # 验证清空结果
        key_count = r.dbsize()
        print(f"清空后: Redis中有 {key_count} 个键")
        
        return True
        
    except Exception as e:
        print(f"❌ Redis清空失败: {e}")
        return False

if __name__ == "__main__":
    success = clear_redis()
    sys.exit(0 if success else 1)