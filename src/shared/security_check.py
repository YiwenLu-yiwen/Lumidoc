"""
安全配置检查工具

在系统启动时检查关键安全配置，避免安全风险
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
import yaml

# 配置日志
logger = logging.getLogger(__name__)

# 默认安全配置文件路径
SECURITY_CONFIG_PATH = os.environ.get(
    "SECURITY_CONFIG_PATH", 
    str(Path(__file__).resolve().parent.parent.parent / "security_config.yaml")
)

# 关键安全配置项及其推荐值
CRITICAL_SECURITY_SETTINGS = {
    # 关键安全配置：环境变量名 -> (类型, 生产环境推荐值, 是否必须, 描述)
    "JWT_ALGORITHM": (str, "RS256", True, "JWT签名算法，推荐使用RS256"),
    "SECRET_KEY": (str, None, True, "密钥，必须是强密钥且不能是默认值"),
    "ACCESS_TOKEN_EXPIRE_MINUTES": (int, 60, True, "访问令牌有效期，建议不超过60分钟"),
    "DATABASE_URL": (str, None, True, "数据库连接URL，必须配置且不能使用默认密码"),
    "REDIS_PASSWORD": (str, None, False, "Redis密码，生产环境必须设置"),
    "NEO4J_PASSWORD": (str, None, False, "Neo4j密码，生产环境必须设置")
}

# 环境配置
ENV_TYPE = os.environ.get("ENVIRONMENT", "local").lower()
IS_PRODUCTION = ENV_TYPE in ["production", "prod"]

def load_security_config() -> Dict[str, Any]:
    """加载安全配置文件"""
    config_path = Path(SECURITY_CONFIG_PATH)
    if not config_path.exists():
        logger.warning(f"安全配置文件不存在: {config_path}")
        return {}
        
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"无法加载安全配置文件: {e}")
        return {}

def check_security_config() -> Tuple[bool, List[str]]:
    """
    检查关键安全配置
    
    Returns:
        Tuple[bool, List[str]]: (是否通过所有必要检查, 警告消息列表)
    """
    # 加载配置
    load_security_config()
    
    # 检查结果
    all_pass = True
    warnings = []
    
    # 检查每个关键安全配置项
    for env_name, (expected_type, recommended_value, required, description) in CRITICAL_SECURITY_SETTINGS.items():
        value = os.environ.get(env_name)
        
        # 检查项目是否存在
        if value is None:
            if required:
                warnings.append(f"缺少必要的安全配置: {env_name} - {description}")
                all_pass = False
            else:
                warnings.append(f"推荐设置安全配置: {env_name} - {description}")
            continue
            
        # 转换为期望的类型
        try:
            if expected_type is bool:
                value = value.lower() in ["true", "1", "t", "yes", "y"]
            elif expected_type is int:
                value = int(value)
        except ValueError:
            warnings.append(f"安全配置格式错误: {env_name}={value}, 期望类型: {expected_type.__name__}")
            all_pass = False
            continue
            
        # 特殊检查: 令牌验证跳过标志
            all_pass = False
            
        # 特殊检查: 默认Secret Key
        if env_name == "SECRET_KEY" and IS_PRODUCTION:
            default_keys = ["your-local-secret-key-here", "secret", "change-me", "your-secret-key"]
            if any(dk in value.lower() for dk in default_keys) or len(value) < 16:
                warnings.append("严重安全风险: SECRET_KEY 使用默认值或过于简单")
                all_pass = False
                
        # 特殊检查: 默认密码
        if IS_PRODUCTION and env_name in ["POSTGRES_PASSWORD", "REDIS_PASSWORD", "NEO4J_PASSWORD"]:
            default_passwords = ["password", "postgres", "admin", "root", "123456", "neo4j"]
            if value and any(dp in value.lower() for dp in default_passwords):
                warnings.append(f"安全风险: {env_name} 使用默认或弱密码")
                
        # 特殊检查: JWT算法
        if env_name == "JWT_ALGORITHM" and IS_PRODUCTION and value != "RS256":
            warnings.append(f"安全建议: 生产环境推荐使用RS256算法代替 {value}")
    
    # 检查其他安全相关配置
    if IS_PRODUCTION:
        # 检查是否设置了安全连接
        if os.environ.get("DATABASE_URL", "").startswith("postgresql://") and "ssl=true" not in os.environ.get("DATABASE_URL", ""):
            warnings.append("安全建议: 生产环境应使用SSL连接数据库")
            
    return all_pass, warnings

def perform_security_check() -> bool:
    """
    执行安全检查并打印结果
    
    Returns:
        bool: 是否通过所有必要检查
    """
    logger.info(f"执行安全配置检查... (环境: {ENV_TYPE})")
    all_pass, warnings = check_security_config()
    
    if warnings:
        logger.warning(f"安全配置检查发现 {len(warnings)} 个问题:")
        for i, warning in enumerate(warnings, 1):
            logger.warning(f"  {i}. {warning}")
    
    if all_pass:
        logger.info("安全配置检查通过 ✓")
    else:
        logger.warning("安全配置检查未通过 ✗")
        
    return all_pass

if __name__ == "__main__":
    # 配置日志
    from src.shared.logger import initialize_logging, get_logger
    initialize_logging("security_check")
    logger = get_logger(__name__)
    # 执行安全检查
    perform_security_check()
