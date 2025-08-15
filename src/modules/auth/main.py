#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
认证服务启动入口
"""

import uvicorn
import sys
import os
from contextlib import asynccontextmanager

# 确保路径正确
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 添加src/modules到系统路径
modules_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

# 更新配置导入
from src.shared.config import AuthServiceSettings
from src.shared.health_check import register_health_routes, create_health_checker
settings = AuthServiceSettings()

# 创建健康检查器
health_checker = create_health_checker("auth", "auth_service_1")

# 定义lifespan事件管理器
@asynccontextmanager
async def lifespan(app):
    """应用生命周期管理"""
    # 启动事件
    try:
        await health_checker.start()
        print("Auth服务启动成功")
        
        # 注册到服务发现
        from src.shared.service_discovery import register_service
        await register_service("auth", port=settings.port, health_check_endpoint="/healthz")
        
    except Exception as e:
        print(f"Auth服务启动失败: {str(e)}")
        
    yield
    
    # 关闭事件
    try:
        await health_checker.stop()
        print("Auth服务关闭")
        
        # 从服务发现注销
        from src.shared.service_discovery import unregister_service
        await unregister_service("auth")
        
    except Exception as e:
        print(f"Auth服务关闭失败: {str(e)}")

# 导入并更新原有应用
import src.modules.auth.auth_api as auth_module
app = auth_module.app
# 更新lifespan
app.router.lifespan_context = lifespan

# 添加Auth特定的健康检查
async def check_database_connection():
    """检查数据库连接"""
    try:
        from src.database import get_db
        from sqlalchemy import text
        db_generator = get_db()
        db = next(db_generator)
        try:
            # 使用text()包装SQL语句
            db.execute(text("SELECT 1"))
            return True
        finally:
            db.close()
    except Exception as e:
        print(f"数据库连接检查失败: {str(e)}")
        return False

async def check_jwt_keys():
    """检查JWT密钥配置"""
    try:
        from src.shared.jwt_utils import get_private_key, get_public_key
        # 检查JWT密钥是否正确配置
        private_key = get_private_key()
        public_key = get_public_key()
        return private_key is not None and public_key is not None
    except Exception as e:
        print(f"JWT密钥检查失败: {str(e)}")
        return False

# 配置健康检查项
health_checker.add_check("database", check_database_connection, critical=True)
health_checker.add_check("jwt_keys", check_jwt_keys, critical=True)

# 注册健康检查路由
register_health_routes(app, health_checker)


if __name__ == "__main__":
    print(f"启动认证服务 - 监听: 0.0.0.0:{settings.port}")
    uvicorn.run(app, host="0.0.0.0", port=settings.port) 