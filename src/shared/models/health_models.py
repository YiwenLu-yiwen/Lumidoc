#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
健康检查模型 - 定义所有服务通用的健康检查响应格式
遵循Lumidoc微服务架构设计原则
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    """
    健康检查响应模型

    Attributes:
        status (str): 服务状态，可能的值: ok, error, degraded, warning
        service (str): 服务名称
        version (str): 服务版本
        checks (Dict[str, Any]): 各依赖服务的健康状态
        detail (Optional[str]): 详细状态信息
        timestamp (Optional[str]): 健康检查的时间戳
    """
    status: str = Field(..., description="服务状态，可能的值: ok, error, degraded, warning")
    service: str = Field(..., description="服务名称")
    version: str = Field(..., description="服务版本")
    checks: Dict[str, Any] = Field({}, description="各依赖服务的健康状态")
    detail: Optional[str] = Field(None, description="详细状态信息")
    timestamp: Optional[str] = Field(None, description="健康检查的时间戳")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "service": "file_service",
                "version": "1.0.0",
                "checks": {
                    "database": {
                        "status": "ok",
                        "critical": True,
                        "message": None
                    },
                    "storage": {
                        "status": "ok",
                        "critical": True,
                        "message": None
                    },
                    "redis": {
                        "status": "ok",
                        "critical": False,
                        "message": None
                    }
                },
                "detail": "所有服务组件正常",
                "timestamp": "2025-06-11T21:45:30.123456"
            }
        }
    }


class ServiceHealthCheck:
    """
    服务健康检查状态常量
    """
    OK = "ok"
    ERROR = "error"
    DEGRADED = "degraded"
    WARNING = "warning"

    @staticmethod
    def determine_status(checks: Dict[str, Any]) -> str:
        """
        根据检查结果确定整体服务状态

        Args:
            checks: 各依赖服务的健康状态

        Returns:
            str: 整体服务状态
        """
        has_critical_error = False
        has_non_critical_error = False

        for _, check in checks.items():
            if check.get("status") != ServiceHealthCheck.OK:
                if check.get("critical", False):
                    has_critical_error = True
                else:
                    has_non_critical_error = True

        if has_critical_error:
            return ServiceHealthCheck.ERROR
        elif has_non_critical_error:
            return ServiceHealthCheck.DEGRADED
        else:
            return ServiceHealthCheck.OK
