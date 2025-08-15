/**
 * 后端健康检查Hook
 * 监控后端服务状态，自动处理离线情况
 */

import { useEffect, useState, useCallback } from 'react';
import { checkBackendHealth, quickBackendCheck, BackendHealthStatus } from '../api/health';

interface UseBackendHealthOptions {
  checkInterval?: number;
  autoCheck?: boolean;
  onBackendOffline?: () => void;
  onBackendOnline?: () => void;
}

export function useBackendHealth(options: UseBackendHealthOptions = {}) {
  const {
    checkInterval = Number(import.meta.env.VITE_BACKEND_HEALTH_CHECK_INTERVAL) || 60000, // 从环境变量获取检查间隔
    autoCheck = true,
    onBackendOffline,
    onBackendOnline
  } = options;

  const [isBackendOnline, setIsBackendOnline] = useState<boolean | null>(null);
  const [healthStatus, setHealthStatus] = useState<BackendHealthStatus | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [lastCheckTime, setLastCheckTime] = useState<Date | null>(null);

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

  // 全面健康检查
  const fullHealthCheck = useCallback(async (): Promise<BackendHealthStatus | null> => {
    if (isChecking) return null;
    
    setIsChecking(true);
    try {
      const status = await checkBackendHealth();
      setHealthStatus(status);
      setLastCheckTime(new Date());
      
      const isOnline = status.overall === 'healthy' || status.overall === 'degraded';
      
      // 状态变化时触发回调
      if (isBackendOnline !== null && isBackendOnline !== isOnline) {
        if (isOnline) {
          onBackendOnline?.();
        } else {
          onBackendOffline?.();
        }
      }
      
      setIsBackendOnline(isOnline);
      return status;
    } catch (error) {
      console.error('[Backend Health] 全面检查失败:', error);
      setIsBackendOnline(false);
      onBackendOffline?.();
      return null;
    } finally {
      setIsChecking(false);
    }
  }, [isChecking, isBackendOnline, onBackendOnline, onBackendOffline]);

  // 初始化检查
  useEffect(() => {
    if (autoCheck) {
      fullHealthCheck();
    }
  }, [autoCheck, fullHealthCheck]);

  // 定期检查
  useEffect(() => {
    if (!autoCheck || checkInterval <= 0) return;

    const interval = setInterval(async () => {
      // 只做快速检查，减少网络开销
      const isOnline = await quickCheck();
      
      // 如果状态发生变化，进行全面检查
      if (isBackendOnline !== null && isBackendOnline !== isOnline) {
        await fullHealthCheck();
      } else if (isBackendOnline === null) {
        // 初始状态未知时，进行全面检查
        await fullHealthCheck();
      } else {
        // 状态未变化时，只更新在线状态
        setIsBackendOnline(isOnline);
        setLastCheckTime(new Date());
      }
    }, checkInterval);

    return () => clearInterval(interval);
  }, [autoCheck, checkInterval, quickCheck, fullHealthCheck, isBackendOnline]);

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