#!/usr/bin/env python3
"""清空Neo4j数据库脚本"""

from neo4j import GraphDatabase
import sys

def clear_neo4j():
    uri = "bolt://localhost:7687"
    username = "neo4j"
    password = "123456789"
    
    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        
        with driver.session() as session:
            # 获取数据库中的节点和关系统计
            result = session.run("MATCH (n) RETURN count(n) as node_count")
            node_count = result.single()["node_count"]
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as rel_count")
            rel_count = result.single()["rel_count"]
            
            print(f"清空前: {node_count} 个节点, {rel_count} 个关系")
            
            if node_count > 0 or rel_count > 0:
                # 清空所有数据
                session.run("MATCH (n) DETACH DELETE n")
                print("✅ Neo4j数据库已清空")
            else:
                print("✅ Neo4j数据库已经是空的")
            
            # 验证清空结果
            result = session.run("MATCH (n) RETURN count(n) as node_count")
            node_count = result.single()["node_count"]
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as rel_count")
            rel_count = result.single()["rel_count"]
            
            print(f"清空后: {node_count} 个节点, {rel_count} 个关系")
            
        driver.close()
        return True
        
    except Exception as e:
        print(f"❌ Neo4j清空失败: {e}")
        return False

if __name__ == "__main__":
    success = clear_neo4j()
    sys.exit(0 if success else 1)