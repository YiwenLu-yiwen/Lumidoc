"""
错误代码枚举
定义系统中所有可能的错误类型
"""

from enum import Enum, auto

class ErrorCode(Enum):
    """标准化错误代码枚举"""
    
    # 通用错误 (1000-1999)
    UNKNOWN_ERROR = 1000
    INVALID_REQUEST = 1001
    SERVICE_UNAVAILABLE = 1002
    TIMEOUT = 1003
    
    # 认证与授权错误 (2000-2999)
    AUTHENTICATION_FAILED = 2000
    TOKEN_EXPIRED = 2001
    TOKEN_INVALID = 2002
    PERMISSION_DENIED = 2003
    
    # 资源相关错误 (3000-3999)
    NOT_FOUND = 3000
    ALREADY_EXISTS = 3001
    RESOURCE_LOCKED = 3002
    
    # 验证错误 (4000-4999)
    VALIDATION_ERROR = 4000
    SCHEMA_ERROR = 4001
    
    # 文件操作错误 (5000-5999)
    FILE_NOT_FOUND = 5000
    FILE_ACCESS_DENIED = 5001
    FILE_TOO_LARGE = 5002
    INVALID_FILE_FORMAT = 5003
    
    # 数据库错误 (6000-6999)
    DATABASE_ERROR = 6000
    QUERY_ERROR = 6001
    CONNECTION_ERROR = 6002
    
    # LLM相关错误 (7000-7999)
    LLM_REQUEST_FAILED = 7000
    LLM_RESPONSE_ERROR = 7001
    LLM_RATE_LIMIT = 7002
    
    # RAG相关错误 (8000-8999)
    RAG_INDEXING_ERROR = 8000
    RAG_QUERY_ERROR = 8001
    
    @property
    def message(self) -> str:
        """返回错误代码对应的默认消息"""
        messages = {
            # 通用错误
            self.UNKNOWN_ERROR: "未知错误",
            self.INVALID_REQUEST: "无效请求",
            self.SERVICE_UNAVAILABLE: "服务不可用",
            self.TIMEOUT: "请求超时",
            
            # 认证与授权错误
            self.AUTHENTICATION_FAILED: "认证失败",
            self.TOKEN_EXPIRED: "令牌已过期",
            self.TOKEN_INVALID: "无效的令牌",
            self.PERMISSION_DENIED: "权限不足",
            
            # 资源相关错误
            self.NOT_FOUND: "资源未找到",
            self.ALREADY_EXISTS: "资源已存在",
            self.RESOURCE_LOCKED: "资源已锁定",
            
            # 验证错误
            self.VALIDATION_ERROR: "数据验证失败",
            self.SCHEMA_ERROR: "数据模式错误",
            
            # 文件操作错误
            self.FILE_NOT_FOUND: "文件未找到",
            self.FILE_ACCESS_DENIED: "文件访问被拒绝",
            self.FILE_TOO_LARGE: "文件过大",
            self.INVALID_FILE_FORMAT: "无效的文件格式",
            
            # 数据库错误
            self.DATABASE_ERROR: "数据库错误",
            self.QUERY_ERROR: "查询错误",
            self.CONNECTION_ERROR: "连接错误",
            
            # LLM相关错误
            self.LLM_REQUEST_FAILED: "LLM请求失败",
            self.LLM_RESPONSE_ERROR: "LLM响应错误",
            self.LLM_RATE_LIMIT: "LLM请求达到速率限制",
            
            # RAG相关错误
            self.RAG_INDEXING_ERROR: "RAG索引错误",
            self.RAG_QUERY_ERROR: "RAG查询错误",
        }
        return messages.get(self, f"错误代码: {self.value}")
    
    @property
    def http_status(self) -> int:
        """返回错误代码对应的HTTP状态码"""
        status_map = {
            # 通用错误
            self.UNKNOWN_ERROR: 500,
            self.INVALID_REQUEST: 400,
            self.SERVICE_UNAVAILABLE: 503,
            self.TIMEOUT: 504,
            
            # 认证与授权错误
            self.AUTHENTICATION_FAILED: 401,
            self.TOKEN_EXPIRED: 401,
            self.TOKEN_INVALID: 401,
            self.PERMISSION_DENIED: 403,
            
            # 资源相关错误
            self.NOT_FOUND: 404,
            self.ALREADY_EXISTS: 409,
            self.RESOURCE_LOCKED: 423,
            
            # 验证错误
            self.VALIDATION_ERROR: 422,
            self.SCHEMA_ERROR: 422,
            
            # 文件操作错误
            self.FILE_NOT_FOUND: 404,
            self.FILE_ACCESS_DENIED: 403,
            self.FILE_TOO_LARGE: 413,
            self.INVALID_FILE_FORMAT: 415,
            
            # 数据库错误
            self.DATABASE_ERROR: 500,
            self.QUERY_ERROR: 500,
            self.CONNECTION_ERROR: 503,
            
            # LLM相关错误
            self.LLM_REQUEST_FAILED: 502,
            self.LLM_RESPONSE_ERROR: 502,
            self.LLM_RATE_LIMIT: 429,
            
            # RAG相关错误
            self.RAG_INDEXING_ERROR: 500,
            self.RAG_QUERY_ERROR: 500,
        }
        return status_map.get(self, 500)  # 默认使用500内部服务器错误 