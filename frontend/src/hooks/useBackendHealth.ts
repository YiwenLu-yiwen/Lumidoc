/**
 * 后端健康检查Hook
 * 通过全局管理器监控后端服务状态，避免重复检查
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { quickBackendCheck, BackendHealthStatus } from '../api/health';
import HealthCheckManager from '../services/HealthCheckManager';

interface UseBackendHealthOptions {
  checkInterval?: number;
  autoCheck?: boolean;
  onBackendOffline?: () => void;
  onBackendOnline?: () => void;
}

export function useBackendHealth(options: UseBackendHealthOptions = {}) {
  const {
    checkInterval = Number(import.meta.env.VITE_BACKEND_HEALTH_CHECK_INTERVAL) || 300000, // 5分钟检查一次
    autoCheck = true, // 启用自动检查，但频率合理
    onBackendOffline,
    onBackendOnline
  } = options;

  const [isBackendOnline, setIsBackendOnline] = useState<boolean | null>(null);
  const [healthStatus, setHealthStatus] = useState<BackendHealthStatus | null>(null);
  const [isChecking] = useState(false);
  const [lastCheckTime, setLastCheckTime] = useState<Date | null>(null);
  // 使用useRef保证subscriberId在组件生命周期内保持不变
  const subscriberIdRef = useRef<string>(`health-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);

  // 快速检查后端状态
  const quickCheck = useCallback(async (): Promise<boolean> => {
    try {
      const isOnline = await quickBackendCheck();
      return isOnline;
    } catch (error) {
      console.error('[Backend Health] 快速检查失败:', error);
      return false;
    }
  }, []);

  // 全面健康检查 - 通过全局管理器执行
  const fullHealthCheck = useCallback(async (): Promise<BackendHealthStatus | null> => {
    const manager = HealthCheckManager.getInstance();
    return await manager.checkHealth();
  }, []);

  // 使用ref保存最新的回调函数
  const callbacksRef = useRef({ onBackendOnline, onBackendOffline });
  callbacksRef.current = { onBackendOnline, onBackendOffline };

  // 订阅全局健康检查管理器 - 只在组件挂载时执行一次
  useEffect(() => {
    const manager = HealthCheckManager.getInstance();
    const subscriberId = subscriberIdRef.current;
    
    console.log(`[Backend Health] 订阅全局健康检查管理器: ${subscriberId}`);
    
    // 订阅健康状态变化
    const unsubscribe = manager.subscribe({
      id: subscriberId,
      onHealthChange: (status) => {
        setHealthStatus(status);
        if (status) {
          setLastCheckTime(new Date());
        }
      },
      onOnlineChange: (isOnline) => {
        setIsBackendOnline(prevOnline => {
          // 状态变化时触发回调
          if (prevOnline !== null && prevOnline !== isOnline) {
            if (isOnline) {
              callbacksRef.current.onBackendOnline?.();
            } else {
              callbacksRef.current.onBackendOffline?.();
            }
          }
          return isOnline;
        });
      }
    });

    // 获取当前状态
    const currentState = manager.getCurrentStatus();
    if (currentState.status) {
      setHealthStatus(currentState.status);
    }
    if (currentState.isOnline !== null) {
      setIsBackendOnline(currentState.isOnline);
    }
    if (currentState.lastCheckTime > 0) {
      setLastCheckTime(new Date(currentState.lastCheckTime));
    }

    return () => {
      console.log(`[Backend Health] 取消订阅: ${subscriberId}`);
      unsubscribe();
    };
  }, []); // 空依赖数组，只在组件挂载时执行一次

  // 单独的effect来处理autoCheck和checkInterval的变化
  useEffect(() => {
    const manager = HealthCheckManager.getInstance();
    if (autoCheck) {
      manager.enable(checkInterval);
    } else {
      manager.disable();
    }
  }, [autoCheck, checkInterval]);

  return {
    isBackendOnline,
    healthStatus,
    isChecking,
    lastCheckTime,
    quickCheck,
    fullHealthCheck,
    refreshHealth: fullHealthCheck
  };
}
