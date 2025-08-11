import sys
import logging
from src.shared.logger import initialize_logging, get_logger
from pathlib import Path
import contextlib
import os
from urllib.parse import urlparse
import asyncio
import traceback
import json
# 导入服务发现模块
from src.shared.service_discovery import call_service, get_service_url

# 添加项目根目录到PATH
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

# 加载项目根目录.env文件
from dotenv import load_dotenv
env_file = root_dir / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
    print(f"已从 {env_file} 加载环境变量")
else:
    print(f"警告: 未找到.env文件在 {env_file}")

# 从URL中提取端口号
def get_port_from_url(url, default_port):
    if not url:
        return default_port
    try:
        parsed = urlparse(url)
        return parsed.port or default_port
    except Exception:
        return default_port

# 从环境变量读取配置
project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8000")
API_PORT = get_port_from_url(project_service_url, 8000)

LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() in ("true", "1", "t")
SERVICE_NAME = os.getenv("SERVICE_NAME", "lumidoc-webui")
SERVICE_ID = os.getenv("SERVICE_ID", None)  # 如未提供则自动生成

# FastAPI 相关导入
from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
import uvicorn

# 导入本地模块
from Lumidoc_webui.backend.middleware import setup_middleware
from Lumidoc_webui.backend.utils.system_check import system_checker
from src.database import init_db, ensure_connection, get_connection_status
from src.shared.health_check import register_health_service, get_system_info, create_health_middleware

# 导入API路由器
from Lumidoc_webui.backend.api.project_routes import router as project_router
from Lumidoc_webui.backend.api.file_routes import router as file_router
from Lumidoc_webui.backend.api.chat_routes import router as chat_router
from Lumidoc_webui.backend.api.graph_routes import router as graph_router
from Lumidoc_webui.backend.api.rag_routes import router as rag_router
from Lumidoc_webui.backend.api.auth_routes import router as user_router
from Lumidoc_webui.backend.api.monitoring_routes import router as monitoring_router
from Lumidoc_webui.backend.api.question_routes import router as question_router
from Lumidoc_webui.backend.routers.api_router import router as custom_api_router

# 初始化日志
initialize_logging(SERVICE_NAME)
logger = get_logger(__name__)

# 全局变量来跟踪系统检查状态
_system_checked = False

# 定义lifespan上下文管理器替代on_event
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    global _system_checked
    # 只在应用启动时执行一次系统检查
    if not _system_checked:
        logger.info("开始系统启动检查...")
        
        # 系统状态检查
        logger.info("进行系统状态检查...")
        system_checker.run_all_checks()
        
        # 初始化数据库
        try:
            logger.info("正在初始化数据库...")
            if init_db():
                logger.info("数据库初始化成功")
            else:
                logger.error("数据库初始化失败，尝试重新连接...")
                # 尝试重连数据库
                if ensure_connection():
                    logger.info("数据库重连成功")
                else:
                    logger.error("数据库重连失败，服务可能无法正常工作")
        except Exception as e:
            logger.error(f"数据库初始化过程中出错: {str(e)}")
            # 如果数据库初始化失败，继续运行但记录错误
            
        db_status, db_message = system_checker.check_database()
        if not db_status:
            logger.error(f"数据库检查失败: {db_message}")
            # 这里不再中断启动，让系统继续尝试运行
        else:
            logger.info(f"数据库检查成功: {db_message}")
            
        # 打印系统信息
        system_info = get_system_info()
        logger.info(f"系统信息: {system_info}")
        
        _system_checked = True
        logger.info("应用启动完成")
    
    yield  # 此处暂停，应用运行
    
    # 关闭时执行
    logger.info("应用即将关闭...")
    # 这里可以添加清理资源的代码

# 创建 FastAPI 应用
app = FastAPI(
    title="STP Backend API",
    description="STP 项目后端 API 服务",
    version="1.0.0",
    lifespan=lifespan,
    debug=DEBUG_MODE
)

# 设置中间件 - 包含认证中间件
setup_middleware(app)

# 添加健康检查中间件
app.middleware("http")(create_health_middleware())

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"全局异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "服务器内部错误", "details": str(exc)},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP异常: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

# 挂载静态文件
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 注册路由
app.include_router(file_router)
app.include_router(project_router)
app.include_router(chat_router)
app.include_router(graph_router)
app.include_router(rag_router)
app.include_router(user_router)
app.include_router(question_router)
app.include_router(monitoring_router)
app.include_router(custom_api_router)

@app.get("/")
async def root():
    """根路径，返回欢迎信息"""
    return {"message": "Welcome to STP WebUI API", "version": "1.0.0", "status": "running"}

@app.get("/system-info")
async def system_information():
    """获取系统信息"""
    return get_system_info()

@app.get("/db-status")
async def db_status():
    """获取数据库连接状态"""
    return get_connection_status()

# 启动健康检查服务
@app.on_event("startup")
async def startup_event():
    """启动事件处理"""
    try:
        await register_health_service(app, SERVICE_NAME, SERVICE_ID)
    except Exception as e:
        logger.error(f"注册健康检查服务失败: {str(e)}")

# 添加直接处理项目文件的路由，但现在会受到认证中间件检查
@app.get("/projects/{project_id}/files")
async def get_project_files(project_id: int, request: Request):
    """获取项目文件列表（转发到文件服务）"""
    from Lumidoc_webui.backend.api.services import file_service
    import urllib.parse
    
    logger.info(f"获取项目{project_id}文件列表")
    try:
        # 从请求头中获取认证令牌
        auth_header = request.headers.get("Authorization")
        headers = {"Authorization": auth_header} if auth_header else {}
        
        # 调用文件服务API获取项目文件列表
        result = await file_service.get(
            f"/projects/{project_id}/files",
            headers=headers
        )
        
        # 处理文件名，确保中文显示正确
        if isinstance(result, list):
            for file in result:
                if 'filename' in file and file['filename']:
                    try:
                        # 解码URL编码的文件名
                        file['display_name'] = urllib.parse.unquote(file['filename'])
                    except:
                        file['display_name'] = file['filename']
        
        logger.info(f"成功获取项目文件列表，项目ID: {project_id}")
        return result
    except Exception as e:
        logger.error(f"获取项目文件列表失败: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": f"获取项目文件列表失败: {str(e)}"},
        )

@app.post("/projects/{project_id}/files/upload")
async def upload_project_file(project_id: int, request: Request):
    """上传项目文件（转发到文件服务）"""
    from Lumidoc_webui.backend.api.services import file_service
    from src.shared.service_discovery import get_service_url
    import httpx
    
    logger.info(f"上传文件到项目{project_id}")
    try:
        # 从请求头中获取认证令牌
        auth_header = request.headers.get("Authorization")
        
        try:
            # 从请求中读取表单数据
            form_data = await request.form()
            
            # 提取所有文件对象
            file_objects = []
            file_field_names = []
            
            # 查找所有文件字段 - 支持file[0], file[1]等索引格式
            for key, value in form_data.items():
                if hasattr(value, "file") and hasattr(value, "filename"):
                    file_objects.append(value)
                    file_field_names.append(key)
                    logger.info(f"找到文件字段: {key}, 文件名: {value.filename}, 类型: {value.content_type}")
            
            if not file_objects:
                logger.error("上传请求中没有找到文件")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "没有找到要上传的文件"},
                )
            
            # 获取文件计数（如果前端提供）
            file_count = form_data.get("fileCount")
            if file_count:
                logger.info(f"前端报告的文件数量: {file_count}")
                
            logger.info(f"上传文件数量: {len(file_objects)}, 文件字段名: {file_field_names}")
            
            # 创建自定义headers，包括认证信息
            headers = {}
            if auth_header:
                headers["Authorization"] = auth_header
            
            # 提取非文件表单字段
            form_fields = {}
            for key, value in form_data.items():
                if key not in file_field_names:
                    form_fields[key] = value
                    
            logger.info(f"表单字段: {form_fields}")
            
            # 通过服务发现获取文件服务URL
            file_service_url = await get_service_url("file")
            if not file_service_url:
                # 回退到配置的URL
                file_service_url = file_service.base_url
                logger.info(f"服务发现未找到file服务，使用配置的URL: {file_service_url}")
            else:
                logger.info(f"通过服务发现获取到file服务URL: {file_service_url}")
            
            # 构建完整的API路径
            api_path = f"/projects/{project_id}/files/upload"
            upload_url = f"{file_service_url}{api_path}"
            logger.info(f"文件上传URL: {upload_url}")
            
            # 支持的文件类型（仅用于处理）
            supported_extensions = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.txt', '.md', '.csv']
            
            # 处理所有文件上传
            results = []
            for i, file_obj in enumerate(file_objects):
                logger.info(f"处理文件 {i+1}/{len(file_objects)}: {file_obj.filename}")
                
                # 检查文件类型
                file_ext = os.path.splitext(file_obj.filename)[1].lower()
                should_process = 'process' in form_fields and str(form_fields['process']).lower() == 'true'
                
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
                
                try:
                    # 读取文件内容
                    content = await file_obj.read()
                    # 重置文件流位置，以便可以再次读取
                    await file_obj.seek(0)
                    
                    logger.info(f"已读取文件内容: {file_obj.filename}, 大小: {len(content)} 字节")
                    
                    # 准备multipart表单数据
                    files = {"file": (file_obj.filename, content, file_obj.content_type)}
                    data = {k: str(v) for k, v in form_fields.items()}
                    
                    # 添加处理标志
                    if "process" not in data:
                        data["process"] = "true"
                        
                    # 记录重试次数
                    retry_count = 0
                    max_retries = 3
                    last_error = None
                    
                    while retry_count < max_retries:
                        try:
                            # 使用httpx发送文件上传请求
                            async with httpx.AsyncClient() as client:
                                logger.info(f"发送上传请求（尝试 {retry_count+1}/{max_retries}）: {file_obj.filename} 到 {upload_url}")
                                
                                # 设置超时时间
                                response = await client.post(
                                    upload_url,
                                    files=files,
                                    data=data,
                                    headers=headers,
                                    timeout=60.0  # 增加超时时间到60秒
                                )
                                
                                status = response.status_code
                                logger.info(f"文件 {file_obj.filename} 上传状态码: {status}")
                                
                                if status != 200:
                                    # 如果请求失败，准备重试
                                    error_text = response.text
                                    logger.error(f"文件 {file_obj.filename} 上传失败，状态码: {status}, 响应内容: {error_text}")
                                    last_error = f"状态码: {status}, 响应: {error_text}"
                                    retry_count += 1
                                    
                                    # 如果是致命错误，不再重试
                                    if status in [400, 403, 404]:
                                        break
                                        
                                    # 等待一段时间后重试
                                    await asyncio.sleep(1)
                                    continue
                                
                                # 处理成功响应
                                try:
                                    file_result = response.json()
                                    logger.info(f"文件服务响应: {file_result}")
                                    if isinstance(file_result, dict):
                                        # 确保结果中包含原始文件名
                                        if 'filename' not in file_result:
                                            file_result['filename'] = file_obj.filename
                                        file_result['success'] = True
                                        
                                        # 检查是否需要处理文件
                                        if 'process' in form_fields and form_fields['process'].lower() == 'true':
                                            logger.info(f"需要处理文件: {file_obj.filename}，准备调用处理API")
                                            try:
                                                # 构建处理文件的API请求
                                                process_url = f"{file_service_url}/projects/{project_id}/files/process"
                                                file_path = file_result.get('path', file_result.get('filename', file_obj.filename))
                                                
                                                # 检查文件是否已存在（通过exists字段）
                                                if file_result.get('exists', False):
                                                    logger.info(f"文件已存在，使用已有记录: {file_obj.filename}")
                                                    # 如果文件已存在，检查状态
                                                    if file_result.get('status') == 'completed':
                                                        logger.info(f"文件已处理完成，无需重新处理: {file_obj.filename}")
                                                        file_result['processing'] = False
                                                        # 添加到结果列表 - 只添加一次
                                                        results.append(file_result)
                                                        break
                                                
                                                # 发送处理请求
                                                async with httpx.AsyncClient() as process_client:
                                                    process_response = await process_client.post(
                                                        process_url,
                                                        json={"file_path": file_path, "process_type": "docling"},
                                                        headers=headers,
                                                        timeout=30.0
                                                    )
                                                    
                                                    if process_response.status_code == 200:
                                                        process_result = process_response.json()
                                                        logger.info(f"文件处理请求成功: {process_result}")
                                                        # 将处理状态添加到结果中
                                                        file_result['processing'] = True
                                                        file_result['processing_id'] = process_result.get('task_id', '')
                                                    else:
                                                        logger.error(f"文件处理请求失败: {process_response.status_code}, {process_response.text}")
                                                        file_result['processing'] = False
                                                        file_result['processing_error'] = f"处理请求失败: {process_response.status_code}"
                                            except Exception as process_error:
                                                logger.error(f"发送文件处理请求时出错: {str(process_error)}")
                                                logger.error(traceback.format_exc())
                                                file_result['processing'] = False
                                                file_result['processing_error'] = f"处理请求异常: {str(process_error)}"
                                        
                                        # 添加到结果列表 - 只添加一次
                                        results.append(file_result)
                                    else:
                                        results.append({
                                            "filename": file_obj.filename,
                                            "success": True,
                                            "message": "文件上传成功，但响应格式异常"
                                        })
                                    
                                    # 成功处理后跳出重试循环
                                    break
                                except Exception as json_error:
                                    logger.error(f"解析文件服务响应时出错: {str(json_error)}")
                                    last_error = f"解析响应失败: {str(json_error)}"
                                    retry_count += 1
                                    await asyncio.sleep(1)
                        except Exception as req_error:
                            logger.error(f"文件 {file_obj.filename} 上传请求时出错: {str(req_error)}")
                            last_error = f"请求错误: {str(req_error)}"
                            retry_count += 1
                            await asyncio.sleep(1)
                    
                    # 如果重试次数用完还是失败，记录错误
                    if retry_count == max_retries:
                        logger.error(f"上传失败，已达最大重试次数: {file_obj.filename}")
                        results.append({
                            "filename": file_obj.filename,
                            "success": False,
                            "message": f"上传失败: {last_error}"
                        })
                        
                except Exception as read_error:
                    # 处理文件读取错误
                    logger.error(f"读取文件内容时出错: {str(read_error)}")
                    logger.error(traceback.format_exc())
                    results.append({
                        "filename": file_obj.filename,
                        "success": False,
                        "message": f"读取文件失败: {str(read_error)}"
                    })
            
            # 汇总所有文件的上传结果
            successful_uploads = sum(1 for r in results if r.get("success", False))
            failed_uploads = len(results) - successful_uploads
            
            logger.info(f"所有文件上传完成: 成功 {successful_uploads}, 失败 {failed_uploads}")
            
            response_data = {
                "success": successful_uploads > 0,
                "files": results,
                "total": len(results),
                "successful": successful_uploads,
                "failed": failed_uploads,
                "message": f"上传完成: {successful_uploads}个文件成功，{failed_uploads}个文件失败"
            }
            
            return JSONResponse(
                status_code=200,
                content=response_data
            )
            
        except Exception as form_error:
            logger.error(f"处理表单数据失败: {str(form_error)}")
            logger.error(traceback.format_exc())
            return JSONResponse(
                status_code=500,
                content={"detail": f"处理表单数据失败: {str(form_error)}"}
            )
            
    except Exception as e:
        logger.error(f"上传文件处理失败: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": f"上传文件处理失败: {str(e)}"}
        )

@app.get("/projects/{project_id}/rag/files")
async def get_rag_files(project_id: int, request: Request):
    """获取RAG文件列表（转发到文件服务）"""
    from Lumidoc_webui.backend.api.services import file_service
    
    logger.info(f"获取项目{project_id}的RAG文件列表")
    try:
        # 从请求头中获取认证令牌
        auth_header = request.headers.get("Authorization")
        headers = {"Authorization": auth_header} if auth_header else {}
        
        # 调用文件服务API获取项目RAG文件列表
        result = await file_service.get(
            f"/projects/{project_id}/rag/files",
            headers=headers
        )
        logger.info(f"成功获取项目RAG文件列表，项目ID: {project_id}")
        return result
    except Exception as e:
        logger.error(f"获取项目RAG文件列表失败: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": f"获取项目RAG文件列表失败: {str(e)}"},
        )

@app.get("/projects/{project_id}/files/download/{file_name:path}")
async def download_project_file(project_id: int, file_name: str, request: Request):
    """下载项目文件（转发到文件服务）"""
    from fastapi.responses import StreamingResponse, HTMLResponse
    from Lumidoc_webui.backend.api.services import file_service
    from src.shared.service_discovery import get_service_url
    import httpx
    
    logger.info(f"下载项目{project_id}文件: {file_name}")
    try:
        # 从请求头中获取认证令牌
        auth_header = request.headers.get("Authorization")
        headers = {"Authorization": auth_header} if auth_header else {}
        
        # 处理请求头中的Accept字段，判断是下载还是预览
        accept_header = request.headers.get("Accept", "")
        # 通过查询参数明确区分预览和下载
        is_preview = "preview" in request.query_params or ("text/html" in accept_header and not request.query_params.get("download"))
        
        # 添加内容类型映射
        content_types = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif"
        }
        
        # 从文件名确定内容类型
        file_ext = os.path.splitext(file_name)[1].lower()
        content_type = content_types.get(file_ext, "application/octet-stream")
        
        # 对文件路径进行解码，确保中文字符正确处理
        try:
            # 如果文件名已经是解码状态，避免重复解码
            from urllib.parse import unquote
            decoded_file_name = unquote(file_name)
        except:
            decoded_file_name = file_name
        
        logger.info(f"处理文件: {decoded_file_name}, 内容类型: {content_type}, 预览模式: {is_preview}")
        
        # 构建查询参数
        params = {}
        if is_preview:
            params["preview"] = "1"
        
        # 从请求中获取所有查询参数并传递
        for k, v in request.query_params.items():
            params[k] = v
            
        # 通过服务发现获取文件服务URL
        file_service_url = await get_service_url("file")
        if not file_service_url:
            # 回退到配置的URL
            file_service_url = file_service.base_url
            logger.info(f"服务发现未找到file服务，使用配置的URL: {file_service_url}")
        else:
            logger.info(f"通过服务发现获取到file服务URL: {file_service_url}")
        
        # 构建完整的API路径
        api_path = f"/projects/{project_id}/files/download/{decoded_file_name}"
        download_url = f"{file_service_url}{api_path}"
        logger.info(f"文件下载URL: {download_url}, 参数: {params}")
        
        # 使用httpx直接调用文件服务API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    download_url,
                    params=params,
                    headers=headers,
                    timeout=60.0  # 增加超时时间以处理大文件
                )
                
                # 检查响应状态
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"文件下载失败: {response.status_code} - {error_text}")
                    return JSONResponse(
                        status_code=response.status_code,
                        content={"detail": f"文件下载失败: {error_text}"}
                    )
                
                # 读取文件内容
                file_data = await response.aread()
            
            # 创建异步生成器返回文件内容
            async def send_file():
                yield file_data
            
            # 特别处理PDF预览
            if is_preview and file_ext == '.pdf':
                logger.info("使用特殊处理预览PDF文件")
                
                # 设置响应头，确保正确的内容类型和内联显示
                response_headers = {
                    "Content-Type": "application/pdf",
                    "Content-Disposition": f"inline; filename=\"{file_name}\"",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
                
                # 使用StreamingResponse直接返回PDF数据
                return StreamingResponse(
                    send_file(),
                    media_type="application/pdf",
                    headers=response_headers
                )
            
            # 根据是预览还是下载设置不同的响应头
            response_headers = {
                "Content-Type": content_type,
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
            
            # 如果是下载操作，添加Content-Disposition头
            if not is_preview:
                response_headers["Content-Disposition"] = f"attachment; filename=\"{file_name}\""
            else:
                # 如果是预览，设置为inline
                response_headers["Content-Disposition"] = f"inline; filename=\"{file_name}\""
            
            # 使用StreamingResponse返回文件，设置正确的content-type和内容处置
            return StreamingResponse(
                send_file(),
                media_type=content_type,
                headers=response_headers
            )
            
        except Exception as http_error:
            logger.error(f"HTTP调用文件服务失败: {str(http_error)}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"调用文件服务失败: {str(http_error)}"}
            )
            
    except Exception as e:
        logger.error(f"下载文件时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": f"下载文件时出错: {str(e)}"},
        )

@app.delete("/projects/{project_id}/files/{file_name:path}")
async def delete_project_file(project_id: int, file_name: str, request: Request):
    """删除项目文件（转发到文件服务）"""
    from Lumidoc_webui.backend.api.services import file_service
    from src.shared.service_discovery import get_service_url
    from Lumidoc_webui.backend.api.project_routes import ensure_url_protocol
    import httpx
    
    logger.info(f"删除项目{project_id}文件: {file_name}")
    try:
        # 从请求头中获取认证令牌
        auth_header = request.headers.get("Authorization")
        headers = {"Authorization": auth_header} if auth_header else {}
        
        # 对文件路径进行解码，确保中文字符正确处理
        try:
            from urllib.parse import unquote
            decoded_file_name = unquote(file_name)
        except Exception as decode_error:
            logger.error(f"解码文件名失败: {str(decode_error)}")
            decoded_file_name = file_name
        
        logger.info(f"解码后的文件路径: {decoded_file_name}")
        
        try:
            # 通过服务发现获取文件服务URL
            file_service_url = await get_service_url("file")
            if not file_service_url:
                # 回退到配置的URL
                file_service_url = ensure_url_protocol(file_service.base_url)
                logger.info(f"服务发现未找到file服务，使用配置的URL: {file_service_url}")
            else:
                logger.info(f"通过服务发现获取到file服务URL: {file_service_url}")
            
            # 构建完整的API路径
            api_path = f"/projects/{project_id}/files/{decoded_file_name}"
            delete_url = f"{file_service_url}{api_path}"
            logger.info(f"文件删除URL: {delete_url}")
            
            # 使用httpx直接调用文件服务API
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    delete_url,
                    headers=headers,
                    timeout=30.0
                )
                
                # 如果是404错误，说明文件不存在，这种情况我们也视为删除成功
                if response.status_code == 404:
                    logger.warning(f"文件不存在，但仍视为删除成功: {decoded_file_name}")
                    return JSONResponse(
                        status_code=200,
                        content={"success": True, "message": f"文件不存在或已被删除: {decoded_file_name}"}
                    )
                
                # 检查其他错误响应
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"文件删除失败: {response.status_code} - {error_text}")
                    # 返回原始状态码
                    return JSONResponse(
                        status_code=response.status_code,
                        content={"detail": f"文件删除失败: {error_text}"}
                    )
                
                # 删除成功
                logger.info(f"成功删除项目{project_id}文件: {decoded_file_name}")
                return JSONResponse(
                    status_code=200,
                    content={"success": True, "message": f"文件已成功删除: {decoded_file_name}"}
                )
                
        except httpx.RequestError as e:
            logger.error(f"调用文件服务失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"调用文件服务失败: {str(e)}")
            
        # 这部分代码可能永远不会执行到，但作为备份保留
        '''
        # 构建正确的文件服务API路径
        file_api_path = f"/projects/{project_id}/files/{decoded_file_name}"
        logger.info(f"将请求发送到文件服务API路径: {file_api_path}")
        
        # 使用ServiceClient调用文件服务删除API
        result = await file_service.delete(
            file_api_path,
            headers=headers
        )
        
        logger.info(f"文件服务响应: {result}")
        
        # 处理响应
        if result:
            logger.info(f"成功删除项目{project_id}文件: {decoded_file_name}")
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": f"文件已成功删除: {decoded_file_name}"}
            )
        else:
            logger.warning(f"文件服务返回空响应")
            # 如果响应为空但没有抛出异常，仍视为成功
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": f"文件已成功删除: {decoded_file_name}"}
            )
        '''
    except Exception as e:
        error_msg = f"删除文件失败: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # 检查是否是404错误
        if "404" in str(e) or "Not Found" in str(e):
            logger.warning(f"文件不存在(404)，但仍视为删除成功: {decoded_file_name}")
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": f"文件不存在或已被删除: {file_name}"}
            )
            
        return JSONResponse(
            status_code=500,
            content={"detail": error_msg},
        )

# 添加直接处理用户项目权限的路由
@app.get("/api/user_permissions/projects")
async def get_user_project_permissions(request: Request):
    """获取用户的项目权限列表（转发到项目服务）"""
    from Lumidoc_webui.backend.api.services import project_service
    
    logger.info("获取用户项目权限列表")
    try:
        # 从请求头中获取认证令牌
        auth_header = request.headers.get("Authorization")
        headers = {"Authorization": auth_header} if auth_header else {}
        
        # 调用项目服务API获取用户项目权限
        result = await project_service.get(
            "/api/user_permissions/projects",
            headers=headers
        )
        logger.info("成功获取用户项目权限列表")
        return result
    except Exception as e:
        logger.error(f"获取用户项目权限列表失败: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": f"获取用户项目权限列表失败: {str(e)}"},
        )

@app.post("/projects/{project_id}/files/process")
async def process_project_file(project_id: int, request: Request):
    """处理项目文件（转发到文件服务）"""
    from Lumidoc_webui.backend.api.services import file_service
    from src.shared.service_discovery import get_service_url
    from Lumidoc_webui.backend.api.project_routes import ensure_url_protocol
    import httpx
    import os
    
    logger.info(f"处理项目{project_id}文件")
    try:
        # 从请求头中获取认证令牌
        auth_header = request.headers.get("Authorization")
        headers = {"Authorization": auth_header} if auth_header else {}
        
        # 获取请求数据
        data = await request.json()
        file_path = data.get("file_path")
        process_type = data.get("process_type", "docling")
        
        if not file_path:
            return JSONResponse(
                status_code=400,
                content={"detail": "缺少必要参数: file_path"}
            )
            
        logger.info(f"准备处理文件: {file_path}, 类型: {process_type}")
        
        # 验证文件类型
        file_ext = os.path.splitext(file_path)[1].lower()
        supported_extensions = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.txt', '.md', '.csv']
        
        if file_ext not in supported_extensions:
            error_msg = f"不支持处理的文件类型: {file_ext}"
            logger.warning(f"{error_msg}, 文件: {file_path}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": error_msg,
                    "file_path": file_path
                }
            )
        
        # 通过服务发现获取文件服务URL
        file_service_url = await get_service_url("file")
        if not file_service_url:
            # 回退到配置的URL
            file_service_url = ensure_url_protocol(file_service.base_url)
            logger.info(f"服务发现未找到file服务，使用配置的URL: {file_service_url}")
        else:
            logger.info(f"通过服务发现获取到file服务URL: {file_service_url}")
        
        # 构建处理API路径
        process_url = f"{file_service_url}/projects/{project_id}/files/process"
        logger.info(f"文件处理URL: {process_url}")
        
        # 发送处理请求
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    process_url,
                    json={"file_path": file_path, "process_type": process_type},
                    headers=headers,
                    timeout=30.0
                )
                
                # 检查响应状态
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"文件处理失败: {response.status_code} - {error_text}")
                    return JSONResponse(
                        status_code=response.status_code,
                        content={"detail": f"文件处理失败: {error_text}"}
                    )
                
                # 返回处理结果
                result = response.json()
                logger.info(f"文件处理请求成功发送，任务ID: {result.get('task_id', 'unknown')}")
                
                # 确保返回结果包含必要的字段
                if 'success' not in result:
                    result['success'] = True
                if 'message' not in result:
                    result['message'] = "文件处理请求已提交"
                if 'file_path' not in result:
                    result['file_path'] = file_path
                    
                return result
        except httpx.RequestError as e:
            logger.error(f"HTTP请求错误: {str(e)}")
            logger.error(traceback.format_exc())
            return JSONResponse(
                status_code=500,
                content={"detail": f"调用文件服务失败: {str(e)}"}
            )
            
    except Exception as e:
        error_msg = f"处理文件请求失败: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": error_msg}
        )

@app.get("/projects/{project_id}/files/content/{file_name:path}")
async def get_project_file_content(project_id: int, file_name: str, request: Request):
    """获取项目文件内容（转发到文件服务）"""
    from fastapi.responses import JSONResponse, Response
    from Lumidoc_webui.backend.api.services import file_service
    from src.shared.service_discovery import get_service_url
    import httpx
    
    logger.info(f"获取项目{project_id}文件内容: {file_name}")
    try:
        # 从请求头中获取认证令牌
        auth_header = request.headers.get("Authorization")
        headers = {"Authorization": auth_header} if auth_header else {}
        
        # 对文件路径进行解码，确保中文字符正确处理
        try:
            from urllib.parse import unquote
            decoded_file_name = unquote(file_name)
        except:
            decoded_file_name = file_name
        
        logger.info(f"处理文件内容请求: {decoded_file_name}")
        
        # 通过服务发现获取文件服务URL
        file_service_url = await get_service_url("file")
        if not file_service_url:
            # 回退到配置的URL
            file_service_url = file_service.base_url
            logger.info(f"服务发现未找到file服务，使用配置的URL: {file_service_url}")
        else:
            logger.info(f"通过服务发现获取到file服务URL: {file_service_url}")
        
        # 构建完整的API路径 - 使用file_hash作为参数
        # 首先获取文件信息以获取file_hash
        file_info_path = f"/projects/{project_id}/files/info/{decoded_file_name}"
        file_info_url = f"{file_service_url}{file_info_path}"
        
        # 获取文件信息
        async with httpx.AsyncClient() as client:
            file_info_response = await client.get(
                file_info_url,
                headers=headers,
                timeout=30.0
            )
            
            if file_info_response.status_code != 200:
                error_text = file_info_response.text
                logger.error(f"获取文件信息失败: {file_info_response.status_code} - {error_text}")
                return Response(
                    content=json.dumps({"detail": f"获取文件信息失败: {error_text}"}),
                    status_code=file_info_response.status_code,
                    media_type="application/json"
                )
            
            # 解析文件信息响应
            file_info = file_info_response.json()
            
            if not file_info.get("success", False):
                logger.error(f"文件信息获取失败: {file_info.get('message', '未知错误')}")
                return Response(
                    content=json.dumps({"detail": f"文件不存在: {decoded_file_name}"}),
                    status_code=404,
                    media_type="application/json"
                )
            
            # 获取文件哈希值
            file_hash = file_info.get("file_hash")
            if not file_hash:
                logger.error(f"文件哈希值不存在: {decoded_file_name}")
                return Response(
                    content=json.dumps({"detail": f"文件哈希值不存在: {decoded_file_name}"}),
                    status_code=404,
                    media_type="application/json"
                )
            
            # 构建内容API路径
            content_path = f"/content/{project_id}/{file_hash}"
            content_url = f"{file_service_url}{content_path}"
            
            # 获取文件内容
            content_response = await client.get(
                content_url,
                headers=headers,
                timeout=60.0  # 增加超时时间以处理大文件
            )
            
            if content_response.status_code != 200:
                error_text = content_response.text
                logger.error(f"获取文件内容失败: {content_response.status_code} - {error_text}")
                return Response(
                    content=json.dumps({"detail": f"获取文件内容失败: {error_text}"}),
                    status_code=content_response.status_code,
                    media_type="application/json"
                )
            
            # 获取内容响应
            content_data = content_response.json()
            
            # 检查内容是否存在
            if not content_data.get("success", False):
                logger.error(f"文件内容获取失败: {content_data.get('message', '未知错误')}")
                return Response(
                    content=json.dumps({"detail": f"文件内容不存在: {decoded_file_name}"}),
                    status_code=404,
                    media_type="application/json"
                )
            
            # 从内容响应中提取data部分
            content_result = content_data.get("data", {})
            
            # 构建最终响应
            response_data = {
                "success": True,
                "file_hash": file_hash,
                "filename": decoded_file_name,
                "content": content_result.get("markdown_content", ""),
                "metadata": content_result.get("metadata", {}),
                "file_type": content_result.get("file_type", ""),
                "page_count": content_result.get("page_count", 0)
            }
            
            # 显式设置响应类型为application/json
            return Response(
                content=json.dumps(response_data),
                status_code=200,
                media_type="application/json",
                headers={"Content-Type": "application/json"}
            )
            
    except Exception as e:
        logger.error(f"获取文件内容时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return Response(
            content=json.dumps({"detail": f"获取文件内容时出错: {str(e)}"}),
            status_code=500,
            media_type="application/json",
            headers={"Content-Type": "application/json"}
        )

if __name__ == "__main__":
    # 直接使用 uvicorn.run 启动服务器，不启用重载
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=API_PORT,
        reload=DEBUG_MODE,
        workers=1,
        log_level=LOG_LEVEL
    ) 