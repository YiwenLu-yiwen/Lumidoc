#!/usr/bin/env python3
"""
在现有PostgreSQL数据库中安装pgvector扩展
"""

import os
import sys
import asyncio
import asyncpg
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取PostgreSQL连接信息
POSTGRES_USER = os.getenv("POSTGRES_USER", "stpuser")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "stppassword")
POSTGRES_DB = os.getenv("POSTGRES_DB", "stpdb")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

# 构建连接字符串
CONNECTION_STRING = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

async def install_pgvector():
    """安装pgvector扩展并创建必要的表和索引"""
    print(f"连接到PostgreSQL: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
    
    try:
        # 连接到PostgreSQL
        conn = await asyncpg.connect(CONNECTION_STRING)
        
        # 检查pgvector扩展是否已安装
        result = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        if result:
            print("✅ pgvector扩展已安装")
        else:
            print("⚠️ pgvector扩展未安装")
            print("注意: 要安装pgvector扩展，PostgreSQL服务器需要支持该扩展。")
            print("如果您使用的是Docker，请确保使用的是包含pgvector的镜像，如ankane/pgvector")
            print("尝试安装pgvector扩展...")
            
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                print("✅ pgvector扩展安装成功")
            except Exception as e:
                print(f"❌ pgvector扩展安装失败: {str(e)}")
                print("请确保PostgreSQL服务器支持pgvector扩展")
                return False
        
        # 读取SQL脚本
        script_path = os.path.join(os.path.dirname(__file__), "setup_pgvector.sql")
        if not os.path.exists(script_path):
            print(f"❌ 找不到SQL脚本: {script_path}")
            return False
            
        with open(script_path, "r") as f:
            sql_script = f.read()
        
        # 执行SQL脚本
        print("执行SQL脚本创建表和索引...")
        
        # 分割SQL语句并逐条执行
        statements = sql_script.split(";")
        for statement in statements:
            statement = statement.strip()
            if statement:
                try:
                    await conn.execute(statement)
                except Exception as e:
                    print(f"⚠️ 执行SQL语句时出错: {str(e)}")
                    print(f"语句: {statement}")
                    # 继续执行其他语句
        
        print("✅ SQL脚本执行完成")
        
        # 验证表是否创建成功
        tables = [
            "rag_default_index_vectors",
            "rag_default_index_document_status",
            "rag_default_index_document_content",
            "rag_default_index_relationships"
        ]
        
        print("\n验证表是否创建成功:")
        for table in tables:
            result = await conn.fetchval(f"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = '{table}')")
            if result:
                print(f"✅ 表 {table} 创建成功")
            else:
                print(f"❌ 表 {table} 创建失败")
        
        # 关闭连接
        await conn.close()
        print("\n✅ 安装完成")
        
        return True
    except Exception as e:
        print(f"❌ 安装失败: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(install_pgvector())
    sys.exit(0 if success else 1) 