import os
import jwt
import bcrypt
from datetime import timedelta
from typing import Optional, Union
import asyncpg

from .user_model import User, UserCreate
from .config.config import settings
import asyncio
from src.shared.jwt_utils import create_jwt_token
from src.shared.logger import initialize_logging, get_logger
from src.shared.time_utils import utc_now, utc_now_naive

# 配置日志
initialize_logging("auth_service")
logger = get_logger(__name__)

class BcryptPasswordContext:
    """Minimal password context backed by the maintained bcrypt package."""

    def hash(self, password: str) -> str:
        password_bytes = password.encode("utf-8")
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")

    def verify(self, password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), hashed_password.encode("utf-8")
            )
        except (TypeError, ValueError):
            return False


pwd_context = BcryptPasswordContext()
logger.info("bcrypt版本: %s", getattr(bcrypt, "__version__", "unknown"))

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
                raise RuntimeError("JWT签名密钥未配置")
            logger.info("JWT签名密钥加载成功")
            
            self.public_key = get_public_key(force_reload=True)
            if not self.public_key:
                raise RuntimeError("JWT验证密钥未配置")
            logger.info("JWT验证密钥加载成功")
            
            # 验证密钥对是否匹配
            self._validate_key_pair()
        except Exception as e:
            logger.error(f"JWT密钥加载失败: {str(e)}")
            raise RuntimeError(f"无法加载JWT密钥: {str(e)}")
    
    def _validate_key_pair(self):
        """验证公钥和私钥是否匹配"""
        try:
            # 创建测试数据
            test_data = {"test": "data", "time": utc_now().isoformat()}
            
            # 使用私钥签名
            token = jwt.encode(test_data, self.private_key, algorithm=settings.JWT_ALGORITHM)
            
            # 使用公钥验证
            try:
                jwt.decode(token, self.public_key, algorithms=[settings.JWT_ALGORITHM])
                logger.info("JWT密钥对验证成功")
            except Exception as e:
                logger.error(f"JWT密钥对验证失败: {str(e)}")
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
            expire = utc_now() + expires_delta
        else:
            expire = utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
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
            
            if not user or not user['is_active']:
                return None
            if not self.verify_password(password, user['hashed_password']):
                return None
            current_time = utc_now_naive()
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

    async def change_password(
        self, username: str, current_password: str, new_password: str
    ) -> bool:
        """验证当前凭据后更新密码。"""
        user = await self.authenticate_user(username, current_password)
        if user is None:
            return False

        hashed_password = self.get_password_hash(new_password)
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE users
                SET hashed_password = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
                """,
                hashed_password,
                user.id,
            )
        return result == "UPDATE 1"
    
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
        current_time = utc_now_naive()
        
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
