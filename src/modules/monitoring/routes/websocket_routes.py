#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
系统监控告警WebSocket路由
实时推送系统监控告警给管理员界面
"""

import json
import asyncio
import logging
from typing import Dict, Set, Optional, List
from enum import Enum
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta
import psutil
import time

from src.shared.logger import get_logger

logger = get_logger(__name__)

class AlertLevel(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertCategory(str, Enum):
    """告警类别"""
    SYSTEM = "system"
    SERVICE = "service"
    DATABASE = "database"
    NETWORK = "network"
    STORAGE = "storage"

# 监控WebSocket连接管理器
class MonitoringConnectionManager:
    """监控WebSocket连接管理器"""
    
    def __init__(self):
        # 管理员连接集合（无项目区分）
        self.admin_connections: Set[WebSocket] = set()
        # 项目特定的监控连接
        self.project_connections: Dict[str, Set[WebSocket]] = {}
        # 告警历史缓存 (最近100条)
        self.alert_history: List[dict] = []
        # 系统指标缓存
        self.system_metrics: Dict[str, any] = {}
        # 最大历史记录数
        self.max_history = 100
    
    async def connect_admin(self, websocket: WebSocket):
        """接受管理员WebSocket连接"""
        await websocket.accept()
        self.admin_connections.add(websocket)
        logger.info(f"管理员监控WebSocket已连接, 当前连接数: {len(self.admin_connections)}")
        
        # 发送历史告警给新连接的管理员
        if self.alert_history:
            try:
                await websocket.send_text(json.dumps({
                    "type": "alert_history",
                    "data": self.alert_history[-10:],  # 最近10条
                    "timestamp": datetime.now().isoformat()
                }, ensure_ascii=False))
            except Exception as e:
                logger.warning(f"发送告警历史失败: {str(e)}")
        
        # 发送当前系统指标
        if self.system_metrics:
            try:
                await websocket.send_text(json.dumps({
                    "type": "system_metrics",
                    "data": self.system_metrics,
                    "timestamp": datetime.now().isoformat()
                }, ensure_ascii=False))
            except Exception as e:
                logger.warning(f"发送系统指标失败: {str(e)}")
    
    async def connect_project(self, websocket: WebSocket, project_id: str):
        """接受项目特定的监控连接"""
        await websocket.accept()
        
        if project_id not in self.project_connections:
            self.project_connections[project_id] = set()
        
        self.project_connections[project_id].add(websocket)
        logger.info(f"项目 {project_id} 监控WebSocket已连接, 当前连接数: {len(self.project_connections[project_id])}")
    
    def disconnect_admin(self, websocket: WebSocket):
        """断开管理员WebSocket连接"""
        self.admin_connections.discard(websocket)
        logger.info(f"管理员监控WebSocket已断开连接")
    
    def disconnect_project(self, websocket: WebSocket, project_id: str):
        """断开项目特定的监控连接"""
        if project_id in self.project_connections:
            self.project_connections[project_id].discard(websocket)
            
            # 如果项目没有连接了，清理
            if not self.project_connections[project_id]:
                del self.project_connections[project_id]
                
        logger.info(f"项目 {project_id} 监控WebSocket已断开连接")
    
    async def send_alert(self, alert_data: dict, project_id: Optional[str] = None):
        """发送告警到连接的客户端"""
        # 添加时间戳
        alert_data["timestamp"] = datetime.now().isoformat()
        alert_data["id"] = f"alert-{int(time.time() * 1000)}"
        
        # 添加到历史记录
        self.alert_history.append(alert_data)
        
        # 保持历史记录在限制内
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
        
        # 准备消息
        message = {
            "type": "alert",
            "data": alert_data,
            "timestamp": alert_data["timestamp"]
        }
        
        message_str = json.dumps(message, ensure_ascii=False)
        
        # 发送给管理员连接
        disconnected_admins = set()
        for connection in self.admin_connections.copy():
            try:
                await connection.send_text(message_str)
                logger.debug(f"告警已发送到管理员连接")
            except Exception as e:
                logger.warning(f"发送告警到管理员失败: {str(e)}")
                disconnected_admins.add(connection)
        
        # 清理断开的管理员连接
        for connection in disconnected_admins:
            self.admin_connections.discard(connection)
        
        # 如果指定了项目，也发送给项目连接
        if project_id and project_id in self.project_connections:
            disconnected_projects = set()
            for connection in self.project_connections[project_id].copy():
                try:
                    await connection.send_text(message_str)
                    logger.debug(f"告警已发送到项目 {project_id}")
                except Exception as e:
                    logger.warning(f"发送告警到项目 {project_id} 失败: {str(e)}")
                    disconnected_projects.add(connection)
            
            # 清理断开的项目连接
            for connection in disconnected_projects:
                self.project_connections[project_id].discard(connection)
    
    async def send_system_metrics(self, metrics_data: dict):
        """发送系统指标更新"""
        # 更新缓存
        self.system_metrics.update(metrics_data)
        
        message = {
            "type": "system_metrics",
            "data": metrics_data,
            "timestamp": datetime.now().isoformat()
        }
        
        message_str = json.dumps(message, ensure_ascii=False)
        
        # 只发送给管理员连接
        disconnected_admins = set()
        for connection in self.admin_connections.copy():
            try:
                await connection.send_text(message_str)
                logger.debug(f"系统指标已发送到管理员")
            except Exception as e:
                logger.warning(f"发送系统指标失败: {str(e)}")
                disconnected_admins.add(connection)
        
        # 清理断开的连接
        for connection in disconnected_admins:
            self.admin_connections.discard(connection)
    
    async def send_service_status(self, service_status: dict):
        """发送服务状态更新"""
        message = {
            "type": "service_status",
            "data": service_status,
            "timestamp": datetime.now().isoformat()
        }
        
        message_str = json.dumps(message, ensure_ascii=False)
        
        # 发送给管理员连接
        disconnected_admins = set()
        for connection in self.admin_connections.copy():
            try:
                await connection.send_text(message_str)
                logger.debug(f"服务状态已发送到管理员")
            except Exception as e:
                logger.warning(f"发送服务状态失败: {str(e)}")
                disconnected_admins.add(connection)
        
        # 清理断开的连接
        for connection in disconnected_admins:
            self.admin_connections.discard(connection)
    
    def get_connection_stats(self) -> dict:
        """获取连接统计信息"""
        project_total = sum(len(connections) for connections in self.project_connections.values())
        return {
            "admin_connections": len(self.admin_connections),
            "project_connections": project_total,
            "projects_with_connections": len(self.project_connections),
            "project_details": {
                project_id: len(connections) 
                for project_id, connections in self.project_connections.items()
            },
            "alert_history_count": len(self.alert_history)
        }

# 全局连接管理器实例
monitoring_connection_manager = MonitoringConnectionManager()

# 创建路由器
monitoring_websocket_router = APIRouter(tags=["监控WebSocket"])

@monitoring_websocket_router.websocket("/ws/monitoring/admin")
async def websocket_admin_monitoring_endpoint(websocket: WebSocket):
    """
    管理员监控WebSocket端点
    
    连接格式: ws://host:port/api/ws/monitoring/admin
    
    消息格式:
    {
        "type": "alert" | "system_metrics" | "service_status" | "alert_history",
        "timestamp": "ISO格式时间戳",
        "data": {...}
    }
    """
    await monitoring_connection_manager.connect_admin(websocket)
    
    try:
        # 发送欢迎消息
        welcome_message = {
            "type": "connection_established",
            "message": "已连接到系统监控管理员界面"
        }
        await websocket.send_text(json.dumps(welcome_message, ensure_ascii=False))
        
        # 保持连接并处理管理员消息
        while True:
            try:
                # 等待管理员消息
                data = await websocket.receive_text()
                logger.debug(f"收到管理员监控消息: {data}")
                
                # 处理管理员消息
                try:
                    admin_message = json.loads(data)
                    message_type = admin_message.get("type")
                    
                    if message_type == "ping":
                        # 响应心跳
                        pong_message = {
                            "type": "pong",
                            "timestamp": admin_message.get("timestamp")
                        }
                        await websocket.send_text(json.dumps(pong_message, ensure_ascii=False))
                    
                    elif message_type == "request_system_metrics":
                        # 管理员请求当前系统指标
                        current_metrics = await get_current_system_metrics()
                        await websocket.send_text(json.dumps({
                            "type": "system_metrics",
                            "data": current_metrics,
                            "timestamp": datetime.now().isoformat()
                        }, ensure_ascii=False))
                    
                    elif message_type == "request_alert_history":
                        # 管理员请求告警历史
                        count = admin_message.get("count", 10)
                        history = monitoring_connection_manager.alert_history[-count:]
                        await websocket.send_text(json.dumps({
                            "type": "alert_history",
                            "data": history,
                            "timestamp": datetime.now().isoformat()
                        }, ensure_ascii=False))
                            
                except json.JSONDecodeError:
                    logger.warning(f"无法解析管理员消息: {data}")
                    
            except WebSocketDisconnect:
                logger.info(f"管理员主动断开监控连接")
                break
            except Exception as e:
                logger.error(f"处理管理员监控WebSocket消息时出错: {str(e)}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"管理员监控WebSocket连接断开")
    except Exception as e:
        logger.error(f"管理员监控WebSocket连接错误: {str(e)}")
    finally:
        monitoring_connection_manager.disconnect_admin(websocket)

@monitoring_websocket_router.websocket("/ws/monitoring/project/{project_id}")
async def websocket_project_monitoring_endpoint(websocket: WebSocket, project_id: str):
    """
    项目特定监控WebSocket端点
    
    连接格式: ws://host:port/api/ws/monitoring/project/{project_id}
    """
    await monitoring_connection_manager.connect_project(websocket, project_id)
    
    try:
        # 发送欢迎消息
        welcome_message = {
            "type": "connection_established",
            "project_id": project_id,
            "message": f"已连接到项目 {project_id} 的监控"
        }
        await websocket.send_text(json.dumps(welcome_message, ensure_ascii=False))
        
        # 保持连接
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"收到项目 {project_id} 监控消息: {data}")
                
                # 简单的心跳处理
                try:
                    client_message = json.loads(data)
                    if client_message.get("type") == "ping":
                        pong_message = {
                            "type": "pong",
                            "timestamp": client_message.get("timestamp")
                        }
                        await websocket.send_text(json.dumps(pong_message, ensure_ascii=False))
                except json.JSONDecodeError:
                    logger.warning(f"无法解析项目监控消息: {data}")
                    
            except WebSocketDisconnect:
                logger.info(f"项目 {project_id} 主动断开监控连接")
                break
            except Exception as e:
                logger.error(f"处理项目监控WebSocket消息时出错: {str(e)}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"项目 {project_id} 监控WebSocket连接断开")
    except Exception as e:
        logger.error(f"项目监控WebSocket连接错误: {str(e)}")
    finally:
        monitoring_connection_manager.disconnect_project(websocket, project_id)

async def get_current_system_metrics() -> dict:
    """获取当前系统指标"""
    try:
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存使用情况
        memory = psutil.virtual_memory()
        
        # 磁盘使用情况
        disk = psutil.disk_usage('/')
        
        # 网络IO
        net_io = psutil.net_io_counters()
        
        return {
            "cpu": {
                "usage_percent": cpu_percent,
                "count": psutil.cpu_count()
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "usage_percent": memory.percent
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "usage_percent": (disk.used / disk.total) * 100
            },
            "network": {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            }
        }
    except Exception as e:
        logger.error(f"获取系统指标失败: {str(e)}")
        return {}

@monitoring_websocket_router.get("/ws/monitoring/stats")
async def get_monitoring_websocket_stats():
    """获取监控WebSocket连接统计信息"""
    return monitoring_connection_manager.get_connection_stats()

@monitoring_websocket_router.post("/api/monitoring/alert")
async def send_test_alert(alert_data: dict):
    """发送测试告警（API端点）"""
    await monitoring_connection_manager.send_alert(alert_data)
    return {"message": "告警已发送"}

@monitoring_websocket_router.get("/ws/monitoring/test", response_class=HTMLResponse)
async def monitoring_websocket_test_page():
    """监控WebSocket测试页面"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>系统监控WebSocket测试</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            #messages { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; margin: 10px 0; }
            .message { margin: 5px 0; padding: 5px; border-left: 3px solid #007cba; }
            .alert { border-left-color: #dc3545; background-color: #fff5f5; }
            .metrics { border-left-color: #28a745; background-color: #f8fff8; }
            .service-status { border-left-color: #ffc107; background-color: #fffdf0; }
            input, button, select { padding: 8px; margin: 5px; }
            .controls { margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>系统监控WebSocket测试</h1>
        <div class="controls">
            <label>连接类型: </label>
            <select id="connectionType">
                <option value="admin">管理员监控</option>
                <option value="project">项目监控</option>
            </select>
            <input type="text" id="projectId" value="test_project" placeholder="项目ID（项目监控时需要）" style="display:none;">
            <button onclick="connect()">连接</button>
            <button onclick="disconnect()">断开</button>
            <button onclick="sendPing()">发送心跳</button>
        </div>
        <div class="controls">
            <button onclick="requestMetrics()">请求系统指标</button>
            <button onclick="requestAlertHistory()">请求告警历史</button>
            <button onclick="sendTestAlert()">发送测试告警</button>
        </div>
        <div>
            <strong>连接状态: </strong><span id="status">未连接</span>
        </div>
        <div id="messages"></div>
        
        <script>
            let websocket = null;
            const messagesDiv = document.getElementById('messages');
            const statusSpan = document.getElementById('status');
            const connectionType = document.getElementById('connectionType');
            const projectIdInput = document.getElementById('projectId');
            
            connectionType.onchange = function() {
                if (connectionType.value === 'project') {
                    projectIdInput.style.display = 'inline-block';
                } else {
                    projectIdInput.style.display = 'none';
                }
            };
            
            function addMessage(message, className = '') {
                const div = document.createElement('div');
                div.className = `message ${className}`;
                div.innerHTML = `<strong>${new Date().toLocaleTimeString()}:</strong> ${message}`;
                messagesDiv.appendChild(div);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
            
            function connect() {
                if (websocket) {
                    websocket.close();
                }
                
                let wsUrl;
                if (connectionType.value === 'admin') {
                    wsUrl = 'ws://localhost:8008/api/ws/monitoring/admin';
                } else {
                    const projectId = projectIdInput.value;
                    if (!projectId) {
                        addMessage('请输入项目ID', 'alert');
                        return;
                    }
                    wsUrl = `ws://localhost:8008/api/ws/monitoring/project/${projectId}`;
                }
                
                addMessage(`连接到监控WebSocket: ${wsUrl}`);
                
                websocket = new WebSocket(wsUrl);
                
                websocket.onopen = function() {
                    statusSpan.textContent = '已连接';
                    statusSpan.style.color = 'green';
                    addMessage('监控WebSocket连接已建立', 'metrics');
                };
                
                websocket.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);
                        let className = '';
                        if (data.type === 'alert') className = 'alert';
                        else if (data.type === 'system_metrics') className = 'metrics';
                        else if (data.type === 'service_status') className = 'service-status';
                        
                        addMessage(`收到消息 [${data.type}]: ${JSON.stringify(data, null, 2)}`, className);
                    } catch (e) {
                        addMessage(`收到文本消息: ${event.data}`);
                    }
                };
                
                websocket.onclose = function() {
                    statusSpan.textContent = '已断开';
                    statusSpan.style.color = 'red';
                    addMessage('监控WebSocket连接已关闭', 'alert');
                };
                
                websocket.onerror = function(error) {
                    addMessage(`连接错误: ${error}`, 'alert');
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
                    addMessage('WebSocket未连接', 'alert');
                }
            }
            
            function requestMetrics() {
                if (websocket && websocket.readyState === WebSocket.OPEN && connectionType.value === 'admin') {
                    const message = {
                        type: 'request_system_metrics',
                        timestamp: new Date().toISOString()
                    };
                    websocket.send(JSON.stringify(message));
                    addMessage('已请求系统指标');
                } else {
                    addMessage('仅管理员连接可请求系统指标', 'alert');
                }
            }
            
            function requestAlertHistory() {
                if (websocket && websocket.readyState === WebSocket.OPEN && connectionType.value === 'admin') {
                    const message = {
                        type: 'request_alert_history',
                        count: 5,
                        timestamp: new Date().toISOString()
                    };
                    websocket.send(JSON.stringify(message));
                    addMessage('已请求告警历史');
                } else {
                    addMessage('仅管理员连接可请求告警历史', 'alert');
                }
            }
            
            function sendTestAlert() {
                // 通过HTTP API发送测试告警
                fetch('/api/monitoring/alert', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        level: 'warning',
                        category: 'system',
                        title: '测试告警',
                        message: '这是一个测试告警消息',
                        source: 'test_system'
                    })
                })
                .then(response => response.json())
                .then(data => {
                    addMessage('测试告警已发送: ' + JSON.stringify(data));
                })
                .catch(error => {
                    addMessage('发送测试告警失败: ' + error, 'alert');
                });
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# 导出连接管理器，供其他模块使用
__all__ = ["monitoring_websocket_router", "monitoring_connection_manager", "AlertLevel", "AlertCategory"]