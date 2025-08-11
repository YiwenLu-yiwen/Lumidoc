import os
import logging
import json
import traceback
import re
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Path, Query, File, UploadFile, Body, Form
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, UUID4

from src.shared.logger import get_logger
from src.database import get_db
from src.modules.auth.dependencies import get_current_user
from src.modules.project.project_service import ProjectService
from src.shared.types.project import ProjectCreate, ProjectUpdate, ProjectResponse
from Lumidoc_webui.backend.api.services import file_service, chat_service
from src.shared.types.response import ApiResponse
from src.shared.types.chat import ChatMessage

# 确保URL总是包含协议
def ensure_url_protocol(url: str) -> str:
    """确保URL包含http://或https://前缀"""
    if not url.startswith(('http://', 'https://')):
        return f"http://{url}"
    return url

# 配置日志
logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/projects",
    tags=["projects"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建新项目"""
    logger.info(f"Creating project for user {user.id}, username: {user.username}")
    try:
        project_service = ProjectService(db)
        result = await project_service.create_project(project, user.id)
        return result
    except Exception as e:
        logger.error(f"Failed to create project: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=list[ProjectResponse])
async def get_projects(
    skip: int = 0,
    limit: int = 100,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取项目列表"""
    logger.info(f"Listing projects for user {user.id}, username: {user.username}")
    try:
        logger.debug(f"用户数据: {json.dumps({'id': user.id, 'username': user.username}, ensure_ascii=False)}")
        
        # 使用ProjectService而不是直接查询
        project_service = ProjectService(db)
        result = await project_service.list_projects(user.id, skip, limit)
        
        logger.info(f"Successfully retrieved {len(result)} projects for user {user.id}")
        return result
    except Exception as e:
        error_msg = f"Failed to list projects: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        # 返回更具体的错误信息
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取项目详情"""
    logger.info(f"Getting project {project_id} for user {user.id}, username: {user.username}")
    try:
        project_service = ProjectService(db)
        result = await project_service.get_project(project_id, user.id)
        return result
    except Exception as e:
        logger.error(f"Failed to get project: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project: ProjectUpdate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新项目"""
    logger.info(f"Updating project {project_id} for user {user.id}, username: {user.username}")
    try:
        project_service = ProjectService(db)
        result = await project_service.update_project(project_id, project, user.id)
        return result
    except Exception as e:
        logger.error(f"Failed to update project: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{project_id}", response_model=ApiResponse)
async def delete_project(
    project_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除项目"""
    logger.info(f"Deleting project {project_id} for user {user.id}, username: {user.username}")
    try:
        project_service = ProjectService(db)
        await project_service.delete_project(project_id, user.id)
        return ApiResponse(
            success=True,
            message=f"Project {project_id} and its resources deleted successfully"
        )
    except Exception as e:
        logger.error(f"Failed to delete project: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}/files")
async def get_project_files(
    project_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取项目文件列表"""
    logger.info(f"获取项目{project_id}文件列表，用户：{user.id}")
    try:
        # 使用服务发现获取文件服务URL
        from src.shared.service_discovery import get_service_url
        
        # 通过服务发现获取文件服务URL
        file_service_url = await get_service_url("file")
        if not file_service_url:
            # 回退到配置的URL
            file_service_url = ensure_url_protocol(file_service.base_url)
            logger.info(f"服务发现未找到file服务，使用配置的URL: {file_service_url}")
        else:
            logger.info(f"通过服务发现获取到file服务URL: {file_service_url}")
        
        # 调用文件服务API获取项目文件列表
        import httpx
        async with httpx.AsyncClient() as client:
            # 构建请求URL - 使用正确的API路径
            api_url = f"{file_service_url}/api/file/list/{project_id}"
            logger.info(f"请求文件列表URL: {api_url}")
            
            # 添加服务间认证头
            headers = {
                "Authorization": f"Service {os.environ.get('SERVICE_AUTH_TOKEN', 'service-token-for-internal-use')}"
            }
            
            # 发送请求
            response = await client.get(api_url, headers=headers, timeout=10.0)
            
            # 检查响应状态
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"获取文件列表失败: {response.status_code} - {error_text}")
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"获取文件列表失败: {error_text}"
                )
            
            # 解析响应结果
            result = response.json()
            logger.info(f"成功获取项目文件列表，项目ID: {project_id}, 文件数量: {len(result) if isinstance(result, list) else '未知'}")
            return result
            
    except httpx.RequestError as e:
        error_msg = f"请求文件服务失败: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"获取项目文件列表失败: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/{project_id}/files/upload")
async def upload_project_file(
    project_id: int,
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传项目文件"""
    logger.info(f"上传文件到项目{project_id}，用户：{user.id}")
    try:
        # 获取文件服务URL
        from src.shared.service_discovery import get_service_url
        import httpx
        
        # 通过服务发现获取文件服务URL
        file_service_url = await get_service_url("file")
        if not file_service_url:
            # 回退到配置的URL
            file_service_url = ensure_url_protocol(file_service.base_url)
            logger.info(f"服务发现未找到file服务，使用配置的URL: {file_service_url}")
        else:
            logger.info(f"通过服务发现获取到file服务URL: {file_service_url}")
        
        try:
            # 从请求中读取表单数据
            form_data = await request.form()
            
            # 获取所有文件对象
            file_objects = []
            for key, value in form_data.items():
                if (key == 'file' or key == 'files' or key.startswith('file[')) and hasattr(value, "file"):
                    file_objects.append(value)
            
            logger.info(f"发现{len(file_objects)}个文件对象")
            
            if not file_objects:
                raise HTTPException(status_code=400, detail="未找到上传文件")
            
            # 创建认证头信息
            headers = {}
            auth_header = request.headers.get("Authorization")
            if auth_header:
                headers["Authorization"] = auth_header
            
            # 从请求中获取process参数
            form_fields = {}
            for key, value in form_data.items():
                if not hasattr(value, "file"):
                    form_fields[key] = str(value)
            
            logger.info(f"表单参数: {form_fields}")
            
            # 支持的文件类型
            supported_extensions = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.txt', '.md', '.csv']
            
            # 构建完整的API路径
            upload_url = f"{file_service_url}/projects/{project_id}/files/upload"
            logger.info(f"文件上传URL: {upload_url}")
            
            # 处理每个文件并收集结果
            results = []
            for i, file_obj in enumerate(file_objects):
                try:
                    logger.info(f"处理文件 {i+1}/{len(file_objects)}: {file_obj.filename}")
                    
                    # 检查文件类型
                    file_ext = os.path.splitext(file_obj.filename)[1].lower()
                    should_process = 'process' in form_fields and form_fields['process'].lower() == 'true'
                    
                    if should_process and file_ext not in supported_extensions:
                        logger.warning(f"不支持处理的文件类型: {file_ext}, 文件: {file_obj.filename}")
                        results.append({
                            "filename": file_obj.filename,
                            "success": True,
                            "message": f"文件上传成功，但不支持处理此类型: {file_ext}",
                            "processing": False,
                            "processing_error": f"不支持的文件类型: {file_ext}"
                        })
                        continue
                    
                    # 读取文件内容
                    content = await file_obj.read()
                    
                    # 准备文件上传数据
                    files = {"file": (file_obj.filename, content, file_obj.content_type)}
                    
                    # 使用httpx发送文件上传请求，确保传递process参数
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            upload_url,
                            files=files,
                            data=form_fields,  # 传递所有表单参数，包括process
                            headers=headers,
                            timeout=60.0  # 增加超时时间以处理大文件
                        )
                        
                        # 检查响应状态
                        if response.status_code != 200:
                            error_text = response.text
                            logger.error(f"文件 {file_obj.filename} 上传失败: {response.status_code} - {error_text}")
                            results.append({
                                "filename": file_obj.filename,
                                "success": False,
                                "message": f"上传失败: {error_text}",
                                "status_code": response.status_code
                            })
                        else:
                            # 处理成功响应
                            try:
                                file_result = response.json()
                                if isinstance(file_result, dict):
                                    # 确保结果中包含原始文件名
                                    if 'filename' not in file_result:
                                        file_result['filename'] = file_obj.filename
                                    file_result['success'] = True
                                    
                                    # 确保处理文件的请求被正确处理
                                    if should_process:
                                        logger.info(f"文件 {file_obj.filename} 需要处理，确认处理状态")
                                        if not file_result.get('processing', False) and not file_result.get('exists', False):
                                            logger.warning(f"文件上传成功但未自动处理，尝试手动触发处理")
                                            # 如果没有自动处理且不是已存在文件，尝试手动触发处理
                                            try:
                                                file_id = file_result.get('file_id')
                                                if file_id:
                                                    process_url = f"{file_service_url}/process/{file_id}"
                                                    process_response = await client.post(
                                                        process_url,
                                                        json={"project_id": project_id},
                                                        headers=headers
                                                    )
                                                    if process_response.status_code == 200:
                                                        process_result = process_response.json()
                                                        file_result['processing'] = True
                                                        file_result['task_id'] = process_result.get('task_id')
                                                        logger.info(f"手动触发处理成功: {file_obj.filename}")
                                                    else:
                                                        logger.warning(f"手动触发处理失败: {process_response.status_code}")
                                            except Exception as process_error:
                                                logger.error(f"手动触发处理出错: {str(process_error)}")
                                    
                                    results.append(file_result)
                                    logger.info(f"文件 {file_obj.filename} 上传成功，响应结果: {file_result}")
                                else:
                                    logger.warning(f"文件服务返回了非预期格式的响应: {file_result}")
                                    results.append({
                                        "filename": file_obj.filename,
                                        "success": True,
                                        "message": "文件上传成功，但服务返回格式异常",
                                        "raw_response": file_result
                                    })
                            except Exception as parse_error:
                                logger.error(f"解析文件 {file_obj.filename} 上传响应时出错: {str(parse_error)}")
                                results.append({
                                    "filename": file_obj.filename,
                                    "success": True,
                                    "message": f"文件上传成功，但解析响应失败: {str(parse_error)}",
                                    "raw_response": response.text
                                })
                except Exception as file_error:
                    logger.error(f"处理文件 {file_obj.filename} 时出错: {str(file_error)}")
                    results.append({
                        "filename": file_obj.filename,
                        "success": False,
                        "message": f"处理失败: {str(file_error)}"
                    })
            
            # 返回所有文件的上传结果
            if len(results) == 1:
                # 单文件上传时返回单个结果
                return results[0]
            else:
                # 多文件上传时返回集合结果
                combined_result = {
                    "success": any(r.get('success', False) for r in results),
                    "files": results,
                    "total": len(results),
                    "successful": sum(1 for r in results if r.get('success', False))
                }
                
                logger.info(f"文件上传完成: {combined_result['total']}个文件, 成功: {combined_result['successful']}个")
                return combined_result
                
        except httpx.RequestError as e:
            logger.error(f"文件上传请求失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"文件上传请求失败: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"文件上传处理失败: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/{project_id}/chat_history", response_model=List[ChatMessage])
async def get_project_chat_history(
    project_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取项目聊天历史"""
    logger.info(f"获取项目{project_id}聊天历史，用户：{user.id}")
    try:
        # 调用聊天服务获取聊天历史 - 修正API路径
        logger.info(f"调用聊天服务API: /chat/history/{project_id}")
        chat_service_url = ensure_url_protocol(chat_service.base_url)
        logger.info(f"聊天服务URL: {chat_service_url}")
        
        result = await chat_service.get(
            f"/chat/history/{project_id}",  # 使用正确的API路径
            params={}
        )
        logger.info(f"成功获取聊天历史，共{len(result) if isinstance(result, list) else '未知数量'}条消息")
        
        # 确保返回格式符合List[ChatMessage]
        if isinstance(result, dict) and "messages" in result:
            messages = result["messages"]
        elif isinstance(result, list):
            messages = result
        else:
            messages = []
            
        return messages
    except Exception as e:
        error_msg = f"获取聊天历史失败: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        # 当API返回404时，返回空列表而不是错误
        if "404" in str(e):
            logger.warning(f"聊天历史API返回404，项目可能没有历史聊天记录，返回空列表")
            return []
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/{project_id}/chat_history")
async def update_project_chat_history(
    project_id: int,
    messages: List[ChatMessage],
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新项目聊天历史"""
    logger.info(f"更新项目{project_id}聊天历史，用户：{user.id}")
    try:
        # 调用聊天服务更新聊天历史
        chat_service_url = ensure_url_protocol(chat_service.base_url)
        logger.info(f"聊天服务URL: {chat_service_url}")
        
        result = await chat_service.post(
            f"/chat/history/{project_id}",
            json={"messages": messages}
        )
        
        return result
    except Exception as e:
        error_msg = f"更新聊天历史失败: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/{project_id}/chat/stream")
async def project_chat_stream(
    project_id: int,
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """项目聊天流式响应"""
    logger.info(f"项目{project_id}聊天流式请求，用户：{user.id}")
    
    # 获取请求JSON数据
    try:
        data = await request.json()
        message = data.get("message")
        logger.debug(f"收到消息: {message[:50]}...")  # 只记录消息前50个字符
        
        if not message:
            return JSONResponse(
                status_code=400,
                content={"error": "No message provided"}
            )
            
        # 准备请求参数
        payload = {
            "message": message,
            "project_id": project_id,
            "user_id": user.id,
            "username": user.username
        }
        
        # 添加可选参数
        system_prompt = data.get("system_prompt")
        if system_prompt:
            payload["system_prompt"] = system_prompt

        # 调用聊天服务API获取流式响应
        async def stream_from_service():
            try:
                # 通过服务发现获取聊天服务URL
                from src.shared.service_discovery import get_service_url
                import httpx
                
                # 获取聊天服务URL
                chat_service_url = await get_service_url("chat")
                if not chat_service_url:
                    # 回退到配置的URL
                    chat_service_url = ensure_url_protocol(chat_service.base_url)
                    logger.info(f"服务发现未找到chat服务，使用配置的URL: {chat_service_url}")
                else:
                    logger.info(f"通过服务发现获取到chat服务URL: {chat_service_url}")
                
                # 构建完整的API路径
                chat_url = f"{chat_service_url}/chat/stream"
                logger.info(f"调用聊天服务URL: {chat_url}")
                logger.info(f"请求数据: {payload}")
                
                # 使用httpx发送流式请求
                async with httpx.AsyncClient() as client:
                    try:
                        # 使用stream方法处理流式响应
                        async with client.stream('POST', chat_url, 
                                               json=payload, 
                                               headers={'Content-Type': 'application/json'},
                                               timeout=300.0) as response:
                            # 确保响应状态码正常
                            if response.status_code != 200:
                                error_msg = f"聊天服务返回错误: {response.status_code}"
                                logger.error(error_msg)
                                error_text = await response.aread()
                                logger.error(f"响应内容: {error_text.decode('utf-8', errors='replace')}")
                                error_json = json.dumps({"error": error_msg})
                                yield f"data: {error_json}\n\n".encode('utf-8')
                                yield f"data: {json.dumps({'content': '', 'done': True})}\n\n".encode('utf-8')
                                return
                            
                            logger.info("聊天服务连接成功，开始流式传输")
                            # 从流式响应中读取数据并转发
                            async for chunk in response.aiter_bytes():
                                if chunk:
                                    yield chunk
                            
                            # 如果没有明确的结束标记，添加一个
                            yield f"data: {json.dumps({'content': '', 'done': True})}\n\n".encode('utf-8')
                    except httpx.RequestError as e:
                        logger.error(f"与聊天服务通信错误: {str(e)}")
                        logger.error(traceback.format_exc())
                        error_json = json.dumps({"error": f"连接聊天服务失败: {str(e)}"})
                        yield f"data: {error_json}\n\n".encode('utf-8')
                        yield f"data: {json.dumps({'content': '', 'done': True})}\n\n".encode('utf-8')
            
            except Exception as e:
                logger.error(f"流式调用聊天服务失败: {str(e)}")
                logger.error(traceback.format_exc())
                error_json = json.dumps({"error": f"处理请求时出错: {str(e)}"})
                yield f"data: {error_json}\n\n".encode('utf-8')
                yield f"data: {json.dumps({'content': '', 'done': True})}\n\n".encode('utf-8')
        
        # 返回流式响应
        return StreamingResponse(
            content=stream_from_service(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
        
    except Exception as e:
        error_msg = f"聊天流处理失败: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # 创建错误流
        async def error_stream():
            error_json = json.dumps({"error": error_msg})
            yield f"data: {error_json}\n\n".encode('utf-8')
            yield f"data: {json.dumps({'content': '', 'done': True})}\n\n".encode('utf-8')
        
        return StreamingResponse(
            content=error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )

@router.delete("/{project_id}/chat_history/clear", response_model=ApiResponse)
async def clear_project_chat_history(
    project_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """清除项目聊天历史"""
    logger.info(f"清除项目{project_id}聊天历史，用户：{user.id}")
    try:
        # 调用聊天服务清除聊天历史
        chat_service_url = ensure_url_protocol(chat_service.base_url)
        logger.info(f"聊天服务URL: {chat_service_url}")
        
        result = await chat_service.delete(
            f"/chat/history/{project_id}/clear"
        )
        
        return ApiResponse(
            success=True,
            message="Chat history cleared successfully"
        )
    except Exception as e:
        error_msg = f"清除聊天历史失败: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg) 