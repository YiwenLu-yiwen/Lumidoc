#!/usr/bin/env python3
"""检查Redis中剩余的键"""

import redis

def check_redis_keys():
    try:
        r = redis.Redis(host='localhost', port=6379, password='123456789', db=0)
        
        # 获取所有键
        keys = r.keys('*')
        print(f"Redis中现有的键 ({len(keys)} 个):")
        
        for key in keys:
            key_str = key.decode('utf-8')
            key_type = r.type(key).decode('utf-8')
            print(f"  - {key_str} ({key_type})")
        
        return keys
        
    except Exception as e:
        print(f"检查Redis键失败: {e}")
        return []

if __name__ == "__main__":
    check_redis_keys()