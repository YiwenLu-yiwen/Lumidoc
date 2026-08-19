#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件服务诊断命令行工具
用法: python diagnose.py
"""

import os
import sys
import asyncio
import logging
import argparse

# 添加项目根目录到导入路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 初始化日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

async def main():
    """主函数"""
    try:
        print("\n========== Lumidoc 文件服务诊断工具 ==========\n")
        print("正在加载诊断模块...")
        
        # 导入诊断工具
        try:
            # 更新引用路径，使用fileproc模块中现有的诊断服务
            from src.modules.fileproc.services.diagnostics import FileServiceDiagnostics
        except ImportError as e:
            logger.error(f"导入诊断模块失败: {str(e)}")
            print("无法导入诊断模块，请确保您正在项目根目录下运行该脚本。")
            sys.exit(1)
        
        # 运行诊断
        await FileServiceDiagnostics().run_full_diagnostics()
        
    except Exception as e:
        logger.error(f"诊断过程中发生错误: {str(e)}")
        print(f"\n错误: {str(e)}")
        print("\n请检查是否在正确目录下运行，并确保环境变量已正确配置。")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lumidoc文件服务诊断工具")
    parser.add_argument("--fix", action="store_true", help="尝试自动修复发现的问题")
    parser.add_argument("--verbose", action="store_true", help="显示详细诊断信息")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 运行异步主函数
    asyncio.run(main()) 