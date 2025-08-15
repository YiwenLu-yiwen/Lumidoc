#!/usr/bin/env python3
"""删除PostgreSQL数据库中的所有表"""

import psycopg2
import sys

def drop_all_tables():
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
            ORDER BY tablename
        """)
        
        tables = cur.fetchall()
        print(f"找到 {len(tables)} 个表:")
        
        if tables:
            for table in tables:
                table_name = table[0]
                print(f"  - {table_name}")
            
            print("\n开始删除所有表...")
            
            # 删除所有表（CASCADE会自动处理外键约束）
            for table in tables:
                table_name = table[0]
                try:
                    cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
                    print(f"✅ 删除表: {table_name}")
                except Exception as e:
                    print(f"❌ 删除表 {table_name} 时出错: {e}")
            
            conn.commit()
            
            # 验证所有表都已删除
            cur.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename NOT LIKE 'pg_%' 
                AND tablename NOT LIKE 'sql_%'
            """)
            
            remaining_tables = cur.fetchall()
            if not remaining_tables:
                print(f"\n✅ 所有 {len(tables)} 个表已成功删除")
            else:
                print(f"\n⚠️  还有 {len(remaining_tables)} 个表未删除:")
                for table in remaining_tables:
                    print(f"  - {table[0]}")
            
        else:
            print("✅ PostgreSQL数据库中没有用户表")
        
        # 删除所有序列
        cur.execute("""
            SELECT sequence_name FROM information_schema.sequences 
            WHERE sequence_schema = 'public'
        """)
        
        sequences = cur.fetchall()
        if sequences:
            print(f"\n删除 {len(sequences)} 个序列:")
            for seq in sequences:
                seq_name = seq[0]
                try:
                    cur.execute(f"DROP SEQUENCE IF EXISTS {seq_name} CASCADE;")
                    print(f"✅ 删除序列: {seq_name}")
                except Exception as e:
                    print(f"❌ 删除序列 {seq_name} 时出错: {e}")
            
            conn.commit()
        
        # 删除所有函数
        cur.execute("""
            SELECT proname, oidvectortypes(proargtypes) as args
            FROM pg_proc INNER JOIN pg_namespace ns ON (pg_proc.pronamespace = ns.oid)
            WHERE ns.nspname = 'public' AND proowner > 1
        """)
        
        functions = cur.fetchall()
        if functions:
            print(f"\n删除 {len(functions)} 个函数:")
            for func in functions:
                func_name = func[0]
                func_args = func[1]
                try:
                    cur.execute(f"DROP FUNCTION IF EXISTS {func_name}({func_args}) CASCADE;")
                    print(f"✅ 删除函数: {func_name}({func_args})")
                except Exception as e:
                    print(f"❌ 删除函数 {func_name} 时出错: {e}")
            
            conn.commit()
        
        # 删除所有类型
        cur.execute("""
            SELECT typname FROM pg_type 
            WHERE typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            AND typtype = 'e'  -- 枚举类型
        """)
        
        types = cur.fetchall()
        if types:
            print(f"\n删除 {len(types)} 个自定义类型:")
            for type_row in types:
                type_name = type_row[0]
                try:
                    cur.execute(f"DROP TYPE IF EXISTS {type_name} CASCADE;")
                    print(f"✅ 删除类型: {type_name}")
                except Exception as e:
                    print(f"❌ 删除类型 {type_name} 时出错: {e}")
            
            conn.commit()
        
        cur.close()
        conn.close()
        
        print(f"\n🎉 PostgreSQL数据库已完全清空！")
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL表删除失败: {e}")
        return False

if __name__ == "__main__":
    success = drop_all_tables()
    sys.exit(0 if success else 1)