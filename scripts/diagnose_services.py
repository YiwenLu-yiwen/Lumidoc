#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
服务诊断脚本
用于检查服务注册状态和健康状况
"""

import os
import sys
import asyncio
import json
from pathlib import Path

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(current_dir, '.env'))

from src.shared.service_discovery import ServiceRegistry, ServiceHealth
from src.shared.logger import initialize_logging, get_logger

# 初始化日志
initialize_logging("service_diagnostics")
logger = get_logger(__name__)

async def check_service_registry():
    """检查服务注册状态"""
    try:
        # 创建服务注册表实例
        registry = ServiceRegistry()
        await registry.connect()
        
        # 获取所有服务
        services = await registry.list_services()
        
        print("\n=== 服务注册状态 ===")
        if not services:
            print("未发现任何已注册的服务")
            return
            
        for service_name, instances in services.items():
            print(f"\n服务: {service_name}")
            print(f"实例数量: {len(instances)}")
            
            for instance in instances:
                print(f"\n  实例ID: {instance['service_id']}")
                print(f"  主机: {instance['host']}")
                print(f"  端口: {instance['port']}")
                print(f"  健康状态: {instance['health_status']}")
                print(f"  注册时间: {instance['registration_time']}")
                print(f"  最后心跳: {instance['last_heartbeat']}")
                
                if instance.get('endpoints'):
                    print("  端点:")
                    for name, path in instance['endpoints'].items():
                        print(f"    - {name}: {path}")
        
        await registry.close()
        
    except Exception as e:
        logger.error(f"检查服务注册状态失败: {str(e)}")
        print(f"\n错误: {str(e)}")

async def check_service_health(service_name: str, port: int):
    """检查特定服务的健康状态"""
    try:
        import aiohttp
        
        url = f"http://localhost:{port}/healthz"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"\n=== {service_name}服务健康状态 ===")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                else:
                    print(f"\n{service_name}服务健康检查失败: HTTP {response.status}")
    except Exception as e:
        print(f"\n检查{service_name}服务健康状态失败: {str(e)}")

async def main():
    """主函数"""
    print("\n开始诊断服务状态...")
    
    # 检查服务注册状态
    await check_service_registry()
    
    # 检查文件服务健康状态
    await check_service_health("文件服务", 8004)
    
    # 检查文件处理服务健康状态
    await check_service_health("文件处理服务", 8005)

if __name__ == "__main__":
    asyncio.run(main()) 