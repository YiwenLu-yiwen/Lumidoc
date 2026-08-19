#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
摘要服务客户端 - 用于调用LLM摘要服务
"""

import os
import logging
import httpx
from typing import Dict, Any

from src.shared.service_discovery import get_service_url

logger = logging.getLogger(__name__)

class SummaryClient:
    """LLM摘要服务客户端"""
    
    def __init__(self):
        """初始化摘要服务客户端"""
        self.service_name = "llm_summary"
        self.service_url = None
        self.timeout = float(os.getenv("LLM_SUMMARY_SERVICE_TIMEOUT", "30"))
    
    async def _get_service_url(self) -> str:
        """获取摘要服务URL"""
        if not self.service_url:
            # 优先从服务发现获取
            discovered_url = await get_service_url(self.service_name)
            if discovered_url:
                self.service_url = discovered_url
            else:
                # 回退到环境变量
                self.service_url = os.getenv("LLM_SUMMARY_SERVICE_URL", "http://localhost:8009")
            
            logger.info(f"摘要服务URL: {self.service_url}")
        
        return self.service_url
    
    async def generate_summary(self, content: str, project_id: str = None, file_hash: str = None) -> Dict[str, Any]:
        """
        生成文档摘要 - 严格遵循项目原则：通过Gateway调用服务
        
        Args:
            content: 文档内容
            project_id: 项目ID（可选）
            file_hash: 文件哈希值（可选）
            
        Returns:
            Dict[str, Any]: 摘要结果
        """
        try:
            # 严格遵循项目原则：所有服务间调用必须通过Gateway
            from src.shared.service_discovery import call_service
            
            # 准备请求数据
            data = {
                "content": content
            }
            
            # 如果提供了项目ID和文件哈希，也一并传递
            if project_id and file_hash:
                data["project_id"] = project_id
                data["file_hash"] = file_hash
            
            # 通过Gateway调用LLM服务生成摘要
            result = await call_service(
                service_name="llm",
                endpoint="api/v1/llm/summarize",
                method="POST",
                json_data=data,
                timeout=self.timeout
            )
            
            if not result or not result.get("success", False):
                logger.error(f"生成摘要失败: {result.get('error', '未知错误') if result else '空响应'}")
                return {
                    "success": False,
                    "error": result.get("error", "生成摘要失败") if result else "服务调用失败"
                }
            
            return result
        
        except Exception as e:
            logger.error(f"生成摘要时发生错误: {str(e)}")
            return {
                "success": False,
                "error": f"生成摘要时发生错误: {str(e)}"
            }
    
    async def get_document_summary(self, project_id: str, file_hash: str, regenerate: bool = False) -> Dict[str, Any]:
        """
        获取文档摘要 - 严格遵循项目原则：通过Gateway调用服务
        
        Args:
            project_id: 项目ID
            file_hash: 文件哈希值
            regenerate: 是否重新生成摘要
            
        Returns:
            Dict[str, Any]: 摘要结果
        """
        try:
            # 严格遵循项目原则：所有服务间调用必须通过Gateway
            from src.shared.service_discovery import call_service
            
            # 构建端点路径
            endpoint = f"api/v1/llm/summary/{project_id}/{file_hash}"
            
            # 准备请求参数
            params = {}
            if regenerate:
                params["regenerate"] = "true"
            
            # 通过Gateway调用LLM服务获取摘要
            result = await call_service(
                service_name="llm",
                endpoint=endpoint,
                method="GET",
                params=params,
                timeout=self.timeout
            )
            
            return result if result else {
                "success": False,
                "error": "服务调用失败"
            }
        
        except Exception as e:
            logger.error(f"获取摘要时发生错误: {str(e)}")
            return {
                "success": False,
                "error": f"获取摘要时发生错误: {str(e)}"
            }
    
    async def check_health(self) -> bool:
        """
        检查摘要服务的健康状态
        
        Returns:
            bool: 服务是否健康
        """
        try:
            service_url = await self._get_service_url()
            health_url = f"{service_url}/health"
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(health_url)
                response.raise_for_status()
                
                health_data = response.json()
                return health_data.get("status") == "ok"
                
        except Exception as e:
            logger.error(f"摘要服务健康检查失败: {str(e)}")
            return False 