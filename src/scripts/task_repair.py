#!/usr/bin/env python3
"""
任务系统诊断和修复脚本
用于命令行调用，可以诊断和修复任务系统问题
"""

import sys
import os
import asyncio
import argparse
import logging
from src.shared.logger import initialize_logging, get_logger
from pathlib import Path
import json
from datetime import datetime

# 添加项目根目录到PATH
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

# 加载项目根目录.env文件
from dotenv import load_dotenv
env_file = root_dir / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
    print(f"已从 {env_file} 加载环境变量")

# 导入任务诊断工具
from src.shared.task_check import TaskDiagnostics

# 配置日志
initialize_logging("task_repair")
logger = get_logger(__name__)

class TaskRepairTool:
    """任务修复工具类"""
    
    def __init__(self):
        """初始化修复工具"""
        self.diagnostics = TaskDiagnostics()
        
    async def connect(self):
        """连接任务诊断工具"""
        await self.diagnostics.connect()
        
    async def close(self):
        """关闭连接"""
        await self.diagnostics.close()
        
    async def analyze(self, output_file=None):
        """
        分析任务系统状态
        
        Args:
            output_file: 可选的输出文件路径，用于保存分析结果
        """
        try:
            # 获取任务摘要
            summary = await self.diagnostics.get_task_summary()
            # 检查瓶颈
            bottlenecks = await self.diagnostics.find_task_bottlenecks()
            # 检查重复任务
            duplicates = await self.diagnostics.detect_duplicate_tasks()
            
            # 组装分析结果
            analysis = {
                "summary": summary,
                "bottlenecks": bottlenecks,
                "duplicates": duplicates,
                "timestamp": datetime.now().isoformat()
            }
            
            # 打印结果摘要
            print("\n======== 任务系统分析 ========")
            print(f"任务总数: {summary['total_tasks']}")
            print("\n状态分布:")
            for status, count in summary['status_counts'].items():
                if count > 0:
                    print(f"  {status}: {count}")
                    
            print(f"\n发现了 {len(bottlenecks)} 个潜在瓶颈")
            print(f"发现了 {len(duplicates)} 组重复任务")
            
            # 保存到文件
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(analysis, f, indent=2)
                print(f"\n详细分析结果已保存到 {output_file}")
                
            return analysis
            
        except Exception as e:
            logger.error(f"分析任务系统时出错: {str(e)}")
            raise
            
    async def repair(self, dry_run=True):
        """
        修复任务系统问题
        
        Args:
            dry_run: 是否只模拟修复而不实际执行
        
        Returns:
            Dict[str, Any]: 修复结果
        """
        if dry_run:
            print("\n======== 模拟修复模式 ========")
            print("这是模拟运行，不会实际修改任务")
            
            # 分析待修复的问题
            duplicates = await self.diagnostics.detect_duplicate_tasks()
            
            # 检查卡住的任务
            bottlenecks = await self.diagnostics.find_task_bottlenecks()
            stalled_tasks = [b for b in bottlenecks if b['type'] == 'long_running_task']
            
            # 简单计算
            repair_stats = {
                "would_clean_expired": 0,  # 无法准确预估，需要实际检查
                "would_mark_duplicates": sum(len(g['tasks']) - 1 for g in duplicates),
                "would_reset_stalled": len(stalled_tasks),
            }
            
            print("\n如果执行实际修复:")
            print(f"  将标记 {repair_stats['would_mark_duplicates']} 个重复任务")
            print(f"  将重置 {repair_stats['would_reset_stalled']} 个卡住的任务")
            print("  将清理过期任务（具体数量需要在实际执行时确定）")
            
            print("\n要执行实际修复，请使用 --no-dry-run 选项")
            return repair_stats
        else:
            print("\n======== 执行实际修复 ========")
            print("正在修复任务系统问题...")
            
            # 执行修复
            results = await self.diagnostics.repair_tasks()
            
            print("\n修复完成:")
            print(f"  清理过期任务: {results['cleaned_expired']}")
            print(f"  标记重复任务: {results['marked_duplicates']}")
            print(f"  重置卡住任务: {results['reset_stalled']}")
            if results['failed_attempts'] > 0:
                print(f"  失败尝试: {results['failed_attempts']}")
            
            if 'error' in results:
                print(f"\n修复过程中出现错误: {results['error']}")
                
            return results
            
    async def show_task(self, task_id):
        """
        显示特定任务的详情
        
        Args:
            task_id: 任务ID
        """
        if not self.diagnostics._task_manager:
            await self.diagnostics.connect()
            
        task_info = await self.diagnostics._task_manager.get_task_status(task_id)
        
        if not task_info or task_info.get("status") is None:
            print(f"任务 {task_id} 不存在或已过期")
            return
            
        print("\n======== 任务详情 ========")
        print(f"任务ID: {task_id}")
        print(f"任务名称: {task_info.get('task_name', 'unknown')}")
        print(f"状态: {task_info.get('status', 'unknown')}")
        print(f"创建时间: {task_info.get('created_at', 'unknown')}")
        print(f"创建者: {task_info.get('created_by', 'unknown')}")
        
        if 'updated_at' in task_info:
            print(f"更新时间: {task_info['updated_at']}")
            
        if 'error' in task_info:
            print(f"\n错误信息: {task_info['error']}")
            
        if task_info.get('content_hash'):
            print(f"\n内容哈希: {task_info['content_hash']}")
            
            # 检查是否有重复任务
            if self.diagnostics._task_manager:
                duplicates = await self.diagnostics.detect_duplicate_tasks()
                for group in duplicates:
                    if group['content_hash'] == task_info['content_hash']:
                        print(f"\n该任务存在 {len(group['tasks'])} 个副本:")
                        for task in group['tasks']:
                            if task['task_id'] == task_id:
                                print(f"  * {task['task_id']} ({task['status']}) - 当前任务")
                            else:
                                print(f"  - {task['task_id']} ({task['status']}) - 创建于 {task['created_at']}")
                        break
        
        # 显示任务参数和结果
        if 'params' in task_info:
            print("\n任务参数:")
            params = task_info['params']
            if isinstance(params, dict):
                if 'args' in params:
                    print(f"  参数: {params['args']}")
                if 'kwargs' in params:
                    for key, value in params['kwargs'].items():
                        print(f"  {key}: {value}")
            else:
                print(f"  {params}")
                
        if 'result' in task_info and task_info['result'] is not None:
            print("\n任务结果:")
            result = task_info['result']
            if isinstance(result, dict) and len(result) > 10:
                # 对于大型结果字典，只显示键
                print(f"  包含 {len(result)} 个键: {', '.join(list(result.keys())[:10])}...")
            elif isinstance(result, list) and len(result) > 10:
                # 对于大型结果列表，只显示长度和前几个元素
                print(f"  列表包含 {len(result)} 个元素")
                print(f"  前几个元素: {result[:5]}...")
            else:
                print(f"  {result}")
                
        if 'result_key' in task_info:
            print(f"\n结果存储在键: {task_info['result_key']}")
            
        return task_info

async def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='任务系统诊断和修复工具')
    
    # 创建子命令
    subparsers = parser.add_subparsers(dest='command', help='要执行的命令')
    
    # 分析命令
    analyze_parser = subparsers.add_parser('analyze', help='分析任务系统状态')
    analyze_parser.add_argument('--output', '-o', help='输出分析结果到文件')
    
    # 修复命令
    repair_parser = subparsers.add_parser('repair', help='修复任务系统问题')
    repair_parser.add_argument('--no-dry-run', action='store_true', help='实际执行修复(默认为模拟修复)')
    
    # 查看任务命令
    show_parser = subparsers.add_parser('show', help='显示特定任务的详情')
    show_parser.add_argument('task_id', help='要查看的任务ID')
    
    # 解析参数
    args = parser.parse_args()
    
    # 创建修复工具
    tool = TaskRepairTool()
    
    try:
        await tool.connect()
        
        if args.command == 'analyze':
            await tool.analyze(args.output)
        elif args.command == 'repair':
            await tool.repair(not args.no_dry_run)
        elif args.command == 'show':
            await tool.show_task(args.task_id)
        else:
            # 默认显示帮助
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\n操作已取消")
    except Exception as e:
        logger.error(f"执行出错: {str(e)}")
    finally:
        await tool.close()

if __name__ == "__main__":
    asyncio.run(main()) 