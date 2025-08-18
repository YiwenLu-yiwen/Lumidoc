from fastapi import FastAPI, HTTPException, Depends, APIRouter, Query, Path as FastAPIPath
from src.shared.health_check import get_system_info, ServiceStatus, HealthResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional, Union
import uuid
from datetime import datetime
from src.database import get_db
from sqlalchemy.orm import Session
import httpx
# 更新配置导入
from .config.config import settings
from .models.project import Project as DBProject
from .models.project_file import ProjectFile as DBProjectFile
# 导入共享类型定义
from src.shared.types.project import ProjectBase, ProjectCreate, ProjectUpdate, ProjectResponse, ProjectStatus
from src.shared.types.file import FileInfo
from src.shared.types.response import ApiResponse
import logging
import traceback
import os
from pathlib import Path
import uuid
from src.modules.auth.dependencies import get_current_user
# 导入任务去重装饰器
from src.shared.task_manager import dedupe_task
import asyncio
from pydantic import BaseModel, Field
# 导入服务客户端
from src.shared.service_discovery import get_service_client, call_service
from src.modules.auth.models.user import User

# 配置日志
logger = logging.getLogger(__name__)

# 创建日志目录
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# 确保记录器有文件处理程序
file_handler = logging.FileHandler(log_dir / "project_service.log")
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)

# 使用路由器替代直接创建FastAPI应用
router = APIRouter(prefix="/api", tags=["projects"])

# 创建单独的权限路由，使用不同的前缀
permissions_router = APIRouter(prefix="/api/user_permissions", tags=["permissions"])

# 创建单独的健康检查路由
health_router = APIRouter(tags=["health"])

# 用于JSON响应的权限模型
class ProjectPermissionResponse(BaseModel):
    project_id: str
    access_level: str  # owner, editor, viewer

class ProjectFile(FileInfo):
    """项目文件响应模型"""
    id: int  # 文件ID
    project_id: str  # 项目ID (UUID)
    file_metadata: Optional[Dict[str, Any]] = None  # 文件元数据
    type: Optional[str] = None  # 文件类型，使用数据库字段
    
    model_config = {
        "from_attributes": True
    }

# 添加RAG文件状态响应模型
class RagFileStatus(BaseModel):
    """RAG文件状态响应模型"""
    id: int
    name: str
    size: Optional[int] = None
    type: Optional[str] = None
    rag_status: str = "pending"  # pending, processing, completed, failed
    rag_processed_at: Optional[str] = None  # 处理完成时间
    rag_error_message: Optional[str] = None  # 错误信息
    is_in_rag: bool = False  # 是否在RAG知识库中
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    model_config = {
        "from_attributes": True
    }

class RagFileUpdate(BaseModel):
    """RAG文件状态更新模型"""
    rag_status: Optional[str] = None
    rag_error_message: Optional[str] = None
    is_in_rag: Optional[bool] = None

class ProjectService:
    def __init__(self, db: Session):
        self.db = db

    @dedupe_task(task_name="create_project")
    async def create_project(self, project: ProjectCreate, user_id: int) -> ProjectResponse:
        """创建新项目"""
        logger.info(f"Creating project '{project.name}' for user {user_id}")
        try:
            # 不再手动生成项目ID，使用数据库自增整数ID
            logger.debug(f"Creating project with auto-generated ID")
            
            # 确保状态值使用枚举的值（小写）
            status_value = ProjectStatus.ACTIVE.value
            logger.debug(f"Using status value: {status_value}")
            
            db_project = DBProject(
                # 移除id字段，让数据库生成
                name=project.name,
                description=project.description,
                user_id=user_id,
                status=status_value,
                project_metadata={}
            )
            logger.debug(f"DBProject object created: name={db_project.name}, status={db_project.status}")
            self.db.add(db_project)
            logger.debug("DBProject object added to session.")
            self.db.commit()
            logger.debug("Session committed.")
            self.db.refresh(db_project)
            logger.info(f"Project created successfully with ID: {db_project.id}")
            
            # 创建项目目录 - ID已经是UUID字符串
            project_id_str = str(db_project.id)
            upload_dir = os.environ.get("UPLOAD_DIR", "./uploads")
            
            # 确保uploads基础目录存在
            base_dir = Path(upload_dir)
            if not base_dir.exists():
                logger.info(f"创建基础上传目录: {base_dir}")
                base_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建项目特定目录
            project_dir = base_dir / project_id_str
            logger.info(f"准备创建项目目录: {project_dir}")
            
            try:
                project_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"项目目录已创建: {project_dir}")
                
                # 验证目录是否真的创建成功
                if project_dir.exists():
                    logger.info(f"确认项目目录已存在: {project_dir}")
                else:
                    logger.error(f"项目目录创建失败，尝试使用os.makedirs")
                    os.makedirs(str(project_dir), exist_ok=True)
                    logger.info(f"使用os.makedirs创建项目目录: {project_dir}")
            except Exception as dir_error:
                logger.error(f"创建项目目录时出错: {str(dir_error)}")
                logger.error(traceback.format_exc())
                # 继续处理，不阻止项目创建完成
            
            # 创建ProjectResponse对象，确保可以被JSON序列化
            # 将datetime对象转换为ISO格式字符串
            created_at_str = db_project.created_at.isoformat() if db_project.created_at else None
            updated_at_str = db_project.updated_at.isoformat() if db_project.updated_at else None
            
            return ProjectResponse(
                id=str(db_project.id),  # 将UUID转换为字符串
                name=db_project.name,
                description=db_project.description,
                status=ProjectStatus(db_project.status),
                project_metadata=db_project.project_metadata,
                created_at=created_at_str,
                updated_at=updated_at_str
            )
        except Exception as e:
            logger.error(f"Error creating project: {str(e)}")
            logger.error(traceback.format_exc())
            self.db.rollback()
            logger.debug("Session rolled back due to error.")
            raise

    @dedupe_task(task_name="list_projects")
    async def list_projects(self, user_id: int, skip: int = 0, limit: int = 100) -> List[ProjectResponse]:
        """获取项目列表 - 恢复简单查询，假设数据库结构已通过迁移修复"""
        logger.info(f"Listing projects for user {user_id} (skip={skip}, limit={limit})")
        if not user_id:
            logger.warning("No user_id provided, returning empty list")
            return []
        
        try:
            logger.debug(f"Querying projects for user_id={user_id}")
            # 添加按ID排序，确保顺序稳定
            db_projects = self.db.query(DBProject).filter(
                DBProject.user_id == user_id
            ).order_by(
                DBProject.id.asc()  # 明确按ID升序排序
            ).offset(skip).limit(limit).all()
            logger.info(f"Found {len(db_projects)} projects for user {user_id}")
            
            # 转换为ProjectResponse对象列表
            return [
                ProjectResponse(
                    id=str(project.id),
                    name=project.name,
                    description=project.description,
                    status=ProjectStatus(project.status),
                    project_metadata=project.project_metadata,
                    created_at=project.created_at.isoformat() if project.created_at else None,
                    updated_at=project.updated_at.isoformat() if project.updated_at else None
                ) for project in db_projects
            ]
        except Exception as e:
            logger.error(f"Error listing projects (ensure migration was run): {str(e)}")
            logger.error(traceback.format_exc())
            raise

    @dedupe_task(task_name="get_project")
    async def get_project(self, project_id: str, user_id: int) -> ProjectResponse:
        """获取项目详情"""
        logger.info(f"Getting project details for project_id={project_id}, user_id={user_id}")
        try:
            project = self.db.query(DBProject).filter(
                DBProject.id == uuid.UUID(project_id),
                DBProject.user_id == user_id
            ).first()
            if not project:
                logger.warning(f"Project {project_id} not found for user {user_id}")
                raise HTTPException(status_code=404, detail="Project not found")
            logger.info(f"Found project: {project.name} (ID: {project.id})")
            
            # 转换为ProjectResponse对象
            return ProjectResponse(
                id=str(project.id),
                name=project.name,
                description=project.description,
                status=ProjectStatus(project.status),
                project_metadata=project.project_metadata,
                created_at=project.created_at.isoformat() if project.created_at else None,
                updated_at=project.updated_at.isoformat() if project.updated_at else None
            )
        except Exception as e:
            logger.error(f"Error getting project: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    @dedupe_task(task_name="update_project")
    async def update_project(self, project_id: str, project: ProjectUpdate, user_id: int) -> ProjectResponse:
        """更新项目信息"""
        logger.info(f"Updating project {project_id} for user {user_id}")
        try:
            db_project = self.db.query(DBProject).filter(
                DBProject.id == uuid.UUID(project_id),
                DBProject.user_id == user_id
            ).first()
            if not db_project:
                logger.warning(f"Project {project_id} not found for user {user_id}")
                raise HTTPException(status_code=404, detail="Project not found")
            
            update_data = project.dict(exclude_unset=True)
            logger.debug(f"Update data: {update_data}")
            for field, value in update_data.items():
                setattr(db_project, field, value)
            
            db_project.updated_at = datetime.now()
            self.db.commit()
            self.db.refresh(db_project)
            logger.info(f"Project {project_id} updated successfully")
            
            # 转换为ProjectResponse对象
            return ProjectResponse(
                id=str(db_project.id),
                name=db_project.name,
                description=db_project.description,
                status=ProjectStatus(db_project.status),
                project_metadata=db_project.project_metadata,
                created_at=db_project.created_at.isoformat() if db_project.created_at else None,
                updated_at=db_project.updated_at.isoformat() if db_project.updated_at else None
            )
        except Exception as e:
            logger.error(f"Error updating project: {str(e)}")
            logger.error(traceback.format_exc())
            self.db.rollback()
            raise

    @dedupe_task(task_name="delete_project")
    async def delete_project(self, project_id: str, user_id: int) -> None:
        """删除项目及其相关资源"""
        logger.info(f"Deleting project {project_id} for user {user_id}")
        try:
            # 删除项目数据，增加用户ID验证
            project = self.db.query(DBProject).filter(
                DBProject.id == uuid.UUID(project_id),
                DBProject.user_id == user_id
            ).first()
            if not project:
                logger.warning(f"Project {project_id} not found for user {user_id}")
                raise HTTPException(status_code=404, detail="Project not found")
            
            # 删除项目文件
            logger.debug(f"Deleting files for project {project_id}")
            file_count = self.db.query(DBProjectFile).filter(DBProjectFile.project_id == uuid.UUID(project_id)).count()
            self.db.query(DBProjectFile).filter(DBProjectFile.project_id == uuid.UUID(project_id)).delete()
            logger.info(f"Deleted {file_count} files from project {project_id}")
            
            # 删除项目
            self.db.delete(project)
            self.db.commit()
            logger.info(f"Project {project_id} deleted successfully")
            
            # 清理相关资源
            await self._cleanup_project_resources(project_id)
        except Exception as e:
            logger.error(f"Error deleting project: {str(e)}")
            logger.error(traceback.format_exc())
            self.db.rollback()
            raise

    async def get_project_files(self, project_id: str, user_id: int) -> List[ProjectFile]:
        """获取项目文件列表"""
        logger.info(f"Getting files for project {project_id}, user {user_id}")
        try:
            # 验证项目归属
            project = self.db.query(DBProject).filter(
                DBProject.id == uuid.UUID(project_id),
                DBProject.user_id == user_id
            ).first()
            if not project:
                logger.warning(f"Project {project_id} not found for user {user_id}")
                raise HTTPException(status_code=404, detail="Project not found")
                
            files = self.db.query(DBProjectFile).filter(DBProjectFile.project_id == uuid.UUID(project_id)).all()
            logger.info(f"Found {len(files)} files for project {project_id}")
            return files
        except Exception as e:
            logger.error(f"Error getting project files: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def _cleanup_project_resources(self, project_id: str):
        """清理项目相关的资源"""
        logger.info(f"Cleaning up resources for project {project_id}")
        
        # 删除图谱数据
        try:
            logger.debug(f"Deleting graph data for project {project_id}")
            await call_service(
                service_name="graph-service",
                endpoint=f"/graphs/{project_id}",
                method="DELETE"
            )
            logger.info(f"Graph deletion completed for project {project_id}")
        except Exception as e:
            logger.error(f"Error deleting graph for project {project_id}: {e}")
        
        # 删除聊天会话
        try:
            logger.debug(f"Deleting chat sessions for project {project_id}")
            await call_service(
                service_name="chat-service",
                endpoint=f"/sessions/project/{project_id}",
                method="DELETE"
            )
            logger.info(f"Chat sessions deletion completed for project {project_id}")
        except Exception as e:
            logger.error(f"Error deleting chat sessions for project {project_id}: {e}")

    async def get_project_rag_files(self, project_id: str, user_id: int) -> List[RagFileStatus]:
        """获取项目RAG文件状态列表"""
        logger.info(f"Getting RAG files status for project {project_id}, user {user_id}")
        try:
            # 验证项目归属
            project = self.db.query(DBProject).filter(
                DBProject.id == uuid.UUID(project_id),
                DBProject.user_id == user_id
            ).first()
            if not project:
                logger.warning(f"Project {project_id} not found for user {user_id}")
                raise HTTPException(status_code=404, detail="Project not found")
                
            files = self.db.query(DBProjectFile).filter(DBProjectFile.project_id == uuid.UUID(project_id)).all()
            logger.info(f"Found {len(files)} files for project {project_id}")
            
            # 转换为RAG文件状态响应
            rag_files = []
            for file in files:
                rag_files.append(RagFileStatus(
                    id=file.id,
                    name=file.name,
                    size=file.size,
                    type=file.type,
                    rag_status=file.rag_status or "pending",
                    rag_processed_at=file.rag_processed_at.isoformat() if file.rag_processed_at else None,
                    rag_error_message=file.rag_error_message,
                    is_in_rag=file.is_in_rag or False,
                    created_at=file.created_at.isoformat() if file.created_at else None,
                    updated_at=file.updated_at.isoformat() if file.updated_at else None
                ))
            
            return rag_files
        except Exception as e:
            logger.error(f"Error getting project RAG files: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def update_file_rag_status(
        self, 
        project_id: str, 
        file_id: int, 
        user_id: int, 
        status_update: RagFileUpdate
    ) -> RagFileStatus:
        """更新文件RAG处理状态"""
        logger.info(f"Updating RAG status for file {file_id} in project {project_id}")
        try:
            # 验证项目归属
            project = self.db.query(DBProject).filter(
                DBProject.id == uuid.UUID(project_id),
                DBProject.user_id == user_id
            ).first()
            if not project:
                logger.warning(f"Project {project_id} not found for user {user_id}")
                raise HTTPException(status_code=404, detail="Project not found")
            
            # 查找文件
            file = self.db.query(DBProjectFile).filter(
                DBProjectFile.id == file_id,
                DBProjectFile.project_id == uuid.UUID(project_id)
            ).first()
            if not file:
                logger.warning(f"File {file_id} not found in project {project_id}")
                raise HTTPException(status_code=404, detail="File not found")
            
            # 更新状态
            update_data = status_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(file, field, value)
            
            # 如果状态变为completed，设置处理时间
            if status_update.rag_status == "completed":
                file.rag_processed_at = datetime.now()
                file.is_in_rag = True
            elif status_update.rag_status == "failed":
                file.is_in_rag = False
            
            file.updated_at = datetime.now()
            self.db.commit()
            self.db.refresh(file)
            
            logger.info(f"File {file_id} RAG status updated to {file.rag_status}")
            
            # 返回更新后的状态
            return RagFileStatus(
                id=file.id,
                name=file.name,
                size=file.size,
                type=file.type,
                rag_status=file.rag_status or "pending",
                rag_processed_at=file.rag_processed_at.isoformat() if file.rag_processed_at else None,
                rag_error_message=file.rag_error_message,
                is_in_rag=file.is_in_rag or False,
                created_at=file.created_at.isoformat() if file.created_at else None,
                updated_at=file.updated_at.isoformat() if file.updated_at else None
            )
        except Exception as e:
            logger.error(f"Error updating file RAG status: {str(e)}")
            logger.error(traceback.format_exc())
            self.db.rollback()
            raise

@permissions_router.get("/projects", response_model=List[ProjectPermissionResponse])
async def get_user_project_permissions(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的项目权限列表"""
    try:
        logger.info(f"获取用户 {user.id} 的项目权限")
        
        # 从数据库查询用户拥有的项目
        projects = []
        try:
            projects = db.query(DBProject).filter(DBProject.user_id == user.id).all()
        except Exception as db_error:
            logger.error(f"数据库查询项目失败: {str(db_error)}")
            logger.error(traceback.format_exc())
            # 数据库查询失败，返回空列表，避免整个请求失败
            return []
        
        if not projects:
            logger.info(f"用户 {user.id} 没有任何项目")
            return []
        
        # 构建权限响应
        permissions = []
        for project in projects:
            try:
                # 用户创建的项目拥有所有者权限
                permissions.append(ProjectPermissionResponse(
                    project_id=str(project.id),
                    access_level="owner"
                ))
            except Exception as item_error:
                logger.error(f"处理项目 {project.id} 权限时出错: {str(item_error)}")
                # 单个项目处理出错，继续处理其他项目
                continue
        
        logger.info(f"用户 {user.id} 的项目权限: {permissions}")
        return permissions
    except Exception as e:
        logger.error(f"获取用户项目权限列表失败: {str(e)}")
        logger.error(traceback.format_exc())
        # 出现错误时返回空列表，而不是引发500错误
        return []

@router.get("/projects", response_model=List[ProjectResponse])
async def get_projects(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, description="分页起始位置"),
    limit: int = Query(100, description="每页记录数")
):
    """获取项目列表"""
    try:
        # 获取当前用户的项目
        projects = db.query(DBProject).filter(DBProject.user_id == user.id).offset(skip).limit(limit).all()
        
        # 手动转换项目对象为响应模型，确保日期格式正确
        result = []
        for project in projects:
            result.append(ProjectResponse(
                id=str(project.id),
                name=project.name,
                description=project.description,
                status=ProjectStatus(project.status),
                project_metadata=project.project_metadata,
                created_at=project.created_at.isoformat() if project.created_at else None,
                updated_at=project.updated_at.isoformat() if project.updated_at else None
            ))
        return result
    except Exception as e:
        logger.error(f"获取项目列表失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取项目列表失败: {str(e)}")

@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str = FastAPIPath(..., description="项目ID (UUID)"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取项目详情"""
    logger.info(f"获取项目 {project_id} 详情")
    service = ProjectService(db)
    try:
        return await service.get_project(project_id=project_id, user_id=user.id)
    except HTTPException as e:
        logger.error(f"获取项目详情失败: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"获取项目详情失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取项目详情失败: {str(e)}")

# 添加创建项目的路由
@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新项目"""
    logger.info(f"创建新项目: {project.name}")
    service = ProjectService(db)
    try:
        return await service.create_project(project=project, user_id=user.id)
    except HTTPException as e:
        logger.error(f"创建项目失败: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"创建项目失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"创建项目失败: {str(e)}")

# 添加更新项目的路由
@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project: ProjectUpdate,
    project_id: str = FastAPIPath(..., description="项目ID (UUID)"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新项目信息"""
    logger.info(f"更新项目 {project_id}")
    service = ProjectService(db)
    try:
        return await service.update_project(project_id=project_id, project=project, user_id=user.id)
    except HTTPException as e:
        logger.error(f"更新项目失败: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"更新项目失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"更新项目失败: {str(e)}")

# 添加删除项目的路由
@router.delete("/projects/{project_id}", response_model=dict)
async def delete_project(
    project_id: str = FastAPIPath(..., description="项目ID (UUID)"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除项目"""
    logger.info(f"删除项目 {project_id}")
    service = ProjectService(db)
    try:
        await service.delete_project(project_id=project_id, user_id=user.id)
        return {"detail": "项目已成功删除"}
    except HTTPException as e:
        logger.error(f"删除项目失败: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"删除项目失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"删除项目失败: {str(e)}")

# 添加OPTIONS支持，确保CORS预检请求能够正确处理
@router.options("/projects/{project_id}")
async def options_project(project_id: str = FastAPIPath(..., description="项目ID (UUID)")):
    """处理项目的OPTIONS预检请求"""
    return {"message": "OK"}

@router.options("/projects")
async def options_projects():
    """处理项目列表的OPTIONS预检请求"""
    return {"message": "OK"}

# 添加RAG文件相关路由
@router.get("/projects/{project_id}/lightrag/files", response_model=List[RagFileStatus])
async def get_project_lightrag_files(
    project_id: str = FastAPIPath(..., description="项目ID (UUID)"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取项目RAG文件状态列表"""
    logger.info(f"获取项目 {project_id} 的RAG文件状态")
    service = ProjectService(db)
    try:
        return await service.get_project_rag_files(project_id=project_id, user_id=user.id)
    except HTTPException as e:
        logger.error(f"获取RAG文件状态失败: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"获取RAG文件状态失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取RAG文件状态失败: {str(e)}")

@router.put("/projects/{project_id}/lightrag/files/{file_id}", response_model=RagFileStatus)
async def update_file_lightrag_status(
    status_update: RagFileUpdate,
    project_id: str = FastAPIPath(..., description="项目ID (UUID)"),
    file_id: int = FastAPIPath(..., description="文件ID"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新文件RAG处理状态"""
    logger.info(f"更新项目 {project_id} 文件 {file_id} 的RAG状态")
    service = ProjectService(db)
    try:
        return await service.update_file_rag_status(
            project_id=project_id, 
            file_id=file_id, 
            user_id=user.id, 
            status_update=status_update
        )
    except HTTPException as e:
        logger.error(f"更新RAG文件状态失败: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"更新RAG文件状态失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"更新RAG文件状态失败: {str(e)}")
