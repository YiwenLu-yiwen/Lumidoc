import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from typing import List
from pydantic import BaseModel
import logging
from Lumidoc_webui.backend.api.auth_routes import get_current_user
from Lumidoc_webui.backend.api.services import project_service

# 设置日志
logger = logging.getLogger(__name__)

# 创建API路由
router = APIRouter()

# 项目权限API响应模型
class ProjectPermissionResponse(BaseModel):
    project_id: str
    access_level: str

@router.get("/user_permissions/projects", response_model=List[ProjectPermissionResponse], tags=["permissions"])
async def get_user_project_permissions(
    current_user = Depends(get_current_user),
    request: Request = None
):
    """获取当前用户的项目权限"""
    try:
        # 获取用户ID
        user_id = current_user.id
        logger.info(f"获取用户 {user_id} 的项目权限")
        
        # 使用项目服务客户端获取权限
        headers = {"Authorization": f"Bearer {current_user.token}"}
        
        # 调用项目服务API获取用户项目权限
        result = await project_service.get(
            "/api/user_permissions/projects",
            headers=headers
        )
        logger.info(f"成功获取用户项目权限: {result}")
        return result
    except Exception as e:
        logger.error(f"获取用户项目权限失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 