"""Shared authentication and project-ownership checks for project-scoped APIs."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, Request


logger = logging.getLogger(__name__)


def extract_auth_header(request: Request) -> Optional[str]:
    """Read user/service authentication from a header or query token."""
    auth_header = request.headers.get("authorization")
    if not auth_header:
        token = request.query_params.get("token")
        if token:
            auth_header = f"Bearer {token}"
    return auth_header


async def get_auth_context(request: Request) -> Dict[str, Any]:
    """Validate a Bearer user token or an internal Service token."""
    auth_header = extract_auth_header(request)
    if not auth_header:
        raise HTTPException(status_code=401, detail="缺少认证令牌")

    if auth_header.startswith("Service "):
        service_token = auth_header.removeprefix("Service ").strip()
        expected_token = os.environ.get("SERVICE_AUTH_TOKEN")
        if not expected_token or service_token != expected_token:
            raise HTTPException(status_code=401, detail="服务间认证失败")
        return {"auth_type": "service", "authorization": auth_header}

    if auth_header.startswith("Bearer "):
        auth_service_url = os.getenv("AUTH_SERVICE_URL", "http://localhost:8007")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{auth_service_url}/api/verify",
                    headers={"Authorization": auth_header},
                )
        except httpx.RequestError as exc:
            logger.error("认证服务不可用: %s", exc)
            raise HTTPException(status_code=503, detail="认证服务不可用") from exc

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="认证令牌无效")
        return {
            "auth_type": "user",
            "authorization": auth_header,
            "user": response.json(),
        }

    raise HTTPException(status_code=401, detail="认证令牌格式错误")


async def require_authenticated(request: Request) -> Dict[str, Any]:
    return await get_auth_context(request)


async def require_service_access(request: Request) -> Dict[str, Any]:
    """Restrict maintenance endpoints to authenticated internal services."""
    context = await get_auth_context(request)
    if context["auth_type"] != "service":
        raise HTTPException(status_code=403, detail="仅允许内部服务调用")
    return context


async def require_project_access(
    request: Request,
    project_id: str,
    auth_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Require ownership without revealing whether another user's project exists."""
    context = auth_context or await get_auth_context(request)
    if context["auth_type"] == "service":
        return context

    project_service_url = os.getenv(
        "PROJECT_SERVICE_URL", "http://localhost:8020"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{project_service_url}/api/projects/{project_id}",
                headers={"Authorization": context["authorization"]},
            )
    except httpx.RequestError as exc:
        logger.error("项目服务不可用: %s", exc)
        raise HTTPException(status_code=503, detail="项目服务不可用") from exc

    if response.status_code == 200:
        return context
    if response.status_code in (401, 403, 404):
        raise HTTPException(status_code=404, detail="Project not found")

    logger.error(
        "项目访问校验失败: status=%s body=%s",
        response.status_code,
        response.text,
    )
    raise HTTPException(status_code=503, detail="项目访问校验失败")


async def require_project_access_dependency(
    request: Request,
    project_id: str,
) -> Dict[str, Any]:
    """FastAPI dependency for routes containing a ``project_id`` path field."""
    return await require_project_access(request, project_id)


async def require_admin(request: Request) -> Dict[str, Any]:
    """Admin access comes from a fresh auth-service lookup, never client claims."""
    context = await get_auth_context(request)
    user = context.get('user', {})
    if context['auth_type'] != 'user' or not user.get('is_active') or not user.get('is_superuser'):
        raise HTTPException(status_code=403, detail='Administrator access required')
    return context
