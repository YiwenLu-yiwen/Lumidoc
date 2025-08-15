#!/usr/bin/env python3
"""清空PostgreSQL数据库脚本"""

import psycopg2
import sys

def clear_postgresql():
    host = "localhost"
    port = 5432
    database = "stpdb"
    username = "stpuser"
    password = "stppassword"
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password
        )
        
        cur = conn.cursor()
        
        # 获取所有用户创建的表
        cur.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename NOT LIKE 'pg_%' 
            AND tablename NOT LIKE 'sql_%'
        """)
        
        tables = cur.fetchall()
        print(f"找到 {len(tables)} 个表:")
        
        if tables:
            for table in tables:
                table_name = table[0]
                print(f"  - {table_name}")
            
            print("\n开始清空数据库...")
            
            # 临时禁用外键约束
            cur.execute("SET session_replication_role = replica;")
            
            # 删除所有表的数据
            for table in tables:
                table_name = table[0]
                try:
                    cur.execute(f"TRUNCATE TABLE {table_name} CASCADE;")
                    print(f"✅ 清空表: {table_name}")
                except Exception as e:
                    print(f"⚠️  清空表 {table_name} 时出错: {e}")
            
            # 恢复外键约束
            cur.execute("SET session_replication_role = DEFAULT;")
            
            conn.commit()
            print("\n✅ PostgreSQL数据库已清空")
        else:
            print("✅ PostgreSQL数据库中没有用户表")
        
        # 清空序列（重置自增ID）
        cur.execute("""
            SELECT sequence_name FROM information_schema.sequences 
            WHERE sequence_schema = 'public'
        """)
        
        sequences = cur.fetchall()
        if sequences:
            print(f"\n重置 {len(sequences)} 个序列:")
            for seq in sequences:
                seq_name = seq[0]
                try:
                    cur.execute(f"ALTER SEQUENCE {seq_name} RESTART WITH 1;")
                    print(f"✅ 重置序列: {seq_name}")
                except Exception as e:
                    print(f"⚠️  重置序列 {seq_name} 时出错: {e}")
            
            conn.commit()
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL清空失败: {e}")
        return False

if __name__ == "__main__":
    success = clear_postgresql()
    sys.exit(0 if success else 1)