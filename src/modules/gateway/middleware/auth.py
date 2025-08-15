"""
Gateway认证中间件
"""

import logging
import time
import os
from typing import Dict, List, Optional, Any, Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
import httpx
from src.modules.gateway.config.config import settings

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件"""
    
    def __init__(self, app, exclude_paths: Optional[List[str]] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or settings.auth_exclude_paths
        self.auth_service_url = settings.get_service_url("auth")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        # 检查是否需要认证
        if not settings.auth_enabled:
            return await call_next(request)
        
        # OPTIONS预检请求无需认证，直接放行
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # 检查是否在排除路径中
        if self._is_excluded_path(request.url.path):
            return await call_next(request)
        
        # 执行认证检查
        auth_result = await self._authenticate_request(request)
        
        if not auth_result["success"]:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "认证失败",
                    "message": auth_result["message"]
                },
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS,PATCH",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Allow-Credentials": "true"
                }
            )
        
        # 将用户信息添加到请求头中
        if auth_result.get("user"):
            request.state.user = auth_result["user"]
        
        return await call_next(request)
    
    def _is_excluded_path(self, path: str) -> bool:
        """检查路径是否在排除列表中"""
        for excluded_path in self.exclude_paths:
            # 对于根路径进行精确匹配
            if excluded_path == "/" and path == "/":
                return True
            # 对于其他路径使用前缀匹配
            elif excluded_path != "/" and path.startswith(excluded_path):
                return True
        return False
    
    async def _authenticate_request(self, request: Request) -> Dict[str, Any]:
        """认证请求"""
        try:
            # 获取认证令牌 - 优先从Header获取，其次从查询参数获取
            auth_header = request.headers.get("authorization")
            token_from_query = request.query_params.get("token")
            
            # 如果Header中没有token，尝试从查询参数获取
            if not auth_header and token_from_query:
                auth_header = f"Bearer {token_from_query}"
                logger.info("从查询参数获取认证令牌")
            
            if not auth_header:
                return {
                    "success": False,
                    "message": "缺少认证令牌"
                }
            
            # 🔧 修复：支持服务间认证 - 处理Service格式的认证
            if auth_header.startswith("Service "):
                service_token = auth_header.replace("Service ", "")
                expected_token = os.environ.get("SERVICE_AUTH_TOKEN", "service-token-for-internal-use")
                
                if service_token == expected_token:
                    logger.info("服务间认证成功")
                    return {
                        "success": True,
                        "user": {
                            "id": 0,
                            "username": "system",
                            "email": "system@example.com", 
                            "is_active": True,
                            "is_superuser": True
                        },
                        "message": "服务间认证成功"
                    }
                else:
                    logger.warning(f"服务间认证失败: 令牌不匹配")
                    return {
                        "success": False,
                        "message": "服务间认证令牌无效"
                    }
            
            # 处理用户Bearer认证
            elif auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
                
                # 调用认证服务验证令牌
                if not self.auth_service_url:
                    logger.error("未配置认证服务URL")
                    return {
                        "success": False,
                        "message": "认证服务不可用"
                    }
                
                # 修复：使用正确的验证接口路径
                verify_url = f"{self.auth_service_url}/api/verify"
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        verify_url,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        user_data = response.json()
                        return {
                            "success": True,
                            "user": user_data,
                            "message": "认证成功"
                        }
                    else:
                        error_details = response.text if response.text else "认证失败"
                        logger.warning(f"认证验证失败: {response.status_code} - {error_details}")
                        return {
                            "success": False,
                            "message": "认证令牌无效"
                        }
            else:
                return {
                    "success": False,
                    "message": "认证令牌格式错误，必须是Bearer或Service格式"
                }
                    
        except httpx.RequestError as e:
            logger.error(f"认证服务请求失败: {e}")
            return {
                "success": False,
                "message": "认证服务不可用"
            }
        except Exception as e:
            logger.error(f"认证过程出错: {e}")
            return {
                "success": False,
                "message": "认证过程出错"
            } 