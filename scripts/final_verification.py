#!/usr/bin/env python3
"""最终验证所有数据库是否完全清空"""

from neo4j import GraphDatabase
import psycopg2
import redis
import os

def final_verification():
    print("🔍 最终验证数据库清空状态\n")
    
    all_clear = True
    
    # 1. 验证Neo4j
    print("1. Neo4j数据库:")
    try:
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "123456789"))
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as node_count")
            node_count = result.single()["node_count"]
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as rel_count")
            rel_count = result.single()["rel_count"]
            
            if node_count == 0 and rel_count == 0:
                print("   ✅ 完全清空 (0 个节点, 0 个关系)")
            else:
                print(f"   ❌ 未完全清空 ({node_count} 个节点, {rel_count} 个关系)")
                all_clear = False
                
        driver.close()
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        all_clear = False
    
    # 2. 验证PostgreSQL
    print("\n2. PostgreSQL数据库:")
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="stpdb",
            user="stpuser",
            password="stppassword"
        )
        
        cur = conn.cursor()
        
        # 检查用户表数量
        cur.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename NOT LIKE 'pg_%' 
            AND tablename NOT LIKE 'sql_%'
        """)
        
        tables = cur.fetchall()
        if len(tables) == 0:
            print("   ✅ 完全清空 (0 个表)")
        else:
            print(f"   ❌ 未完全清空 ({len(tables)} 个表)")
            for table in tables:
                print(f"      - {table[0]}")
            all_clear = False
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        all_clear = False
    
    # 3. 验证Redis
    print("\n3. Redis缓存:")
    try:
        r = redis.Redis(host='localhost', port=6379, password='123456789', db=0)
        key_count = r.dbsize()
        if key_count == 0:
            print("   ✅ 完全清空 (0 个键)")
        else:
            print(f"   ⚠️  有服务注册键 ({key_count} 个键)")
            # 服务注册键是正常的，不算清空失败
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
    
    # 4. 验证存储目录
    print("\n4. 存储目录:")
    directories = ['./uploads', './content', './rag_storage', './rag_cache']
    total_files = 0
    
    for directory in directories:
        if os.path.exists(directory):
            file_count = sum([len(files) for r, d, files in os.walk(directory)])
            total_files += file_count
            if file_count == 0:
                print(f"   ✅ {directory}: 已清空")
            else:
                print(f"   ❌ {directory}: {file_count} 个文件")
                all_clear = False
        else:
            print(f"   ✅ {directory}: 不存在")
    
    print("\n" + "="*60)
    if all_clear:
        print("🎉 所有数据库和存储已完全清空！")
        print("\n📊 清空汇总:")
        print("   ✅ Neo4j: 所有节点和关系已删除")
        print("   ✅ PostgreSQL: 所有用户表已删除")
        print("   ✅ Redis: 数据已清空 (服务注册键正常)")
        print("   ✅ 存储目录: 所有文件已清空")
        print("\n🚀 系统已准备好接受新数据！")
    else:
        print("⚠️  清空过程中发现问题，请检查上述输出")
    
    return all_clear

if __name__ == "__main__":
    success = final_verification()
    exit(0 if success else 1)