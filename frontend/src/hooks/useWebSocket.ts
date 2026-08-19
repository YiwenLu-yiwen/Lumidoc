/**
 * WebSocket React Hooks
 * 简化WebSocket在React组件中的使用
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import {
  FileProcessWebSocketClient,
  GraphWebSocketClient,
  MonitoringWebSocketClient,
  webSocketManager,
  ProgressUpdate,
  GraphUpdate,
  ProcessingStatus,
  ServiceStatus,
  SystemAlert,
  SystemMetrics
} from '../api/websocket';
import type { GraphStatistics } from '../types/graph';

type GraphSnapshot = NonNullable<GraphUpdate['graph']>;

// 文档处理进度Hook
export function useFileProcessWebSocket(projectId: string | null) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<ProgressUpdate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const clientRef = useRef<FileProcessWebSocketClient | null>(null);

  const connect = useCallback(async () => {
    if (!projectId) return;

    try {
      setError(null);
      const client = await webSocketManager.createFileProcessConnection(projectId);
      clientRef.current = client;

      // 设置事件监听
      client.onProgressUpdate((data) => {
        setLastUpdate({ ...data, type: 'progress' });
      });

      client.onTaskCompleted((data) => {
        setLastUpdate({ ...data, type: 'completed' });
      });

      client.onTaskError((data) => {
        setLastUpdate({ ...data, type: 'error' });
      });

      await client.connect();
      setIsConnected(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '连接失败');
      setIsConnected(false);
    }
  }, [projectId]);

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
      clientRef.current = null;
    }
    setIsConnected(false);
    setLastUpdate(null);
  }, []);

  useEffect(() => {
    if (projectId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [projectId, connect, disconnect]);

  return {
    isConnected,
    lastUpdate,
    error,
    connect,
    disconnect
  };
}

// 知识图谱WebSocket Hook
export function useGraphWebSocket(projectId: string | null) {
  const [isConnected, setIsConnected] = useState(false);
  const [graphData, setGraphData] = useState<GraphSnapshot | null>(null);
  const [statistics, setStatistics] = useState<GraphStatistics | null>(null);
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const clientRef = useRef<GraphWebSocketClient | null>(null);

  const connect = useCallback(async () => {
    if (!projectId) return;

    try {
      setError(null);
      const client = await webSocketManager.createGraphConnection(projectId);
      clientRef.current = client;

      // 设置事件监听
      client.onGraphUpdate((data: GraphUpdate) => {
        if (data.update_type === 'full') {
          if (data.graph) {
            setGraphData(data.graph);
          }
        } else {
          setGraphData((prev) => {
            if (!prev) return { nodes: [], relationships: [] };

            if (data.update_type === 'add_node' && data.node) {
              const node = data.node;
              const hasNode = prev.nodes.some((existingNode) => existingNode.id === node.id);
              const nodes = hasNode
                ? prev.nodes.map((existingNode) => existingNode.id === node.id ? node : existingNode)
                : [...prev.nodes, node];
              return { ...prev, nodes };
            } else if (data.update_type === 'add_relationship' && data.relationship) {
              const relationship = data.relationship;
              const matchesRelationship = (existingRelationship: typeof relationship) =>
                existingRelationship.source === relationship.source &&
                existingRelationship.target === relationship.target &&
                existingRelationship.type === relationship.type;
              const hasRelationship = prev.relationships.some(matchesRelationship);
              const relationships = hasRelationship
                ? prev.relationships.map((existingRelationship) =>
                  matchesRelationship(existingRelationship) ? relationship : existingRelationship
                )
                : [...prev.relationships, relationship];
              return {
                ...prev,
                relationships
              };
            }

            return prev;
          });
        }
      });

      client.onGraphStatistics((data) => {
        setStatistics(data);
      });

      client.onProcessingStatus((data) => {
        setProcessingStatus(data);
      });

      client.onGraphStateSync((data) => {
        setGraphData(data);
      });

      await client.connect();
      setIsConnected(true);

      // 连接成功后请求当前图谱状态
      client.requestGraphState();
    } catch (err) {
      setError(err instanceof Error ? err.message : '连接失败');
      setIsConnected(false);
    }
  }, [projectId]);

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
      clientRef.current = null;
    }
    setIsConnected(false);
    setGraphData(null);
    setStatistics(null);
    setProcessingStatus(null);
  }, []);

  const requestGraphState = useCallback(() => {
    if (clientRef.current && isConnected) {
      clientRef.current.requestGraphState();
    }
  }, [isConnected]);

  useEffect(() => {
    if (projectId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [projectId, connect, disconnect]);

  return {
    isConnected,
    graphData,
    statistics,
    processingStatus,
    error,
    connect,
    disconnect,
    requestGraphState
  };
}

// 系统监控WebSocket Hook
export function useMonitoringWebSocket(type: 'admin' | 'project', projectId?: string) {
  const [isConnected, setIsConnected] = useState(false);
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null);
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const clientRef = useRef<MonitoringWebSocketClient | null>(null);

  const connect = useCallback(async () => {
    try {
      setError(null);
      const client = await webSocketManager.createMonitoringConnection(type, projectId);
      clientRef.current = client;

      // 设置事件监听
      client.onAlert((alert: SystemAlert) => {
        setAlerts(prev => [alert, ...prev].slice(0, 100)); // 保持最新100条告警
      });

      if (type === 'admin') {
        client.onSystemMetrics((metrics: SystemMetrics) => {
          setSystemMetrics(metrics);
        });

        client.onServiceStatus((status) => {
          setServiceStatus(status);
        });

        client.onAlertHistory((history: SystemAlert[]) => {
          setAlerts(prev => [...history, ...prev].slice(0, 100));
        });
      }

      await client.connect();
      setIsConnected(true);

      // 如果是管理员连接，请求当前数据
      if (type === 'admin') {
        client.requestSystemMetrics();
        client.requestAlertHistory(10);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '连接失败');
      setIsConnected(false);
    }
  }, [type, projectId]);

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
      clientRef.current = null;
    }
    setIsConnected(false);
    setAlerts([]);
    setSystemMetrics(null);
    setServiceStatus(null);
  }, []);

  const requestSystemMetrics = useCallback(() => {
    if (clientRef.current && isConnected && type === 'admin') {
      clientRef.current.requestSystemMetrics();
    }
  }, [isConnected, type]);

  const requestAlertHistory = useCallback((count: number = 10) => {
    if (clientRef.current && isConnected && type === 'admin') {
      clientRef.current.requestAlertHistory(count);
    }
  }, [isConnected, type]);

  const clearAlerts = useCallback(() => {
    setAlerts([]);
  }, []);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    alerts,
    systemMetrics,
    serviceStatus,
    error,
    connect,
    disconnect,
    requestSystemMetrics,
    requestAlertHistory,
    clearAlerts
  };
}

// WebSocket连接状态Hook
export function useWebSocketStatus() {
  const [connectionStatus, setConnectionStatus] = useState<Record<string, boolean>>({});

  const updateStatus = useCallback(() => {
    const status = webSocketManager.getConnectionStatus();
    setConnectionStatus(status);
  }, []);

  useEffect(() => {
    // 定期更新连接状态
    const interval = setInterval(updateStatus, 5000);
    updateStatus(); // 立即更新一次

    return () => {
      clearInterval(interval);
    };
  }, [updateStatus]);

  const disconnectAll = useCallback(() => {
    webSocketManager.disconnectAll();
    setConnectionStatus({});
  }, []);

  return {
    connectionStatus,
    updateStatus,
    disconnectAll
  };
}
