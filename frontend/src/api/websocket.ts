/**
 * WebSocket API 客户端
 * 统一管理所有WebSocket连接
 */

import type { GraphEntity, GraphRelationship, GraphStatistics } from '../types/graph';

export interface WebSocketMessage {
  type: string;
  timestamp: string;
  data?: unknown;
  project_id?: string;
  task_id?: string;
}

export interface ProgressUpdate {
  type?: 'progress' | 'completed' | 'error';
  status: string;
  progress: number;
  stage: string;
  message: string;
  file_id?: string;
  processing_time?: number;
  result?: unknown;
  error?: string;
}

export interface GraphUpdate {
  update_type: 'add_node' | 'add_relationship' | 'full';
  node?: GraphEntity;
  relationship?: GraphRelationship;
  graph?: {
    nodes: GraphEntity[];
    relationships: GraphRelationship[];
  };
}

export type ProcessingStatus = Record<string, unknown>;
export type ServiceStatus = Record<string, unknown>;

export interface SystemAlert {
  level: 'info' | 'warning' | 'error' | 'critical';
  category: 'system' | 'service' | 'database' | 'network' | 'storage';
  title: string;
  message: string;
  source: string;
  id?: string;
  timestamp?: string;
}

export interface SystemMetrics {
  cpu: {
    usage_percent: number;
    count: number;
  };
  memory: {
    total: number;
    available: number;
    used: number;
    usage_percent: number;
  };
  disk: {
    total: number;
    used: number;
    free: number;
    usage_percent: number;
  };
  network: {
    bytes_sent: number;
    bytes_recv: number;
    packets_sent: number;
    packets_recv: number;
  };
}

export type WebSocketEventCallback = (message: WebSocketMessage) => void;

// 基础WebSocket客户端类
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private eventCallbacks: Map<string, WebSocketEventCallback[]> = new Map();
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private isConnected = false;

  constructor(url: string) {
    this.url = url;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log(`WebSocket连接已建立: ${this.url}`);
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            this.handleMessage(message);
          } catch {
            console.warn('无法解析WebSocket消息:', event.data);
          }
        };

        this.ws.onclose = (event) => {
          console.log(`WebSocket连接已关闭: ${this.url}, 代码: ${event.code}`);
          this.isConnected = false;
          this.stopHeartbeat();
          
          // 如果不是主动关闭，尝试重连
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
          }
        };

        this.ws.onerror = (error) => {
          console.error(`WebSocket错误: ${this.url}`, error);
          reject(error);
        };

      } catch (error) {
        reject(error);
      }
    });
  }

  disconnect(): void {
    if (this.ws) {
      this.stopHeartbeat();
      this.ws.close(1000, '客户端主动断开');
      this.ws = null;
      this.isConnected = false;
    }
  }

  private attemptReconnect(): void {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    
    console.log(`尝试重连WebSocket (${this.reconnectAttempts}/${this.maxReconnectAttempts}): ${this.url}`);
    
    setTimeout(() => {
      this.connect().catch((error) => {
        console.error('重连失败:', error);
      });
    }, delay);
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.isConnected) {
        this.send({
          type: 'ping',
          timestamp: new Date().toISOString()
        });
      }
    }, 30000); // 每30秒发送心跳
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  send(message: Record<string, unknown>): void {
    if (this.ws && this.isConnected) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket未连接，无法发送消息');
    }
  }

  private handleMessage(message: WebSocketMessage): void {
    // 处理pong响应
    if (message.type === 'pong') {
      return;
    }

    // 触发相应的事件回调
    const callbacks = this.eventCallbacks.get(message.type) || [];
    callbacks.forEach(callback => callback(message));

    // 触发通用事件回调
    const allCallbacks = this.eventCallbacks.get('*') || [];
    allCallbacks.forEach(callback => callback(message));
  }

  on(eventType: string, callback: WebSocketEventCallback): void {
    if (!this.eventCallbacks.has(eventType)) {
      this.eventCallbacks.set(eventType, []);
    }
    this.eventCallbacks.get(eventType)!.push(callback);
  }

  off(eventType: string, callback: WebSocketEventCallback): void {
    const callbacks = this.eventCallbacks.get(eventType);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  getConnectionState(): boolean {
    return this.isConnected;
  }
}

// 文档处理进度WebSocket客户端
export class FileProcessWebSocketClient extends WebSocketClient {
  constructor(projectId: string, customUrl?: string) {
    // 支持自定义URL或使用默认URL
    const url = customUrl || `ws://localhost:8005/api/ws/progress/${projectId}`;
    super(url);
  }

  onProgressUpdate(callback: (data: ProgressUpdate) => void): void {
    this.on('progress_update', (message) => {
      callback(message.data as ProgressUpdate);
    });
  }

  onTaskCompleted(callback: (data: ProgressUpdate) => void): void {
    this.on('task_completed', (message) => {
      callback(message.data as ProgressUpdate);
    });
  }

  onTaskError(callback: (data: ProgressUpdate) => void): void {
    this.on('task_error', (message) => {
      callback(message.data as ProgressUpdate);
    });
  }
}

// 知识图谱WebSocket客户端
export class GraphWebSocketClient extends WebSocketClient {
  constructor(projectId: string, customUrl?: string) {
    // 支持自定义URL或使用默认URL
    const url = customUrl || `ws://localhost:8003/api/ws/graph/${projectId}`;
    super(url);
  }

  onGraphUpdate(callback: (data: GraphUpdate) => void): void {
    this.on('graph_update', (message) => {
      callback(message.data as GraphUpdate);
    });
  }

  onGraphStatistics(callback: (data: GraphStatistics) => void): void {
    this.on('graph_statistics', (message) => {
      callback(message.data as GraphStatistics);
    });
  }

  onProcessingStatus(callback: (data: ProcessingStatus) => void): void {
    this.on('processing_status', (message) => {
      callback(message.data as ProcessingStatus);
    });
  }

  onGraphStateSync(callback: (data: NonNullable<GraphUpdate['graph']>) => void): void {
    this.on('graph_state_sync', (message) => {
      callback(message.data as NonNullable<GraphUpdate['graph']>);
    });
  }

  requestGraphState(): void {
    this.send({
      type: 'request_graph_state',
      timestamp: new Date().toISOString()
    });
  }
}

// 系统监控WebSocket客户端
export class MonitoringWebSocketClient extends WebSocketClient {
  constructor(type: 'admin' | 'project', projectIdOrUrl?: string, customUrl?: string) {
    let url: string;
    
    if (customUrl) {
      // 如果提供了自定义URL，直接使用
      url = customUrl;
    } else if (type === 'admin') {
      url = 'ws://localhost:8008/api/ws/monitoring/admin';
    } else {
      // project类型，第二个参数是projectId
      url = `ws://localhost:8008/api/ws/monitoring/project/${projectIdOrUrl}`;
    }
    
    super(url);
  }

  onAlert(callback: (data: SystemAlert) => void): void {
    this.on('alert', (message) => {
      callback(message.data as SystemAlert);
    });
  }

  onSystemMetrics(callback: (data: SystemMetrics) => void): void {
    this.on('system_metrics', (message) => {
      callback(message.data as SystemMetrics);
    });
  }

  onServiceStatus(callback: (data: ServiceStatus) => void): void {
    this.on('service_status', (message) => {
      callback(message.data as ServiceStatus);
    });
  }

  onAlertHistory(callback: (data: SystemAlert[]) => void): void {
    this.on('alert_history', (message) => {
      callback(message.data as SystemAlert[]);
    });
  }

  requestSystemMetrics(): void {
    this.send({
      type: 'request_system_metrics',
      timestamp: new Date().toISOString()
    });
  }

  requestAlertHistory(count: number = 10): void {
    this.send({
      type: 'request_alert_history',
      count,
      timestamp: new Date().toISOString()
    });
  }
}

// WebSocket管理器 - 统一管理所有连接
export class WebSocketManager {
  private connections: Map<string, WebSocketClient> = new Map();

  // 创建文档处理进度连接
  async createFileProcessConnection(projectId: string): Promise<FileProcessWebSocketClient> {
    const key = `fileproc-${projectId}`;
    let client = this.connections.get(key) as FileProcessWebSocketClient;
    
    if (!client) {
      // 尝试通过服务发现获取WebSocket URL
      let wsUrl: string | null = null;
      try {
        const { getFileProcessWebSocketUrl } = await import('./serviceDiscovery');
        wsUrl = await getFileProcessWebSocketUrl(projectId);
      } catch (error) {
        console.warn('[WebSocket Manager] 服务发现获取FileProc WebSocket URL失败，使用默认URL:', error);
      }
      
      client = new FileProcessWebSocketClient(projectId, wsUrl || undefined);
      this.connections.set(key, client);
    }
    
    return client;
  }

  // 创建知识图谱连接
  async createGraphConnection(projectId: string): Promise<GraphWebSocketClient> {
    const key = `graph-${projectId}`;
    let client = this.connections.get(key) as GraphWebSocketClient;
    
    if (!client) {
      // 尝试通过服务发现获取WebSocket URL
      let wsUrl: string | null = null;
      try {
        const { getGraphWebSocketUrl } = await import('./serviceDiscovery');
        wsUrl = await getGraphWebSocketUrl(projectId);
      } catch (error) {
        console.warn('[WebSocket Manager] 服务发现获取Graph WebSocket URL失败，使用默认URL:', error);
      }
      
      client = new GraphWebSocketClient(projectId, wsUrl || undefined);
      this.connections.set(key, client);
    }
    
    return client;
  }

  // 创建监控连接
  async createMonitoringConnection(type: 'admin' | 'project', projectId?: string): Promise<MonitoringWebSocketClient> {
    const key = type === 'admin' ? 'monitoring-admin' : `monitoring-project-${projectId}`;
    let client = this.connections.get(key) as MonitoringWebSocketClient;
    
    if (!client) {
      // 尝试通过服务发现获取WebSocket URL
      let wsUrl: string | null = null;
      try {
        const { getMonitoringWebSocketUrl } = await import('./serviceDiscovery');
        wsUrl = await getMonitoringWebSocketUrl(type, projectId);
      } catch (error) {
        console.warn('[WebSocket Manager] 服务发现获取Monitoring WebSocket URL失败，使用默认URL:', error);
      }
      
      client = new MonitoringWebSocketClient(type, projectId, wsUrl || undefined);
      this.connections.set(key, client);
    }
    
    return client;
  }

  // 断开指定连接
  disconnect(key: string): void {
    const client = this.connections.get(key);
    if (client) {
      client.disconnect();
      this.connections.delete(key);
    }
  }

  // 断开所有连接
  disconnectAll(): void {
    this.connections.forEach((client) => {
      client.disconnect();
    });
    this.connections.clear();
  }

  // 获取连接状态
  getConnectionStatus(): Record<string, boolean> {
    const status: Record<string, boolean> = {};
    this.connections.forEach((client, key) => {
      status[key] = client.getConnectionState();
    });
    return status;
  }
}

// 全局WebSocket管理器实例
export const webSocketManager = new WebSocketManager();

// 便捷函数
export const createFileProcessWebSocket = (projectId: string) => 
  webSocketManager.createFileProcessConnection(projectId);

export const createGraphWebSocket = (projectId: string) => 
  webSocketManager.createGraphConnection(projectId);

export const createMonitoringWebSocket = (type: 'admin' | 'project', projectId?: string) => 
  webSocketManager.createMonitoringConnection(type, projectId);
