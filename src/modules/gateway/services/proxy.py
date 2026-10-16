"""
Gateway请求代理和转发模块
"""

import logging
import time
from typing import Dict, Optional
import httpx
from fastapi import Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from .service_discovery import get_service_discovery, ServiceInstance
from src.modules.gateway.config.config import settings

logger = logging.getLogger(__name__)

class RequestProxy:
    """请求代理器"""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=30.0,   # 增加连接超时时间
                read=7200.0,    # 支持长时间运行的请求（2小时）
                write=30.0,     # 增加写入超时时间
                pool=30.0       # 增加连接池超时时间
            ),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20
            ),
            follow_redirects=True,  # 启用自动重定向跟随，确保透明代理
            verify=False  # 禁用SSL验证，避免本地连接问题
        )

    async def proxy_request(
        self,
        request: Request,
        service_name: str,
        target_path: str = None
    ) -> Response:
        """代理请求到目标服务"""
        start_time = time.time()

        try:
            # 获取服务发现实例
            service_discovery = await get_service_discovery()
            service_instance = await service_discovery.get_service_instance(service_name)

            if not service_instance:
                logger.error(f"未找到可用的服务实例: {service_name}")
                raise HTTPException(
                    status_code=503,
                    detail=f"服务 {service_name} 不可用"
                )

            # 构建目标URL
            target_url = await self._build_target_url(
                service_instance,
                request,
                target_path
            )

            # 准备请求头
            headers = await self._prepare_headers(request)

            # 准备请求体
            body = await self._prepare_body(request)

            # 获取服务配置
            service_config = settings.get_service_config(service_name)
            timeout = service_config.get("timeout", 30.0) if service_config else 30.0

            # 发送请求
            response = await self._send_request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                timeout=timeout
            )

            # 记录请求统计
            response_time = time.time() - start_time
            service_instance.record_request(response_time, response.status_code < 400)

            # 处理响应
            return await self._handle_response(response, request)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"代理请求失败: {e}")
            # 记录错误统计
            try:
                service_instance.record_request(time.time() - start_time, False)
            except Exception:
                pass
            raise HTTPException(
                status_code=502,
                detail=f"网关错误: {str(e)}"
            )

    async def _build_target_url(
        self,
        service_instance: ServiceInstance,
        request: Request,
        target_path: str = None
    ) -> str:
        """构建目标URL"""
        base_url = service_instance.url.rstrip('/')

        if target_path:
            # 使用指定的目标路径
            path = target_path
        else:
            # 从请求URL中提取路径
            path = request.url.path

            # 获取服务配置
            service_config = settings.get_service_config(service_instance.name)
            if service_config and service_config.get("prefix"):
                prefix = service_config["prefix"]
                strip_prefix = service_config.get("strip_prefix", True)  # 默认移除前缀

                if path.startswith(prefix):
                    if strip_prefix:
                        # 移除Gateway前缀，添加实际服务路径
                        path = path[len(prefix):]

                        # 根据服务名称处理特殊路由
                        if service_instance.name == "fileproc":
                            # FileProc服务需要/api前缀
                            if not path.startswith('/api'):
                                path = '/api' + path
                        elif service_instance.name == "auth":
                            # Auth服务需要/api前缀
                            if not path.startswith('/api'):
                                path = '/api' + path
                        elif service_instance.name == "file":
                            # File服务需要/api/file前缀
                            if not path.startswith('/api'):
                                path = '/api/file' + path
                        elif service_instance.name == "project":
                            # 项目服务：移除前缀后直接转发
                            if not path.startswith('/'):
                                path = '/' + path
                        elif service_instance.name == "lightrag":
                            # LightRAG服务保持原有路由结构
                            if not path.startswith('/rag'):
                                path = '/rag' + path
                    else:
                        # 不移除前缀，直接转发
                        # 对于文件服务，需要添加/api前缀
                        if service_instance.name == "file":
                            # File服务需要/api/file前缀，但当前路径是/file/...
                            if path.startswith('/file') and not path.startswith('/api'):
                                path = '/api' + path
                        # 对于LLM服务，需要转换为/api/v1/llm前缀
                        elif service_instance.name == "llm":
                            # LLM服务需要/api/v1/llm前缀，当前路径是/llm/...
                            if path.startswith('/llm') and not path.startswith('/api'):
                                # 检查是否是健康检查端点，这些端点不需要API前缀
                                remaining_path = path[4:]  # 移除/llm前缀
                                if remaining_path in ['/health', '/healthz', '/ready', '/']:
                                    path = remaining_path if remaining_path != '/' else '/health'
                                else:
                                    # 其他端点需要API前缀
                                    path = path.replace('/llm', '/api/v1/llm', 1)
                        # 对于LightRAG，需要处理双重前缀情况
                        elif service_instance.name == "lightrag":
                            # 处理多级路径模式：/api/lightrag/lightrag/... -> /api/lightrag/...
                            if "/lightrag/lightrag/" in path:
                                path = path.replace("/lightrag/lightrag/", "/lightrag/rag/", 1)
                            # 处理普通情况：/lightrag/... -> /rag/...
                            else:
                                path = path.replace("/lightrag", "/rag", 1)

        # 确保路径以 / 开头
        if not path.startswith('/'):
            path = '/' + path

        # 构建完整URL
        target_url = f"{base_url}{path}"

        # 添加查询参数
        if request.url.query:
            target_url += f"?{request.url.query}"

        logger.info(f"转发请求: {request.method} {request.url} -> {target_url}")

        return target_url

    async def _prepare_headers(self, request: Request) -> Dict[str, str]:
        """准备请求头"""
        headers = {}

        # 复制原始请求头，排除一些不应该转发的头
        skip_headers = {
            'host', 'connection', 'accept-encoding', 'content-length',
            'transfer-encoding', 'te', 'upgrade', 'proxy-authorization',
            'proxy-authenticate'
        }

        for name, value in request.headers.items():
            if name.lower() not in skip_headers:
                headers[name] = value

        # 添加Gateway特有的头
        headers['X-Forwarded-For'] = request.client.host
        headers['X-Forwarded-Proto'] = request.url.scheme
        headers['X-Forwarded-Host'] = request.headers.get('host', '')
        headers['X-Gateway-Version'] = settings.service_version

        return headers

    async def _prepare_body(self, request: Request) -> Optional[bytes]:
        """准备请求体"""
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return None

        try:
            body = await request.body()
            return body if body else None
        except Exception as e:
            logger.warning(f"读取请求体失败: {e}")
            return None

    async def _send_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        content: Optional[bytes],
        timeout: float
    ) -> httpx.Response:
        """发送HTTP请求"""
        try:
            logger.debug(f"🔧 Gateway正在发送请求: {method} {url}")
            logger.debug(f"🔧 请求头: {headers}")
            logger.debug(f"🔧 超时设置: {timeout}秒")

            upstream_request = self.client.build_request(
                method=method,
                url=url,
                headers=headers,
                content=content,
                timeout=timeout
            )

            response = await self.client.send(upstream_request, stream=True)

            logger.debug(f"✅ Gateway请求成功: {method} {url} -> {response.status_code}")
            return response

        except httpx.TimeoutException as e:
            logger.error(f"❌ Gateway请求超时: {method} {url} - {str(e)}")
            raise HTTPException(status_code=504, detail="请求超时")
        except httpx.ConnectError as e:
            logger.error(f"❌ Gateway连接错误: {method} {url} - {str(e)}")
            logger.error(f"🔧 连接详情: {e.__class__.__name__} - {str(e)}")
            raise HTTPException(status_code=502, detail="连接错误: 无法连接到目标服务")
        except httpx.RequestError as e:
            logger.error(f"❌ Gateway请求错误: {method} {url} - {str(e)}")
            logger.error(f"🔧 错误详情: {e.__class__.__name__} - {str(e)}")
            raise HTTPException(status_code=502, detail=f"请求错误: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Gateway未知错误: {method} {url} - {str(e)}")
            logger.error(f"🔧 异常详情: {e.__class__.__name__} - {str(e)}")
            import traceback
            logger.error(f"🔧 完整错误栈: {traceback.format_exc()}")
            raise HTTPException(status_code=502, detail=f"网关内部错误: {str(e)}")

    async def _handle_response(self, response: httpx.Response, request: Request) -> Response:
        """处理响应"""
        # 准备响应头
        response_headers = {}

        # 复制响应头，排除一些不应该转发的头
        skip_headers = {
            'connection', 'transfer-encoding', 'content-encoding',
            'content-length', 'server'
        }

        for name, value in response.headers.items():
            if name.lower() not in skip_headers:
                response_headers[name] = value

        # 添加Gateway特有的头
        response_headers['X-Gateway-Proxy'] = 'Lumidoc-Gateway'

        # 处理不同类型的响应
        content_type = response.headers.get('content-type', '')

        if 'text/event-stream' in content_type:
            # 处理SSE流响应
            return await self._handle_streaming_response(response, response_headers)
        elif 'application/octet-stream' in content_type or 'application/pdf' in content_type:
            # 处理二进制文件响应
            return await self._handle_binary_response(response, response_headers)
        else:
            # 处理普通响应
            return await self._handle_regular_response(response, response_headers)

    async def _handle_streaming_response(
        self,
        response: httpx.Response,
        headers: Dict[str, str]
    ) -> StreamingResponse:
        """处理流式响应"""
        async def generate():
            # 添加心跳机制，防止客户端超时
            last_chunk_time = time.time()
            heartbeat_interval = 15.0  # 15秒发送一次心跳

            try:
                # 发送初始心跳，确保连接建立
                yield b": connection established\n\n"

                # 处理流式响应
                async for chunk in response.aiter_bytes():
                    # 发送实际数据
                    if chunk:
                        yield chunk

                    # 更新最后接收时间
                    current_time = time.time()

                    # 如果太久没有数据，发送心跳
                    if current_time - last_chunk_time > heartbeat_interval:
                        yield b": keepalive\n\n"
                        last_chunk_time = current_time
                    else:
                        last_chunk_time = current_time

            except httpx.ReadTimeout:
                logger.error("流式响应读取超时")
                error_msg = "Read timeout, please retry"
                yield f"data: {{\"error\":\"{error_msg}\"}}\n\n".encode('utf-8')
            except Exception as e:
                logger.error(f"流式响应处理错误: {str(e)}")
                error_msg = "Processing error, please retry"
                yield f"data: {{\"error\":\"{error_msg}\"}}\n\n".encode('utf-8')
            finally:
                await response.aclose()

        return StreamingResponse(
            content=generate(),
            status_code=response.status_code,
            headers=headers,
            media_type=response.headers.get('content-type', 'text/event-stream')
        )

    async def _handle_binary_response(
        self,
        response: httpx.Response,
        headers: Dict[str, str]
    ) -> Response:
        """处理二进制响应"""
        content = await response.aread()

        return Response(
            content=content,
            status_code=response.status_code,
            headers=headers,
            media_type=response.headers.get('content-type', 'application/octet-stream')
        )

    async def _handle_regular_response(
        self,
        response: httpx.Response,
        headers: Dict[str, str]
    ) -> Response:
        """处理普通响应"""
        content = await response.aread()

        return Response(
            content=content,
            status_code=response.status_code,
            headers=headers,
            media_type=response.headers.get('content-type', 'application/json')
        )

    async def close(self):
        """关闭代理器"""
        await self.client.aclose()

# 全局代理实例
request_proxy = RequestProxy()

async def get_request_proxy() -> RequestProxy:
    """获取请求代理实例"""
    return request_proxy
