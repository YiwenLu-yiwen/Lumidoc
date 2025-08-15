import os
import jwt
import warnings
from datetime import datetime, timedelta
from typing import Optional, Union
import asyncpg

# 抑制bcrypt版本警告
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=UserWarning, module="passlib.*")
    from passlib.context import CryptContext

from .user_model import User, UserCreate, UserInDB
from .config.config import settings
import asyncio
import logging
from src.shared.jwt_utils import create_jwt_token, get_private_key, get_public_key
from src.shared.logger import initialize_logging, get_logger

# 配置日志
initialize_logging("auth_service")
logger = get_logger(__name__)

# 修复bcrypt版本问题
def get_crypt_context():
    """获取加密上下文，处理各种bcrypt版本兼容性问题"""
    try:
        # 首先尝试导入bcrypt，确定版本
        import bcrypt
        bcrypt_version = getattr(bcrypt, "__version__", None)
        if not bcrypt_version:
            # 新版本bcrypt没有__about__.__version__属性
            logger.info(f"使用兼容模式初始化CryptContext，当前bcrypt版本无法通过常规方式确定")
        else:
            logger.info(f"bcrypt版本: {bcrypt_version}")
        
        # 使用安全的配置初始化CryptContext
        context = CryptContext(
            schemes=["bcrypt"],
            bcrypt__rounds=12,
            bcrypt__ident="2b",
            deprecated="auto"
        )
        
        # 测试加密和验证功能是否正常工作
        test_password = "test_password_for_verification"
        test_hash = context.hash(test_password)
        if not context.verify(test_password, test_hash):
            raise ValueError("CryptContext验证测试失败")
            
        logger.info("已使用兼容模式初始化CryptContext")
        return context
        
    except Exception as e:
        logger.error(f"标准CryptContext初始化失败: {str(e)}")
        # 实现备用加密方案 - 直接使用bcrypt库
        try:
            import bcrypt
            
            class CustomBcryptContext:
                """自定义bcrypt上下文，直接使用bcrypt库而不依赖passlib的包装"""
                def hash(self, password: str) -> str:
                    """对密码进行哈希"""
                    if isinstance(password, str):
                        password = password.encode('utf-8')
                    salt = bcrypt.gensalt(rounds=12)
                    hashed = bcrypt.hashpw(password, salt)
                    return hashed.decode('utf-8')
                
                def verify(self, password: str, hash: str) -> bool:
                    """验证密码是否匹配哈希值"""
                    if isinstance(password, str):
                        password = password.encode('utf-8')
                    if isinstance(hash, str):
                        hash = hash.encode('utf-8')
                    try:
                        return bcrypt.checkpw(password, hash)
                    except Exception as verify_err:
                        logger.error(f"验证密码时出错: {str(verify_err)}")
                        return False
            
            # 创建并测试自定义上下文
            custom_context = CustomBcryptContext()
            test_password = "test_password_for_verification"
            test_hash = custom_context.hash(test_password)
            if not custom_context.verify(test_password, test_hash):
                raise ValueError("自定义加密上下文验证测试失败")
                
            logger.info("已使用自定义bcrypt封装初始化CryptContext")
            return custom_context
            
        except Exception as backup_err:
            logger.critical(f"所有CryptContext初始化方法都失败: {str(backup_err)}")
            raise RuntimeError("无法初始化密码加密系统，这会导致认证功能无法使用") from backup_err

# 初始化密码上下文
pwd_context = get_crypt_context()

class AuthService:
    def __init__(self):
        self.db_pool = None
        self._lock = asyncio.Lock()  # 添加锁以防止并发初始化
        
        # 使用共享JWT工具获取密钥
        try:
            # 从jwt_utils导入获取密钥函数
            from src.shared.jwt_utils import get_private_key, get_public_key
            
            # 强制重新加载密钥，确保最新
            self.private_key = get_private_key(force_reload=True)
            if not self.private_key:
                # 备用方案：直接读取文件
                with open(settings.jwt_private_key_path, "r") as f:
                    self.private_key = f.read().strip()
                logger.info(f"直接从文件加载JWT私钥: {settings.jwt_private_key_path}")
            else:
                logger.info(f"使用jwt_utils加载JWT私钥")
            
            self.public_key = get_public_key(force_reload=True)
            if not self.public_key:
                # 备用方案：直接读取文件
                with open(settings.jwt_public_key_path, "r") as f:
                    self.public_key = f.read().strip()
                logger.info(f"直接从文件加载JWT公钥: {settings.jwt_public_key_path}")
            else:
                logger.info(f"使用jwt_utils加载JWT公钥")
            
            # 验证密钥对是否匹配
            self._validate_key_pair()
        except Exception as e:
            logger.error(f"JWT密钥加载失败: {str(e)}")
            raise RuntimeError(f"无法加载JWT密钥: {str(e)}")
    
    def _validate_key_pair(self):
        """验证公钥和私钥是否匹配"""
        try:
            # 创建测试数据
            test_data = {"test": "data", "time": str(datetime.utcnow())}
            
            # 使用私钥签名
            token = jwt.encode(test_data, self.private_key, algorithm=settings.JWT_ALGORITHM)
            
            # 使用公钥验证
            try:
                decoded = jwt.decode(token, self.public_key, algorithms=[settings.JWT_ALGORITHM])
                logger.info("JWT密钥对验证成功")
            except Exception as e:
                logger.error(f"JWT密钥对验证失败: {str(e)}")
                # 记录密钥信息（不包含完整内容）
                if self.private_key and self.public_key:
                    priv_len = len(self.private_key)
                    pub_len = len(self.public_key)
                    logger.error(f"私钥长度: {priv_len}, 公钥长度: {pub_len}")
                    logger.error(f"私钥前10字符: {self.private_key[:10]}...")
                    logger.error(f"公钥前10字符: {self.public_key[:10]}...")
                raise ValueError(f"JWT密钥对不匹配: {str(e)}")
        except Exception as e:
            logger.error(f"验证JWT密钥对时出错: {str(e)}")
            raise
    
    async def _init_db_pool(self):
        """初始化数据库连接池"""
        async with self._lock:  # 使用锁确保只初始化一次
            if self.db_pool is not None:
                return
                
            # 直接使用 postgresql://
            database_url = os.getenv('DATABASE_URL', '')
            if not database_url:
                database_url = f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
            
            logger.info(f"使用数据库连接: {database_url.replace(settings.db_password, '******')}")
            
            try:
                self.db_pool = await asyncpg.create_pool(
                    database_url,
                    min_size=5,      # 最小连接数
                    max_size=20,     # 最大连接数
                    command_timeout=30.0,  # 命令超时时间
                    max_inactive_connection_lifetime=60.0,  # 非活动连接的最大生命周期
                    max_queries=50000,  # 每个连接最大查询次数
                    max_cached_statement_lifetime=300.0,  # 缓存语句的最大生命周期
                    statement_cache_size=100  # 语句缓存大小
                )
                
                # 创建用户表
                async with self.db_pool.acquire() as conn:
                    await conn.execute('''
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            username TEXT UNIQUE NOT NULL,
                            email TEXT UNIQUE,
                            hashed_password TEXT NOT NULL,
                            nickname TEXT,
                            is_active BOOLEAN DEFAULT TRUE,
                            is_superuser BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    
                    # 检查email列是否为NOT NULL，如果是则修改为可为NULL
                    constraints = await conn.fetch('''
                        SELECT column_name, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = 'users' AND column_name = 'email'
                    ''')
                    
                    if constraints and constraints[0]['is_nullable'] == 'NO':
                        logger.info("修改email字段为可空")
                        await conn.execute('ALTER TABLE users ALTER COLUMN email DROP NOT NULL')
                
                logger.info("数据库连接池初始化成功")
            except Exception as e:
                logger.error(f"数据库连接池初始化失败: {str(e)}")
                raise
    
    async def close(self):
        """关闭数据库连接池"""
        if self.db_pool:
            await self.db_pool.close()
            self.db_pool = None
            logger.info("数据库连接池已关闭")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """获取密码哈希"""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """创建访问令牌"""
        # 尝试使用统一JWT工具
        token = create_jwt_token(data, expires_delta)
        if token:
            return token
        
        # 备用方案：使用原有实现
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        
        # 确保sub字段是字符串类型
        if "sub" in to_encode and not isinstance(to_encode["sub"], str):
            to_encode["sub"] = str(to_encode["sub"])
            
        encoded_jwt = jwt.encode(to_encode, self.private_key, algorithm=settings.JWT_ALGORITHM)
        if isinstance(encoded_jwt, bytes):
            encoded_jwt = encoded_jwt.decode('utf-8')
        return encoded_jwt
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """验证用户 - 支持用户名或邮箱登录"""
        if self.db_pool is None:
            await self._init_db_pool()
        
        async with self.db_pool.acquire() as conn:
            # 首先尝试通过用户名查找
            user = await conn.fetchrow(
                'SELECT * FROM users WHERE username = $1',
                username
            )
            
            # 如果用户名未找到，尝试通过邮箱查找
            if not user and '@' in username:
                user = await conn.fetchrow(
                    'SELECT * FROM users WHERE email = $1',
                    username
                )
            
            if not user:
                return None
            if not self.verify_password(password, user['hashed_password']):
                return None
            current_time = datetime.utcnow()
            return User(
                id=user['id'],
                username=user['username'],
                email=user['email'],
                nickname=user['nickname'],
                is_active=user['is_active'],
                is_superuser=user['is_superuser'],
                created_at=user['created_at'],
                updated_at=current_time
            )
    
    async def create_user(self, user: UserCreate) -> User:
        """创建用户"""
        if self.db_pool is None:
            await self._init_db_pool()
        
        # 验证必填字段
        if not user.email:
            raise ValueError("邮箱地址是必填项")
        
        hashed_password = self.get_password_hash(user.password)
        nickname = user.nickname if user.nickname else "momo"  # 自动补默认昵称
        email = user.email  # 现在必须有值
        current_time = datetime.utcnow()
        
        logger.info(f"创建用户: username={user.username}, email={email}, nickname={nickname}")
        
        async with self.db_pool.acquire() as conn:
            try:
                # 使用RETURNING id来获取自动生成的id
                new_user = await conn.fetchrow('''
                    INSERT INTO users (username, email, hashed_password, nickname, is_active, is_superuser, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING *
                ''', user.username, email, hashed_password, nickname, user.is_active, user.is_superuser, current_time, current_time)
                
                logger.info(f"用户创建成功: id={new_user['id']}, username={new_user['username']}")
                
                return User(
                    id=new_user['id'],
                    username=new_user['username'],
                    email=new_user['email'],
                    nickname=new_user['nickname'],
                    is_active=new_user['is_active'],
                    is_superuser=new_user['is_superuser'],
                    created_at=new_user['created_at'],
                    updated_at=new_user['updated_at']
                )
            except Exception as e:
                logger.error(f"创建用户失败: {str(e)}")
                if "duplicate key" in str(e).lower():
                    if "username" in str(e).lower():
                        raise ValueError("用户名已存在")
                    elif "email" in str(e).lower():
                        raise ValueError("邮箱已存在")
                raise
    
    async def get_user(self, user_id: Union[int, str]) -> Optional[User]:
        """获取用户"""
        if self.db_pool is None:
            await self._init_db_pool()
        
        # 确保user_id是整数类型
        try:
            # 如果传入的是字符串，尝试转换为整数
            if isinstance(user_id, str) and user_id.isdigit():
                user_id = int(user_id)
            elif isinstance(user_id, str):
                logger.error(f"无法将user_id '{user_id}'转换为整数")
                raise ValueError(f"无效的用户ID格式: {user_id}")
        except ValueError as e:
            logger.error(f"转换user_id时出错: {str(e)}")
            raise
        
        logger.debug(f"查询用户ID: {user_id}, 类型: {type(user_id)}")
        
        async with self.db_pool.acquire() as conn:
            user = await conn.fetchrow(
                'SELECT * FROM users WHERE id = $1',
                user_id
            )
            if not user:
                return None
            return User(
                id=user['id'],
                username=user['username'],
                email=user['email'],
                nickname=user['nickname'],
                is_active=user['is_active'],
                is_superuser=user['is_superuser'],
                created_at=user['created_at'],
                updated_at=user['updated_at']
            ) 