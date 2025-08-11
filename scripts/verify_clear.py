#!/usr/bin/env python3
"""验证数据库清空结果脚本"""

from neo4j import GraphDatabase
import psycopg2
import redis
import os

def verify_neo4j():
    try:
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "123456789"))
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as node_count")
            node_count = result.single()["node_count"]
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as rel_count")
            rel_count = result.single()["rel_count"]
            
            print(f"Neo4j: {node_count} 个节点, {rel_count} 个关系")
            
        driver.close()
        return node_count == 0 and rel_count == 0
    except Exception as e:
        print(f"Neo4j验证失败: {e}")
        return False

def verify_postgresql():
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="stpdb",
            user="stpuser",
            password="stppassword"
        )
        
        cur = conn.cursor()
        
        # 检查所有表的记录数
        cur.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename NOT LIKE 'pg_%' 
            AND tablename NOT LIKE 'sql_%'
        """)
        
        tables = cur.fetchall()
        total_rows = 0
        
        for table in tables:
            table_name = table[0]
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            total_rows += count
        
        print(f"PostgreSQL: {len(tables)} 个表, 总共 {total_rows} 条记录")
        
        cur.close()
        conn.close()
        return total_rows == 0
    except Exception as e:
        print(f"PostgreSQL验证失败: {e}")
        return False

def verify_redis():
    try:
        r = redis.Redis(host='localhost', port=6379, password='123456789', db=0)
        key_count = r.dbsize()
        print(f"Redis: {key_count} 个键")
        return key_count == 0
    except Exception as e:
        print(f"Redis验证失败: {e}")
        return False

def verify_storage():
    directories = ['./uploads', './content', './rag_storage', './rag_cache']
    total_files = 0
    
    for directory in directories:
        if os.path.exists(directory):
            file_count = sum([len(files) for r, d, files in os.walk(directory)])
            total_files += file_count
            print(f"存储目录 {directory}: {file_count} 个文件")
        else:
            print(f"存储目录 {directory}: 不存在")
    
    return total_files == 0

def main():
    print("🔍 验证数据库清空结果\n")
    
    results = []
    
    print("1. Neo4j数据库:")
    results.append(verify_neo4j())
    
    print("\n2. PostgreSQL数据库:")
    results.append(verify_postgresql())
    
    print("\n3. Redis缓存:")
    results.append(verify_redis())
    
    print("\n4. 存储目录:")
    results.append(verify_storage())
    
    print("\n" + "="*50)
    if all(results):
        print("✅ 所有数据库和存储已成功清空！")
    else:
        print("⚠️  清空验证中发现问题，请检查上述输出")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)