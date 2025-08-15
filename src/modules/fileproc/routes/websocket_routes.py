#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件处理进度WebSocket路由
实时推送文档处理进度给前端
"""

import json
import asyncio
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import HTMLResponse

from src.shared.logger import get_logger

logger = get_logger(__name__)

# WebSocket连接管理器
class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        # 项目ID -> WebSocket连接集合
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # 任务ID -> 项目ID映射
        self.task_project_mapping: Dict[str, str] = {}
    
    async def connect(self, websocket: WebSocket, project_id: str):
        """接受WebSocket连接"""
        await websocket.accept()
        
        if project_id not in self.active_connections:
            self.active_connections[project_id] = set()
        
        self.active_connections[project_id].add(websocket)
        logger.info(f"WebSocket客户端已连接到项目 {project_id}, 当前连接数: {len(self.active_connections[project_id])}")
    
    def disconnect(self, websocket: WebSocket, project_id: str):
        """断开WebSocket连接"""
        if project_id in self.active_connections:
            self.active_connections[project_id].discard(websocket)
            
            # 如果项目没有连接了，清理
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
                
        logger.info(f"WebSocket客户端已断开连接，项目: {project_id}")
    
    async def send_progress_update(self, project_id: str, task_id: str, progress_data: dict):
        """发送进度更新到指定项目的所有连接"""
        if project_id not in self.active_connections:
            logger.debug(f"项目 {project_id} 没有活跃的WebSocket连接")
            return
        
        # 准备消息数据
        message = {
            "type": "progress_update",
            "task_id": task_id,
            "project_id": project_id,
            "timestamp": progress_data.get("timestamp"),
            "data": progress_data
        }
        
        message_str = json.dumps(message, ensure_ascii=False)
        
        # 发送给所有连接的客户端
        disconnected_connections = set()
        
        for connection in self.active_connections[project_id].copy():
            try:
                await connection.send_text(message_str)
                logger.debug(f"进度更新已发送到项目 {project_id}, 任务 {task_id}")
            except Exception as e:
                logger.warning(f"发送进度更新失败: {str(e)}")
                disconnected_connections.add(connection)
        
        # 清理断开的连接
        for connection in disconnected_connections:
            self.active_connections[project_id].discard(connection)
    
    async def send_task_completion(self, project_id: str, task_id: str, result_data: dict):
        """发送任务完成通知"""
        if project_id not in self.active_connections:
            logger.debug(f"项目 {project_id} 没有活跃的WebSocket连接")
            return
        
        message = {
            "type": "task_completed",
            "task_id": task_id,
            "project_id": project_id,
            "timestamp": result_data.get("timestamp"),
            "data": result_data
        }
        
        message_str = json.dumps(message, ensure_ascii=False)
        
        # 发送给所有连接的客户端
        disconnected_connections = set()
        
        for connection in self.active_connections[project_id].copy():
            try:
                await connection.send_text(message_str)
                logger.info(f"任务完成通知已发送到项目 {project_id}, 任务 {task_id}")
            except Exception as e:
                logger.warning(f"发送任务完成通知失败: {str(e)}")
                disconnected_connections.add(connection)
        
        # 清理断开的连接
        for connection in disconnected_connections:
            self.active_connections[project_id].discard(connection)
    
    async def send_error_notification(self, project_id: str, task_id: str, error_data: dict):
        """发送错误通知"""
        if project_id not in self.active_connections:
            logger.debug(f"项目 {project_id} 没有活跃的WebSocket连接")
            return
        
        message = {
            "type": "task_error",
            "task_id": task_id,
            "project_id": project_id,
            "timestamp": error_data.get("timestamp"),
            "data": error_data
        }
        
        message_str = json.dumps(message, ensure_ascii=False)
        
        # 发送给所有连接的客户端
        disconnected_connections = set()
        
        for connection in self.active_connections[project_id].copy():
            try:
                await connection.send_text(message_str)
                logger.error(f"错误通知已发送到项目 {project_id}, 任务 {task_id}")
            except Exception as e:
                logger.warning(f"发送错误通知失败: {str(e)}")
                disconnected_connections.add(connection)
        
        # 清理断开的连接
        for connection in disconnected_connections:
            self.active_connections[project_id].discard(connection)
    
    def register_task_project(self, task_id: str, project_id: str):
        """注册任务与项目的映射"""
        self.task_project_mapping[task_id] = project_id
        logger.debug(f"任务 {task_id} 已映射到项目 {project_id}")
    
    def get_project_for_task(self, task_id: str) -> str:
        """获取任务对应的项目ID"""
        return self.task_project_mapping.get(task_id)
    
    def get_connection_stats(self) -> dict:
        """获取连接统计信息"""
        total_connections = sum(len(connections) for connections in self.active_connections.values())
        return {
            "total_connections": total_connections,
            "projects_with_connections": len(self.active_connections),
            "project_details": {
                project_id: len(connections) 
                for project_id, connections in self.active_connections.items()
            }
        }

# 全局连接管理器实例
connection_manager = ConnectionManager()

# 创建路由器
websocket_router = APIRouter(tags=["WebSocket进度推送"])

@websocket_router.websocket("/ws/progress/{project_id}")
async def websocket_progress_endpoint(websocket: WebSocket, project_id: str):
    """
    文档处理进度WebSocket端点
    
    连接格式: ws://host:port/api/ws/progress/{project_id}
    
    消息格式:
    {
        "type": "progress_update" | "task_completed" | "task_error",
        "task_id": "string",
        "project_id": "string", 
        "timestamp": "ISO格式时间戳",
        "data": {...}
    }
    """
    await connection_manager.connect(websocket, project_id)
    
    try:
        # 发送欢迎消息
        welcome_message = {
            "type": "connection_established",
            "project_id": project_id,
            "message": f"已连接到项目 {project_id} 的处理进度推送"
        }
        await websocket.send_text(json.dumps(welcome_message, ensure_ascii=False))
        
        # 保持连接并处理客户端消息（如果有）
        while True:
            try:
                # 等待客户端消息
                data = await websocket.receive_text()
                logger.debug(f"收到来自项目 {project_id} 的客户端消息: {data}")
                
                # 这里可以处理客户端发送的消息，比如心跳包
                try:
                    client_message = json.loads(data)
                    if client_message.get("type") == "ping":
                        # 响应心跳
                        pong_message = {
                            "type": "pong",
                            "timestamp": client_message.get("timestamp")
                        }
                        await websocket.send_text(json.dumps(pong_message, ensure_ascii=False))
                except json.JSONDecodeError:
                    logger.warning(f"无法解析客户端消息: {data}")
                    
            except WebSocketDisconnect:
                logger.info(f"客户端主动断开连接，项目: {project_id}")
                break
            except Exception as e:
                logger.error(f"处理WebSocket消息时出错: {str(e)}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket连接断开，项目: {project_id}")
    except Exception as e:
        logger.error(f"WebSocket连接错误: {str(e)}")
    finally:
        connection_manager.disconnect(websocket, project_id)

@websocket_router.get("/ws/stats")
async def get_websocket_stats():
    """获取WebSocket连接统计信息"""
    return connection_manager.get_connection_stats()

@websocket_router.get("/ws/test", response_class=HTMLResponse)
async def websocket_test_page():
    """WebSocket测试页面"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>文档处理进度WebSocket测试</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            #messages { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; margin: 10px 0; }
            .message { margin: 5px 0; padding: 5px; border-left: 3px solid #007cba; }
            .error { border-left-color: #dc3545; }
            .success { border-left-color: #28a745; }
            input, button { padding: 8px; margin: 5px; }
        </style>
    </head>
    <body>
        <h1>文档处理进度WebSocket测试</h1>
        <div>
            <label>项目ID: </label>
            <input type="text" id="projectId" value="test_project" placeholder="输入项目ID">
            <button onclick="connect()">连接</button>
            <button onclick="disconnect()">断开</button>
            <button onclick="sendPing()">发送心跳</button>
        </div>
        <div>
            <strong>连接状态: </strong><span id="status">未连接</span>
        </div>
        <div id="messages"></div>
        
        <script>
            let websocket = null;
            const messagesDiv = document.getElementById('messages');
            const statusSpan = document.getElementById('status');
            
            function addMessage(message, className = '') {
                const div = document.createElement('div');
                div.className = `message ${className}`;
                div.innerHTML = `<strong>${new Date().toLocaleTimeString()}:</strong> ${message}`;
                messagesDiv.appendChild(div);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
            
            function connect() {
                const projectId = document.getElementById('projectId').value;
                if (!projectId) {
                    addMessage('请输入项目ID', 'error');
                    return;
                }
                
                if (websocket) {
                    websocket.close();
                }
                
                const wsUrl = `ws://localhost:8005/api/ws/progress/${projectId}`;
                addMessage(`连接到: ${wsUrl}`);
                
                websocket = new WebSocket(wsUrl);
                
                websocket.onopen = function() {
                    statusSpan.textContent = '已连接';
                    statusSpan.style.color = 'green';
                    addMessage('WebSocket连接已建立', 'success');
                };
                
                websocket.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);
                        addMessage(`收到消息: ${JSON.stringify(data, null, 2)}`);
                    } catch (e) {
                        addMessage(`收到文本消息: ${event.data}`);
                    }
                };
                
                websocket.onclose = function() {
                    statusSpan.textContent = '已断开';
                    statusSpan.style.color = 'red';
                    addMessage('WebSocket连接已关闭', 'error');
                };
                
                websocket.onerror = function(error) {
                    addMessage(`连接错误: ${error}`, 'error');
                };
            }
            
            function disconnect() {
                if (websocket) {
                    websocket.close();
                    websocket = null;
                }
            }
            
            function sendPing() {
                if (websocket && websocket.readyState === WebSocket.OPEN) {
                    const message = {
                        type: 'ping',
                        timestamp: new Date().toISOString()
                    };
                    websocket.send(JSON.stringify(message));
                    addMessage('已发送心跳包');
                } else {
                    addMessage('WebSocket未连接', 'error');
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# 导出连接管理器，供其他模块使用
__all__ = ["websocket_router", "connection_manager"]