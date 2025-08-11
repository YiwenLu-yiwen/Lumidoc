import os
import logging
import sys
from src.shared.logger import initialize_logging, get_logger
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import psycopg2
from sqlalchemy.exc import SQLAlchemyError
import psutil
from dotenv import load_dotenv
from src.database import engine

# ANSI颜色代码
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# 配置日志
initialize_logging("system_checker")
logger = get_logger(__name__)

# 默认环境变量配置
DEFAULT_ENV = {
    'POSTGRES_HOST': 'localhost',
    'POSTGRES_PORT': '5432',
    'POSTGRES_USER': 'stpuser',
    'POSTGRES_PASSWORD': 'stppassword',
    'POSTGRES_DB': 'stpdb',
    'REDIS_HOST': 'localhost',
    'REDIS_PORT': '6379',
    'REDIS_DB': '0',
    'REDIS_PASSWORD': '',
    'OPENAI_API_KEY': '',
    'OPENAI_API_BASE': 'https://api.openai.com/v1',
    'MODEL_NAME': 'gpt-3.5-turbo',
    'MAX_TOKENS': '2000',
    'TEMPERATURE': '0.7',
    'LOG_LEVEL': 'INFO'
}

def create_default_env(env_path: Path) -> None:
    """创建默认的.env文件"""
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write("# 数据库配置\n")
            f.write(f"POSTGRES_HOST={DEFAULT_ENV['POSTGRES_HOST']}\n")
            f.write(f"POSTGRES_PORT={DEFAULT_ENV['POSTGRES_PORT']}\n")
            f.write(f"POSTGRES_USER={DEFAULT_ENV['POSTGRES_USER']}\n")
            f.write(f"POSTGRES_PASSWORD={DEFAULT_ENV['POSTGRES_PASSWORD']}\n")
            f.write(f"POSTGRES_DB={DEFAULT_ENV['POSTGRES_DB']}\n\n")
            
            f.write("# Redis配置\n")
            f.write(f"REDIS_HOST={DEFAULT_ENV['REDIS_HOST']}\n")
            f.write(f"REDIS_PORT={DEFAULT_ENV['REDIS_PORT']}\n")
            f.write(f"REDIS_DB={DEFAULT_ENV['REDIS_DB']}\n")
            f.write(f"REDIS_PASSWORD={DEFAULT_ENV['REDIS_PASSWORD']}\n\n")
            
            f.write("# OpenAI配置\n")
            f.write(f"OPENAI_API_KEY={DEFAULT_ENV['OPENAI_API_KEY']}\n")
            f.write(f"OPENAI_API_BASE={DEFAULT_ENV['OPENAI_API_BASE']}\n")
            f.write(f"MODEL_NAME={DEFAULT_ENV['MODEL_NAME']}\n")
            f.write(f"MAX_TOKENS={DEFAULT_ENV['MAX_TOKENS']}\n")
            f.write(f"TEMPERATURE={DEFAULT_ENV['TEMPERATURE']}\n\n")
            
            f.write("# 日志配置\n")
            f.write(f"LOG_LEVEL={DEFAULT_ENV['LOG_LEVEL']}\n")
        
        print(f"{Colors.GREEN}✓ 已创建默认环境变量配置文件: {env_path}{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.RED}✗ 创建默认环境变量配置文件失败: {str(e)}{Colors.ENDC}")

class SystemChecker:
    def __init__(self):
        # 加载环境变量
        env_path = Path(__file__).resolve().parent.parent.parent.parent.parent / '.env'
        if env_path.exists():
            try:
                load_dotenv(env_path)
                print(f"{Colors.GREEN}✓ 成功加载环境变量配置文件{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.YELLOW}⚠ 加载环境变量配置文件失败: {str(e)}，将创建新的配置文件{Colors.ENDC}")
                create_default_env(env_path)
                load_dotenv(env_path)
        else:
            print(f"{Colors.YELLOW}⚠ 未找到环境变量配置文件，将创建新的配置文件{Colors.ENDC}")
            create_default_env(env_path)
            load_dotenv(env_path)
        
        # 初始化检查结果
        self.check_results = {
            'database': False,
            'disk_space': False,
            'memory': False,
            'cpu': False
        }

        # 打印当前配置
        db_config = {
            'host': os.getenv('POSTGRES_HOST', DEFAULT_ENV['POSTGRES_HOST']),
            'port': os.getenv('POSTGRES_PORT', DEFAULT_ENV['POSTGRES_PORT']),
            'user': os.getenv('POSTGRES_USER', DEFAULT_ENV['POSTGRES_USER']),
            'password': os.getenv('POSTGRES_PASSWORD', DEFAULT_ENV['POSTGRES_PASSWORD']),
            'database': os.getenv('POSTGRES_DB', DEFAULT_ENV['POSTGRES_DB'])
        }
        print(f"\n{Colors.BLUE}数据库配置:{Colors.ENDC}")
        print(f"  {Colors.BOLD}host:{Colors.ENDC} {db_config['host']}")
        print(f"  {Colors.BOLD}port:{Colors.ENDC} {db_config['port']}")
        print(f"  {Colors.BOLD}user:{Colors.ENDC} {db_config['user']}")
        print(f"  {Colors.BOLD}password:{Colors.ENDC} {db_config['password']}")
        print(f"  {Colors.BOLD}database:{Colors.ENDC} {db_config['database']}")

    def check_database(self) -> Tuple[bool, str]:
        """检查数据库连接"""
        try:
            # 使用统一的数据库引擎测试连接
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            print(f"\n{Colors.GREEN}✓ 数据库连接成功{Colors.ENDC}")
            return True, "数据库连接成功"
        except SQLAlchemyError as e:
            if "could not connect to server" in str(e):
                error_msg = f"{Colors.RED}✗ PostgreSQL服务器未运行或无法连接，请确保PostgreSQL已安装并运行{Colors.ENDC}"
                print(f"\n{error_msg}")
                return False, error_msg
            elif "database" in str(e) and "does not exist" in str(e):
                error_msg = f"{Colors.RED}✗ 数据库不存在，请先创建数据库{Colors.ENDC}"
                print(f"\n{error_msg}")
                return False, error_msg
            else:
                error_msg = f"{Colors.RED}✗ 数据库连接失败: {str(e)}{Colors.ENDC}"
                print(f"\n{error_msg}")
                return False, error_msg
        except Exception as e:
            error_msg = f"{Colors.RED}✗ 数据库检查出错: {str(e)}{Colors.ENDC}"
            print(f"\n{error_msg}")
            return False, error_msg

    def check_disk_space(self) -> Tuple[bool, str]:
        """检查磁盘空间"""
        try:
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                error_msg = f"{Colors.RED}✗ 磁盘空间不足: {disk.percent}%{Colors.ENDC}"
                print(f"\n{error_msg}")
                return False, error_msg
            print(f"\n{Colors.GREEN}✓ 磁盘空间充足: {disk.percent}%{Colors.ENDC}")
            return True, f"磁盘空间充足: {disk.percent}%"
        except Exception as e:
            error_msg = f"{Colors.RED}✗ 磁盘空间检查出错: {str(e)}{Colors.ENDC}"
            print(f"\n{error_msg}")
            return False, error_msg

    def check_memory(self) -> Tuple[bool, str]:
        """检查内存使用情况"""
        try:
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                error_msg = f"{Colors.RED}✗ 内存使用率过高: {memory.percent}%{Colors.ENDC}"
                print(f"\n{error_msg}")
                return False, error_msg
            print(f"\n{Colors.GREEN}✓ 内存使用正常: {memory.percent}%{Colors.ENDC}")
            return True, f"内存使用正常: {memory.percent}%"
        except Exception as e:
            error_msg = f"{Colors.RED}✗ 内存检查出错: {str(e)}{Colors.ENDC}"
            print(f"\n{error_msg}")
            return False, error_msg

    def check_cpu(self) -> Tuple[bool, str]:
        """检查CPU使用情况"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                error_msg = f"{Colors.RED}✗ CPU使用率过高: {cpu_percent}%{Colors.ENDC}"
                print(f"\n{error_msg}")
                return False, error_msg
            print(f"\n{Colors.GREEN}✓ CPU使用正常: {cpu_percent}%{Colors.ENDC}")
            return True, f"CPU使用正常: {cpu_percent}%"
        except Exception as e:
            error_msg = f"{Colors.RED}✗ CPU检查出错: {str(e)}{Colors.ENDC}"
            print(f"\n{error_msg}")
            return False, error_msg

    def run_all_checks(self):
        """运行所有检查"""
        print(f"\n{Colors.BLUE}开始系统检查...{Colors.ENDC}")
        
        # 按顺序检查各项服务
        checks = [
            ('database', self.check_database),
            ('disk_space', self.check_disk_space),
            ('memory', self.check_memory),
            ('cpu', self.check_cpu)
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            print(f"\n{Colors.BLUE}检查 {check_name}...{Colors.ENDC}")
            result = check_func()
            self.check_results[check_name] = result
            
            if not result[0]:
                all_passed = False
                if check_name == 'database':
                    print(f"\n{Colors.YELLOW}⚠ 数据库问题解决建议：{Colors.ENDC}")
                    print(f"{Colors.YELLOW}1. 确保PostgreSQL已安装并运行{Colors.ENDC}")
                    print(f"{Colors.YELLOW}2. 检查数据库配置是否正确{Colors.ENDC}")
                    print(f"{Colors.YELLOW}3. 如果数据库不存在，请先创建数据库{Colors.ENDC}")
                    print(f"{Colors.YELLOW}4. 检查数据库用户权限{Colors.ENDC}")
                    print(f"\n{Colors.YELLOW}请在.env文件中配置以下环境变量：{Colors.ENDC}")
                    print(f"{Colors.YELLOW}POSTGRES_HOST=localhost{Colors.ENDC}")
                    print(f"{Colors.YELLOW}POSTGRES_PORT=5432{Colors.ENDC}")
                    print(f"{Colors.YELLOW}POSTGRES_USER=your_username{Colors.ENDC}")
                    print(f"{Colors.YELLOW}POSTGRES_PASSWORD=your_password{Colors.ENDC}")
                    print(f"{Colors.YELLOW}POSTGRES_DB=your_database{Colors.ENDC}")
        
        if all_passed:
            print(f"\n{Colors.GREEN}✓ 所有服务检查通过！{Colors.ENDC}")
        else:
            print(f"\n{Colors.RED}✗ 部分服务检查未通过，请查看上述错误信息{Colors.ENDC}")

    def print_summary(self):
        """打印检查结果摘要"""
        self.run_all_checks()

# 创建全局实例
system_checker = SystemChecker() 