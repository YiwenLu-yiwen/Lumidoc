import os
import logging
import sys
from src.shared.logger import initialize_logging, get_logger
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
import psutil
from dotenv import load_dotenv
import subprocess
from neo4j import GraphDatabase

# 配置日志
initialize_logging("system_check")
logger = get_logger(__name__)

# 默认配置
DEFAULT_CONFIG = {
    'database': {
        'host': 'localhost',
        'port': 5432,
        'user': 'stpuser',
        'password': 'stppassword',
        'database': 'stpdb'
    },
    'neo4j': {
        'uri': 'bolt://localhost:7687',
        'user': 'neo4j',
        'password': '123456789'
    }
}

class SystemChecker:
    def __init__(self):
        # 加载环境变量
        env_path = Path(__file__).resolve().parent.parent.parent.parent / '.env'
        if env_path.exists():
            try:
                load_dotenv(dotenv_path=env_path)
                logger.info("成功加载环境变量配置文件")
            except Exception as e:
                logger.warning(f"加载环境变量配置文件失败: {str(e)}，将使用默认配置")
        else:
            logger.warning("未找到环境变量配置文件，将使用默认配置")
        
        # 初始化检查结果
        self.check_results = {
            'database': False,
            'neo4j': False,
            'disk_space': False,
            'memory': False,
            'cpu': False
        }
        
        # 检查是否直接提供了POSTGRES_URL
        self.postgres_url = os.getenv('POSTGRES_URL')
        
        # 初始化数据库配置
        self.db_config = {
            'host': os.getenv('POSTGRES_HOST') or DEFAULT_CONFIG['database']['host'],
            'port': int(os.getenv('POSTGRES_PORT', str(DEFAULT_CONFIG['database']['port']))),
            'user': os.getenv('POSTGRES_USER') or DEFAULT_CONFIG['database']['user'],
            'password': os.getenv('POSTGRES_PASSWORD') or DEFAULT_CONFIG['database']['password'],
            'database': os.getenv('POSTGRES_DB') or DEFAULT_CONFIG['database']['database']
        }
        
        # 初始化Neo4j配置
        self.neo4j_config = {
            'uri': os.getenv('NEO4J_URI') or DEFAULT_CONFIG['neo4j']['uri'],
            'user': os.getenv('NEO4J_USER') or DEFAULT_CONFIG['neo4j']['user'],
            'password': os.getenv('NEO4J_PASSWORD') or DEFAULT_CONFIG['neo4j']['password']
        }
        
        # 打印当前配置
        self._print_config_tree()

    def _print_config_tree(self):
        """以树状图形式打印配置信息"""
        logger.info("当前系统配置:")
        logger.info("├── PostgreSQL")
        if self.postgres_url:
            logger.info("│   └── 使用完整URL连接: %s", self.postgres_url.split("@")[1] if "@" in self.postgres_url else "已配置")
        else:
            logger.info("│   ├── host: %s", self.db_config['host'])
            logger.info("│   ├── port: %s", self.db_config['port'])
            logger.info("│   ├── user: %s", self.db_config['user'])
            logger.info("│   ├── password: %s", self.db_config['password'])
            logger.info("│   └── database: %s", self.db_config['database'])
        logger.info("└── Neo4j")
        logger.info("    ├── uri: %s", self.neo4j_config['uri'])
        logger.info("    ├── user: %s", self.neo4j_config['user'])
        logger.info("    └── password: %s", self.neo4j_config['password'])

    def check_neo4j(self) -> Tuple[bool, str]:
        """检查Neo4j连接"""
        try:
            driver = GraphDatabase.driver(
                self.neo4j_config['uri'],
                auth=(self.neo4j_config['user'], self.neo4j_config['password'])
            )
            # 测试连接
            with driver.session() as session:
                result = session.run("RETURN 1 as n")
                result.single()
            driver.close()
            return True, "Neo4j连接成功"
        except Exception as e:
            error_msg = f"Neo4j连接失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def check_postgres_installed(self) -> bool:
        """检查PostgreSQL是否已安装"""
        try:
            result = subprocess.run(['which', 'psql'], capture_output=True, text=True)
            return result.returncode == 0
        except Exception:
            return False

    def check_postgres_running(self) -> bool:
        """检查PostgreSQL服务是否正在运行"""
        try:
            # 优先检查Docker容器
            try:
                import subprocess
                result = subprocess.run(['docker', 'ps', '--filter', 'ancestor=postgres', '--format', '{{.Names}}'],
                                      capture_output=True, text=True)
                if result.stdout.strip():
                    # 检查到PostgreSQL Docker镜像运行的容器
                    logger.info(f"检测到PostgreSQL Docker容器正在运行: {result.stdout.strip()}")
                    return True
                    
                # 使用name过滤器再次检查
                result = subprocess.run(['docker', 'ps', '--filter', 'name=postgres', '--format', '{{.Names}}'],
                                      capture_output=True, text=True)
                if result.stdout.strip():
                    logger.info(f"检测到PostgreSQL Docker容器正在运行: {result.stdout.strip()}")
                    return True
            except Exception as e:
                logger.debug(f"检查Docker容器时出错: {str(e)}")
                
            # 尝试直接连接PostgreSQL
            if self.postgres_url:
                # 使用完整URL连接
                conn = psycopg2.connect(self.postgres_url, connect_timeout=3)
            else:
                conn = psycopg2.connect(
                    host=self.db_config['host'],
                    port=self.db_config['port'],
                    user=self.db_config['user'],
                    password=self.db_config['password'],
                    # 连接到默认的postgres数据库
                    database='postgres',
                    # 设置短连接超时
                    connect_timeout=3
                )
            conn.close()
            return True
        except Exception as e:
            logger.debug(f"直接连接PostgreSQL失败: {str(e)}")
            return False

    def check_database(self) -> Tuple[bool, str]:
        """检查数据库连接"""
        # 如果Docker中运行了PostgreSQL，我们认为服务是可用的
        postgres_running = self.check_postgres_running()
        
        if not postgres_running and not self.check_postgres_installed():
            error_msg = "PostgreSQL未安装且服务未运行，请安装或启动PostgreSQL"
            logger.error(error_msg)
            return False, error_msg
            
        try:
            # 使用sqlalchemy创建连接，以适应更多环境
            if self.postgres_url:
                conn_str = self.postgres_url
                logger.info("使用POSTGRES_URL环境变量中的完整连接URL")
            else:
                conn_str = f"postgresql://{self.db_config['user']}:{self.db_config['password']}@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
                logger.info("使用组合的数据库连接参数")
                
            engine = create_engine(conn_str, connect_args={'connect_timeout': 5})
            
            try:
                connection = engine.connect()
                connection.close()
                logger.info("数据库连接测试成功")
                return True, "PostgreSQL连接成功"
            except Exception as conn_e:
                logger.warning(f"SQLAlchemy连接失败，尝试使用psycopg2: {str(conn_e)}")
                # 尝试直接使用psycopg2作为备选
                try:
                    if self.postgres_url:
                        conn = psycopg2.connect(self.postgres_url, connect_timeout=5)
                    else:
                        conn = psycopg2.connect(
                            host=self.db_config['host'],
                            port=self.db_config['port'],
                            user=self.db_config['user'],
                            password=self.db_config['password'],
                            database=self.db_config['database'],
                            connect_timeout=5
                        )
                    conn.close()
                    logger.info("psycopg2数据库连接测试成功")
                    return True, "PostgreSQL连接成功"
                except Exception as psycopg_e:
                    logger.error(f"psycopg2连接也失败: {str(psycopg_e)}")
                    raise conn_e
                
        except SQLAlchemyError as e:
            if "database" in str(e).lower() and "does not exist" in str(e).lower():
                logger.warning(f"数据库 {self.db_config['database']} 不存在，尝试创建")
                # 尝试连接到默认数据库，然后创建项目数据库
                try:
                    if self.postgres_url:
                        # 从URL中提取主机部分
                        url_parts = self.postgres_url.rsplit('/', 1)
                        default_conn_str = f"{url_parts[0]}/postgres"
                    else:
                        default_conn_str = f"postgresql://{self.db_config['user']}:{self.db_config['password']}@{self.db_config['host']}:{self.db_config['port']}/postgres"
                    
                    default_engine = create_engine(default_conn_str)
                    with default_engine.connect() as conn:
                        # 需要提交事务，CREATE DATABASE不能在事务中执行
                        conn.execute("COMMIT")
                        db_name = self.db_config['database']
                        if self.postgres_url:
                            # 从URL提取数据库名
                            db_name = self.postgres_url.rsplit('/', 1)[-1].split('?')[0]
                        
                        conn.execute(f"CREATE DATABASE {db_name}")
                    logger.info(f"成功创建数据库 {db_name}")
                    return True, f"数据库 {db_name} 已创建并连接成功"
                except Exception as create_e:
                    error_msg = f"数据库不存在且无法创建: {str(create_e)}"
                    logger.error(error_msg)
                    return False, error_msg
            else:
                error_msg = f"PostgreSQL连接失败: {str(e)}"
                logger.error(error_msg)
                return False, error_msg
        except Exception as e:
            error_msg = f"数据库检查出错: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def check_disk_space(self) -> Tuple[bool, str]:
        """检查磁盘空间"""
        try:
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                error_msg = f"磁盘空间不足: {disk.percent}%"
                logger.error(error_msg)
                return False, error_msg
            return True, f"磁盘空间充足: {disk.percent}%"
        except Exception as e:
            error_msg = f"磁盘空间检查出错: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def check_memory(self) -> Tuple[bool, str]:
        """检查内存使用情况"""
        try:
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                error_msg = f"内存使用率过高: {memory.percent}%"
                logger.error(error_msg)
                return False, error_msg
            return True, f"内存使用正常: {memory.percent}%"
        except Exception as e:
            error_msg = f"内存检查出错: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def check_cpu(self) -> Tuple[bool, str]:
        """检查CPU使用情况"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                error_msg = f"CPU使用率过高: {cpu_percent}%"
                logger.error(error_msg)
                return False, error_msg
            return True, f"CPU使用正常: {cpu_percent}%"
        except Exception as e:
            error_msg = f"CPU检查出错: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def run_all_checks(self):
        """运行所有检查"""
        print("\n开始系统检查...")
        
        # 按顺序检查各项服务
        checks = [
            ('database', self.check_database),
            ('neo4j', self.check_neo4j),
            ('disk_space', self.check_disk_space),
            ('memory', self.check_memory),
            ('cpu', self.check_cpu)
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            print(f"\n检查 {check_name}...")
            result = check_func()
            self.check_results[check_name] = result
            status = "✅" if result[0] else "❌"
            print(f"{status} {check_name}: {result[1]}")
            
            if not result[0]:
                all_passed = False
                print("\n⚠️ 服务检查未通过")
                if check_name == 'database':
                    print("\nPostgreSQL问题解决建议：")
                    print("1. 确保PostgreSQL已安装并运行")
                    print("2. 检查数据库配置是否正确")
                    print("3. 如果数据库不存在，请先创建数据库")
                    print("4. 检查数据库用户权限")
                elif check_name == 'neo4j':
                    print("\nNeo4j问题解决建议：")
                    print("1. 确保Neo4j服务已启动")
                    print("2. 检查Neo4j配置是否正确")
                    print("3. 检查Neo4j用户权限")
                    print("4. 确保Neo4j端口可访问")
        
        if all_passed:
            print("\n✅ 所有服务检查通过！")
        else:
            print("\n⚠️ 部分服务检查未通过，请查看上述错误信息")

    def print_summary(self):
        """打印检查结果摘要"""
        self.run_all_checks()

# 创建全局实例
system_checker = SystemChecker() 