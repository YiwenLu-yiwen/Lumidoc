#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
知识图谱实时更新WebSocket路由
实时推送图谱变化给前端
"""

import json
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from datetime import datetime

from src.shared.logger import get_logger

logger = get_logger(__name__)

# WebSocket连接管理器
class GraphConnectionManager:
    """知识图谱WebSocket连接管理器"""
    
    def __init__(self):
        # 项目ID -> WebSocket连接集合
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # 图谱更新缓存，用于新连接时同步当前状态
        self.graph_state_cache: Dict[str, dict] = {}
    
    async def connect(self, websocket: WebSocket, project_id: str):
        """接受WebSocket连接"""
        await websocket.accept()
        
        if project_id not in self.active_connections:
            self.active_connections[project_id] = set()
        
        self.active_connections[project_id].add(websocket)
        logger.info(f"图谱WebSocket客户端已连接到项目 {project_id}, 当前连接数: {len(self.active_connections[project_id])}")
        
        # 如果有缓存的图谱状态，发送给新连接的客户端
        if project_id in self.graph_state_cache:
            try:
                await websocket.send_text(json.dumps({
                    "type": "graph_state_sync",
                    "project_id": project_id,
                    "data": self.graph_state_cache[project_id],
                    "timestamp": datetime.now().isoformat()
                }, ensure_ascii=False))
                logger.info(f"已向新连接发送图谱状态同步: {project_id}")
            except Exception as e:
                logger.warning(f"发送图谱状态同步失败: {str(e)}")
    
    def disconnect(self, websocket: WebSocket, project_id: str):
        """断开WebSocket连接"""
        if project_id in self.active_connections:
            self.active_connections[project_id].discard(websocket)
            
            # 如果项目没有连接了，清理
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
                
        logger.info(f"图谱WebSocket客户端已断开连接，项目: {project_id}")
    
    async def send_graph_update(self, project_id: str, update_data: dict):
        """发送图谱更新到指定项目的所有连接"""
        if project_id not in self.active_connections:
            logger.debug(f"项目 {project_id} 没有活跃的图谱WebSocket连接")
            return
        
        # 更新缓存
        if project_id not in self.graph_state_cache:
            self.graph_state_cache[project_id] = {"nodes": [], "relationships": []}
        
        # 根据更新类型更新缓存
        update_type = update_data.get("update_type", "full")
        if update_type == "add_node":
            node_data = update_data.get("node")
            if node_data:
                # 检查节点是否已存在，如果存在则更新，否则添加
                existing_nodes = self.graph_state_cache[project_id]["nodes"]
                updated = False
                for i, existing_node in enumerate(existing_nodes):
                    if existing_node.get("id") == node_data.get("id"):
                        existing_nodes[i] = node_data
                        updated = True
                        break
                if not updated:
                    existing_nodes.append(node_data)
        elif update_type == "add_relationship":
            rel_data = update_data.get("relationship")
            if rel_data:
                # 检查关系是否已存在，如果存在则更新，否则添加
                existing_rels = self.graph_state_cache[project_id]["relationships"]
                updated = False
                for i, existing_rel in enumerate(existing_rels):
                    if (existing_rel.get("source") == rel_data.get("source") and 
                        existing_rel.get("target") == rel_data.get("target") and
                        existing_rel.get("type") == rel_data.get("type")):
                        existing_rels[i] = rel_data
                        updated = True
                        break
                if not updated:
                    existing_rels.append(rel_data)
        elif update_type == "full":
            # 完全替换缓存
            self.graph_state_cache[project_id] = update_data.get("graph", {"nodes": [], "relationships": []})
        
        # 准备消息数据
        message = {
            "type": "graph_update",
            "project_id": project_id,
            "timestamp": datetime.now().isoformat(),
            "data": update_data
        }
        
        message_str = json.dumps(message, ensure_ascii=False)
        
        # 发送给所有连接的客户端
        disconnected_connections = set()
        
        for connection in self.active_connections[project_id].copy():
            try:
                await connection.send_text(message_str)
                logger.debug(f"图谱更新已发送到项目 {project_id}")
            except Exception as e:
                logger.warning(f"发送图谱更新失败: {str(e)}")
                disconnected_connections.add(connection)
        
        # 清理断开的连接
        for connection in disconnected_connections:
            self.active_connections[project_id].discard(connection)
    
    async def send_graph_statistics(self, project_id: str, stats_data: dict):
        """发送图谱统计信息"""
        if project_id not in self.active_connections:
            logger.debug(f"项目 {project_id} 没有活跃的图谱WebSocket连接")
            return
        
        message = {
            "type": "graph_statistics",
            "project_id": project_id,
            "timestamp": datetime.now().isoformat(),
            "data": stats_data
        }
        
        message_str = json.dumps(message, ensure_ascii=False)
        
        # 发送给所有连接的客户端
        disconnected_connections = set()
        
        for connection in self.active_connections[project_id].copy():
            try:
                await connection.send_text(message_str)
                logger.info(f"图谱统计已发送到项目 {project_id}")
            except Exception as e:
                logger.warning(f"发送图谱统计失败: {str(e)}")
                disconnected_connections.add(connection)
        
        # 清理断开的连接
        for connection in disconnected_connections:
            self.active_connections[project_id].discard(connection)
    
    async def send_processing_status(self, project_id: str, status_data: dict):
        """发送图谱处理状态"""
        if project_id not in self.active_connections:
            logger.debug(f"项目 {project_id} 没有活跃的图谱WebSocket连接")
            return
        
        message = {
            "type": "processing_status",
            "project_id": project_id,
            "timestamp": datetime.now().isoformat(),
            "data": status_data
        }
        
        message_str = json.dumps(message, ensure_ascii=False)
        
        # 发送给所有连接的客户端
        disconnected_connections = set()
        
        for connection in self.active_connections[project_id].copy():
            try:
                await connection.send_text(message_str)
                logger.info(f"图谱处理状态已发送到项目 {project_id}")
            except Exception as e:
                logger.warning(f"发送图谱处理状态失败: {str(e)}")
                disconnected_connections.add(connection)
        
        # 清理断开的连接
        for connection in disconnected_connections:
            self.active_connections[project_id].discard(connection)
    
    def get_connection_stats(self) -> dict:
        """获取连接统计信息"""
        total_connections = sum(len(connections) for connections in self.active_connections.values())
        return {
            "total_connections": total_connections,
            "projects_with_connections": len(self.active_connections),
            "project_details": {
                project_id: len(connections) 
                for project_id, connections in self.active_connections.items()
            },
            "cached_projects": len(self.graph_state_cache)
        }

# 全局连接管理器实例
graph_connection_manager = GraphConnectionManager()

# 创建路由器
graph_websocket_router = APIRouter(tags=["图谱WebSocket"])

@graph_websocket_router.websocket("/ws/graph/{project_id}")
async def websocket_graph_endpoint(websocket: WebSocket, project_id: str):
    """
    知识图谱实时更新WebSocket端点
    
    连接格式: ws://host:port/api/ws/graph/{project_id}
    
    消息格式:
    {
        "type": "graph_update" | "graph_statistics" | "processing_status" | "graph_state_sync",
        "project_id": "string",
        "timestamp": "ISO格式时间戳",
        "data": {...}
    }
    """
    await graph_connection_manager.connect(websocket, project_id)
    
    try:
        # 发送欢迎消息
        welcome_message = {
            "type": "connection_established",
            "project_id": project_id,
            "message": f"已连接到项目 {project_id} 的图谱实时更新"
        }
        await websocket.send_text(json.dumps(welcome_message, ensure_ascii=False))
        
        # 保持连接并处理客户端消息
        while True:
            try:
                # 等待客户端消息
                data = await websocket.receive_text()
                logger.debug(f"收到来自项目 {project_id} 的图谱客户端消息: {data}")
                
                # 处理客户端消息
                try:
                    client_message = json.loads(data)
                    message_type = client_message.get("type")
                    
                    if message_type == "ping":
                        # 响应心跳
                        pong_message = {
                            "type": "pong",
                            "timestamp": client_message.get("timestamp")
                        }
                        await websocket.send_text(json.dumps(pong_message, ensure_ascii=False))
                    
                    elif message_type == "request_graph_state":
                        # 客户端请求当前图谱状态
                        if project_id in graph_connection_manager.graph_state_cache:
                            state_message = {
                                "type": "graph_state_response",
                                "project_id": project_id,
                                "data": graph_connection_manager.graph_state_cache[project_id],
                                "timestamp": datetime.now().isoformat()
                            }
                            await websocket.send_text(json.dumps(state_message, ensure_ascii=False))
                        else:
                            error_message = {
                                "type": "error",
                                "message": f"项目 {project_id} 没有缓存的图谱状态"
                            }
                            await websocket.send_text(json.dumps(error_message, ensure_ascii=False))
                            
                except json.JSONDecodeError:
                    logger.warning(f"无法解析图谱客户端消息: {data}")
                    
            except WebSocketDisconnect:
                logger.info(f"图谱客户端主动断开连接，项目: {project_id}")
                break
            except Exception as e:
                logger.error(f"处理图谱WebSocket消息时出错: {str(e)}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"图谱WebSocket连接断开，项目: {project_id}")
    except Exception as e:
        logger.error(f"图谱WebSocket连接错误: {str(e)}")
    finally:
        graph_connection_manager.disconnect(websocket, project_id)

@graph_websocket_router.get("/ws/graph/stats")
async def get_graph_websocket_stats():
    """获取图谱WebSocket连接统计信息"""
    return graph_connection_manager.get_connection_stats()

@graph_websocket_router.get("/ws/graph/test", response_class=HTMLResponse)
async def graph_websocket_test_page():
    """图谱WebSocket测试页面"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>知识图谱WebSocket测试</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            #messages { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; margin: 10px 0; }
            .message { margin: 5px 0; padding: 5px; border-left: 3px solid #007cba; }
            .graph-update { border-left-color: #28a745; background-color: #f8fff8; }
            .statistics { border-left-color: #ffc107; background-color: #fffdf0; }
            .error { border-left-color: #dc3545; background-color: #fff5f5; }
            input, button { padding: 8px; margin: 5px; }
            .controls { margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>知识图谱WebSocket测试</h1>
        <div class="controls">
            <label>项目ID: </label>
            <input type="text" id="projectId" value="test_project" placeholder="输入项目ID">
            <button onclick="connect()">连接</button>
            <button onclick="disconnect()">断开</button>
            <button onclick="sendPing()">发送心跳</button>
            <button onclick="requestGraphState()">请求图谱状态</button>
        </div>
        <div class="controls">
            <button onclick="simulateNodeAdd()">模拟添加节点</button>
            <button onclick="simulateRelationAdd()">模拟添加关系</button>
            <button onclick="simulateStatistics()">模拟统计更新</button>
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
                
                const wsUrl = `ws://localhost:8003/api/ws/graph/${projectId}`;
                addMessage(`连接到图谱WebSocket: ${wsUrl}`);
                
                websocket = new WebSocket(wsUrl);
                
                websocket.onopen = function() {
                    statusSpan.textContent = '已连接';
                    statusSpan.style.color = 'green';
                    addMessage('图谱WebSocket连接已建立', 'graph-update');
                };
                
                websocket.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);
                        let className = '';
                        if (data.type === 'graph_update') className = 'graph-update';
                        else if (data.type === 'graph_statistics') className = 'statistics';
                        else if (data.type === 'error') className = 'error';
                        
                        addMessage(`收到消息 [${data.type}]: ${JSON.stringify(data, null, 2)}`, className);
                    } catch (e) {
                        addMessage(`收到文本消息: ${event.data}`);
                    }
                };
                
                websocket.onclose = function() {
                    statusSpan.textContent = '已断开';
                    statusSpan.style.color = 'red';
                    addMessage('图谱WebSocket连接已关闭', 'error');
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
            
            function requestGraphState() {
                if (websocket && websocket.readyState === WebSocket.OPEN) {
                    const message = {
                        type: 'request_graph_state',
                        timestamp: new Date().toISOString()
                    };
                    websocket.send(JSON.stringify(message));
                    addMessage('已请求图谱状态');
                } else {
                    addMessage('WebSocket未连接', 'error');
                }
            }
            
            function simulateNodeAdd() {
                addMessage('注意: 这只是前端模拟，实际节点添加需要通过后端API', 'statistics');
            }
            
            function simulateRelationAdd() {
                addMessage('注意: 这只是前端模拟，实际关系添加需要通过后端API', 'statistics');
            }
            
            function simulateStatistics() {
                addMessage('注意: 这只是前端模拟，实际统计更新需要通过后端API', 'statistics');
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# 导出连接管理器，供其他模块使用
__all__ = ["graph_websocket_router", "graph_connection_manager"]