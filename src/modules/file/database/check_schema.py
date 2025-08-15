"""
临时脚本：检查数据库表结构
"""
import asyncio
import logging
from ..config.database import FileServiceDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_project_files_schema():
    """检查project_files表结构"""
    try:
        pool = await FileServiceDatabase.get_pool()
        async with pool.acquire() as conn:
            # 查询project_files表结构
            result = await conn.fetch("""
                SELECT column_name, data_type, character_maximum_length 
                FROM information_schema.columns 
                WHERE table_name = 'project_files'
            """)
            
            logger.info("project_files表结构:")
            for row in result:
                logger.info(f"{row['column_name']}: {row['data_type']}, max_length={row['character_maximum_length']}")
            
            # 检查name字段长度限制
            name_column = next((row for row in result if row['column_name'] == 'name'), None)
            if name_column and name_column['character_maximum_length'] and name_column['character_maximum_length'] < 255:
                logger.warning(f"name字段长度限制过短: {name_column['character_maximum_length']}，建议至少255")
            
            # 检查path字段长度限制
            path_column = next((row for row in result if row['column_name'] == 'path'), None)
            if path_column and path_column['character_maximum_length'] and path_column['character_maximum_length'] < 255:
                logger.warning(f"path字段长度限制过短: {path_column['character_maximum_length']}，建议至少255")
            
            # 检查file_hash字段长度限制
            file_hash_column = next((row for row in result if row['column_name'] == 'file_hash'), None)
            if file_hash_column and file_hash_column['character_maximum_length'] and file_hash_column['character_maximum_length'] < 64:
                logger.warning(f"file_hash字段长度限制过短: {file_hash_column['character_maximum_length']}，建议至少64")
            
        await pool.close()
    except Exception as e:
        logger.error(f"检查数据库表结构失败: {str(e)}")

if __name__ == "__main__":
    asyncio.run(check_project_files_schema()) 