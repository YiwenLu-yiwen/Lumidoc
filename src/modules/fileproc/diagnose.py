#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件服务诊断工具

用于诊断和排查文件上传、处理服务中的问题
"""

# ruff: noqa: E402 -- direct execution adjusts sys.path before package imports.

import os
import sys
import json
import asyncio
import argparse
import traceback

# 确保路径正确
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 添加src目录到系统路径
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# 初始化日志
from src.shared.logger import initialize_logging, get_logger
initialize_logging("file_diagnostics")
logger = get_logger(__name__)

# 导入诊断工具
from src.modules.fileproc.services.diagnostics import FileServiceDiagnostics

async def run_diagnostics(args):
    """运行诊断程序"""
    try:
        diagnostics = FileServiceDiagnostics()

        if args.check_health:
            # 健康检查
            # 使用服务发现获取服务URL
            file_service_url = await diagnostics.get_service_url("file")
            fileproc_service_url = await diagnostics.get_service_url("fileproc")

            file_health = await diagnostics.check_service_health(file_service_url)
            fileproc_health = await diagnostics.check_service_health(fileproc_service_url)

            print("\n=== 服务健康状态 ===")
            print(f"文件服务(file): {file_health['status']}")
            print(f"文件处理服务(fileproc): {fileproc_health['status']}")

            if not file_health['success'] or not fileproc_health['success']:
                print("\n可能的解决方案:")
                print("1. 检查服务是否已启动")
                print("2. 检查服务端口是否正确")
                print("3. 查看日志文件中是否有错误信息")

        elif args.check_redis:
            # Redis检查
            redis_result = await diagnostics.check_redis_connection()

            print("\n=== Redis连接状态 ===")
            if redis_result['success']:
                print(f"状态: {redis_result['status']}")
                print(f"已注册服务: {', '.join(redis_result['registered_services'])}")
            else:
                print(f"错误: {redis_result['error']}")
                print("\n可能的解决方案:")
                print("1. 检查Redis服务是否运行")
                print("2. 确认Redis连接信息是否正确")
                print("3. 检查网络连接")

        elif args.check_postgres:
            # PostgreSQL检查
            postgres_result = await diagnostics.check_postgres_connection()

            print("\n=== PostgreSQL连接状态 ===")
            if postgres_result['success']:
                print(f"状态: {postgres_result['status']}")
                print(f"文件相关表: {', '.join(postgres_result['existing_tables'])}")
                print(f"文件记录数: {postgres_result['file_count']}")
            else:
                print(f"错误: {postgres_result['error']}")
                print("\n可能的解决方案:")
                print("1. 检查PostgreSQL服务是否运行")
                print("2. 确认数据库连接信息是否正确")
                print("3. 检查数据库表是否已初始化")

        elif args.check_storage:
            # 存储目录检查
            dir_result = diagnostics.check_directories()

            print("\n=== 存储目录状态 ===")
            if dir_result['success']:
                dirs = dir_result['directories']
                for dir_name, info in dirs.items():
                    print(f"\n{dir_name}:")
                    print(f"  路径: {info['path']}")
                    print(f"  存在: {'是' if info['exists'] else '否'}")
                    print(f"  是目录: {'是' if info['is_directory'] else '否'}")
                    print(f"  可写: {'是' if info['writable'] else '否'}")

                    if 'owner' in info:
                        print(f"  所有者: {info['owner']}")
                        print(f"  组: {info['group']}")
                        print(f"  权限: {info['permissions']}")

                # 检查目录是否存在问题
                has_problems = False
                for dir_name, info in dirs.items():
                    if not info['exists'] or not info['is_directory'] or not info['writable']:
                        has_problems = True
                        break

                if has_problems:
                    print("\n发现问题，可能的解决方案:")
                    print("1. 创建缺失的目录: mkdir -p [目录路径]")
                    print("2. 修改目录权限: chmod -R 755 [目录路径]")
                    print("3. 确保运行服务的用户有权限访问这些目录")
            else:
                print(f"错误: {dir_result['error']}")

        elif args.check_system:
            # 系统信息检查
            sys_result = diagnostics.check_system_info()

            print("\n=== 系统信息 ===")
            if sys_result['success']:
                info = sys_result['system_info']
                print(f"平台: {info['platform']}")
                print(f"Python版本: {info['python_version'].split()[0]}")
                print(f"主机名: {info['hostname']}")
                print(f"当前目录: {info['current_dir']}")
                print(f"用户: {info['user']}")

                print(f"\nGPU: {info['gpu']['info']}")
                print(f"Docling: {info['docling']['info']}")

                if 'disk_space' in info:
                    disk = info['disk_space']
                    if 'error' not in disk:
                        print("\n磁盘空间:")
                        print(f"  可用: {disk['free_gb']} GB")
                        print(f"  总计: {disk['total_gb']} GB")
                        print(f"  剩余比例: {disk['percentage_free']}%")

                        if disk['percentage_free'] < 10:
                            print("\n警告: 磁盘空间不足，可能影响文件处理")
            else:
                print(f"错误: {sys_result['error']}")

        elif args.test_upload:
            # 测试文件上传
            if not args.project_id:
                print("错误: 测试上传需要指定项目ID (--project-id)")
                return

            print("\n=== 测试文件上传 ===")
            print(f"项目ID: {args.project_id}")
            print("正在上传测试文件...")

            upload_result = await diagnostics.test_file_upload(args.project_id)

            if upload_result['success']:
                print("上传成功!")
                print(f"文件ID: {upload_result['file_id']}")

                # 检查处理状态
                if 'task_id' in upload_result['response']:
                    task_id = upload_result['response']['task_id']
                    if task_id:
                        print(f"任务ID: {task_id}")
                        print("正在检查处理状态...")

                        for i in range(5):  # 轮询5次
                            status_result = await diagnostics.check_task_status(task_id)
                            if status_result['success']:
                                print(f"处理状态: {status_result['status']}")
                                if status_result['status'] in ['completed', 'failed']:
                                    break
                            else:
                                print(f"获取状态失败: {status_result['error']}")
                                break

                            if i < 4:  # 不是最后一次轮询
                                print("等待3秒...")
                                await asyncio.sleep(3)
            else:
                print(f"上传失败: {upload_result['error']}")
                print("\n可能的解决方案:")
                print("1. 检查文件服务是否正常运行")
                print("2. 确认项目ID是否有效")
                print("3. 检查网络连接和服务URL配置")

        elif args.read_logs:
            # 读取日志
            log_result = await diagnostics.read_logs(args.log_lines)

            print(f"\n=== 最近 {args.log_lines} 行日志 ===")
            if log_result['success']:
                logs = log_result['logs']
                for log_file, lines in logs.items():
                    print(f"\n文件: {log_file}")
                    print("-" * 50)
                    for line in lines:
                        print(line)
            else:
                print(f"错误: {log_result['error']}")
                print("\n可能的解决方案:")
                print("1. 检查LOG_FILE环境变量是否正确设置")
                print("2. 确认logs目录是否存在")
                print("3. 检查日志文件权限")

        elif args.full_diagnostics:
            # 完整诊断
            print("\n=== 运行完整诊断 ===")
            print("这可能需要一些时间...")

            project_id = args.project_id if args.project_id else None
            results = await diagnostics.run_full_diagnostics(project_id)

            if args.output:
                # 将结果保存到文件
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"诊断结果已保存到: {args.output}")

            # 分析问题并提供建议
            analyze_diagnostics(results)

        else:
            # 默认运行基本检查
            print("\n=== 基本系统检查 ===")

            # 检查系统信息
            sys_result = diagnostics.check_system_info()
            if sys_result['success']:
                info = sys_result['system_info']
                print(f"平台: {info['platform']}")
                print(f"GPU: {'可用' if info['gpu']['available'] else '不可用'}")
                print(f"Docling: {'可用' if info['docling']['available'] else '不可用'}")

            # 检查目录
            dir_result = diagnostics.check_directories()
            if dir_result['success']:
                dirs = dir_result['directories']
                storage_ok = dirs['upload_dir']['exists'] and dirs['upload_dir']['writable']
                content_ok = dirs['content_dir']['exists'] and dirs['content_dir']['writable']
                print(f"上传目录: {'正常' if storage_ok else '有问题'}")
                print(f"内容目录: {'正常' if content_ok else '有问题'}")

            # 获取服务URL
            file_service_url = await diagnostics.get_service_url("file")
            fileproc_service_url = await diagnostics.get_service_url("fileproc")

            # 检查服务健康
            file_health = await diagnostics.check_service_health(file_service_url)
            fileproc_health = await diagnostics.check_service_health(fileproc_service_url)
            print(f"文件服务: {'正常' if file_health['success'] else '异常'}")
            print(f"处理服务: {'正常' if fileproc_health['success'] else '异常'}")

            # 检查数据库连接
            redis_result = await diagnostics.check_redis_connection()
            postgres_result = await diagnostics.check_postgres_connection()
            print(f"Redis: {'正常' if redis_result['success'] else '异常'}")
            print(f"PostgreSQL: {'正常' if postgres_result['success'] else '异常'}")

            print("\n要获取详细诊断，请使用 --full-diagnostics 参数")

    except Exception as e:
        print(f"诊断过程中发生错误: {str(e)}")
        print(traceback.format_exc())

def analyze_diagnostics(results):
    """分析诊断结果并提供建议"""
    print("\n=== 诊断结果分析 ===")

    # 收集问题
    issues = []

    # 检查服务健康
    if not results['diagnostics']['file_service_health']['success']:
        issues.append("文件服务(file)不可访问或未运行")

    if not results['diagnostics']['fileproc_service_health']['success']:
        issues.append("文件处理服务(fileproc)不可访问或未运行")

    # 检查数据库连接
    if not results['diagnostics']['redis_connection']['success']:
        issues.append("Redis连接失败")

    if not results['diagnostics']['postgres_connection']['success']:
        issues.append("PostgreSQL连接失败")

    # 检查目录
    dir_result = results['diagnostics']['directories']
    if not dir_result['success']:
        issues.append("存储目录检查失败")
    else:
        dirs = dir_result['directories']
        for dir_name, info in dirs.items():
            if not info['exists']:
                issues.append(f"{dir_name}不存在")
            elif not info['writable']:
                issues.append(f"{dir_name}不可写")

    # 检查系统
    sys_result = results['diagnostics']['system_info']
    if sys_result['success']:
        info = sys_result['system_info']

        # 检查GPU支持
        if info['gpu']['available'] and 'USE_GPU' in os.environ and os.environ['USE_GPU'].lower() == 'true':
            if not info['docling']['available']:
                issues.append("GPU可用但docling库未安装")

        # 检查磁盘空间
        if 'disk_space' in info and 'error' not in info['disk_space']:
            if info['disk_space']['percentage_free'] < 10:
                issues.append("磁盘空间不足(小于10%)")

    # 检查服务发现
    if 'service_discovery' in results['diagnostics'] and not results['diagnostics']['service_discovery']['success']:
        issues.append("服务发现功能异常")

    # 检查上传测试
    if 'file_upload_test' in results['diagnostics'] and not results['diagnostics']['file_upload_test']['success']:
        issues.append("文件上传测试失败")

    # 检查日志
    if 'logs' in results['diagnostics'] and not results['diagnostics']['logs']['success']:
        issues.append("日志读取失败")

    # 输出问题和建议
    if issues:
        print("\n发现以下问题:")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue}")

        print("\n建议的解决方案:")

        # 针对具体问题提供建议
        if "文件服务(file)不可访问或未运行" in issues or "文件处理服务(fileproc)不可访问或未运行" in issues:
            print("- 检查服务是否已启动:")
            print("  查看正在运行的服务: ps aux | grep 'file\\|fileproc'")
            print("  启动服务: ./start_services.sh 或 python -m src.modules.file.main")

        if "Redis连接失败" in issues:
            print("- 检查Redis服务:")
            print("  确认Redis服务运行状态: redis-cli ping")
            print("  检查Redis连接参数是否正确(.env文件)")

        if "PostgreSQL连接失败" in issues:
            print("- 检查PostgreSQL服务:")
            print("  确认服务运行状态: pg_isready")
            print("  检查数据库连接参数是否正确(.env文件)")

        if any(issue.endswith("不存在") for issue in issues):
            print("- 创建缺失的目录:")
            print("  mkdir -p ./storage/content ./temp")

        if any(issue.endswith("不可写") for issue in issues):
            print("- 修改目录权限:")
            print("  chmod -R 755 ./storage ./temp")
            print("  确保运行服务的用户有权限访问这些目录")

        if "磁盘空间不足" in '\n'.join(issues):
            print("- 清理磁盘空间:")
            print("  删除临时文件: rm -rf ./temp/*")
            print("  考虑增加存储空间或清理不必要的文件")

        if "文件上传测试失败" in issues:
            print("- 文件上传问题:")
            print("  检查文件服务URL配置是否正确")
            print("  确认项目ID是否有效")
            print("  查看日志获取详细错误信息: ./diagnose.py --read-logs")

        # 全局建议
        print("\n其他建议:")
        print("- 检查服务日志中的详细错误信息")
        print("- 确保.env文件中的配置正确")
        print("- 重启所有服务: ./start_services.sh restart")
    else:
        print("未发现明显问题，系统运行正常。")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="文件服务诊断工具")

    # 基本参数
    parser.add_argument("--project-id", help="用于测试的项目ID")
    parser.add_argument("--output", help="将诊断结果保存到指定文件")

    # 特定检查
    parser.add_argument("--check-health", action="store_true", help="检查服务健康状态")
    parser.add_argument("--check-redis", action="store_true", help="检查Redis连接")
    parser.add_argument("--check-postgres", action="store_true", help="检查PostgreSQL连接")
    parser.add_argument("--check-storage", action="store_true", help="检查存储目录")
    parser.add_argument("--check-system", action="store_true", help="检查系统信息")

    # 测试功能
    parser.add_argument("--test-upload", action="store_true", help="测试文件上传(需要--project-id)")

    # 日志查看
    parser.add_argument("--read-logs", action="store_true", help="读取日志文件")
    parser.add_argument("--log-lines", type=int, default=100, help="读取日志的行数")

    # 完整诊断
    parser.add_argument("--full-diagnostics", action="store_true", help="运行完整诊断")

    args = parser.parse_args()

    # 运行诊断
    asyncio.run(run_diagnostics(args))

if __name__ == "__main__":
    main()
