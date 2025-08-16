/**
 * 后端状态检查包装器
 * 在应用启动时检查后端状态，如果后端未启动则显示错误页面
 */

import React, { useState, useEffect } from 'react';
import { useBackendHealth } from '../../hooks/useBackendHealth';
import { BackendOfflineError } from './BackendOfflineError';

interface BackendStatusWrapperProps {
  children: React.ReactNode;
  enableHealthCheck?: boolean;
}

export const BackendStatusWrapper: React.FC<BackendStatusWrapperProps> = ({
  children,
  enableHealthCheck = true  // 启用合理的健康检查
}) => {
  const [initialCheckCompleted, setInitialCheckCompleted] = useState(false);
  const [showOfflineError, setShowOfflineError] = useState(false);

  const { isBackendOnline, isChecking, fullHealthCheck } = useBackendHealth({
    autoCheck: enableHealthCheck,
    checkInterval: 300000, // 5分钟检查一次，合理的频率
    onBackendOffline: () => {
      if (initialCheckCompleted && enableHealthCheck) {
        console.log('[Backend Status] 后端服务离线，显示错误页面');
        setShowOfflineError(true);
      }
    },
    onBackendOnline: () => {
      if (enableHealthCheck) {
        console.log('[Backend Status] 后端服务恢复在线，隐藏错误页面');
        setShowOfflineError(false);
      }
    }
  });

  // 简化初始化检查
  useEffect(() => {
    if (!enableHealthCheck) {
      setInitialCheckCompleted(true);
      return;
    }

    console.log('[Backend Status] 启用健康检查模式');
    setInitialCheckCompleted(true);
  }, [enableHealthCheck]);

  // 后端状态变化处理
  useEffect(() => {
    if (!initialCheckCompleted || !enableHealthCheck) return;

    if (isBackendOnline === false) {
      setShowOfflineError(true);
    } else if (isBackendOnline === true && showOfflineError) {
      setShowOfflineError(false);
    }
  }, [isBackendOnline, initialCheckCompleted, enableHealthCheck, showOfflineError]);

  // 后端恢复处理
  const handleBackendReady = () => {
    console.log('[Backend Status] 后端已就绪，隐藏错误页面');
    setShowOfflineError(false);
    // 可以选择刷新页面以重新初始化所有状态
    // window.location.reload();
  };

  // 如果禁用健康检查，直接渲染子组件
  if (!enableHealthCheck) {
    return <>{children}</>;
  }

  // 初始检查未完成且正在检查中，显示加载状态
  if (!initialCheckCompleted && isChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-indigo-50">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
            <svg className="animate-spin w-8 h-8 text-blue-600" fill="none" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
              <path fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" className="opacity-75" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">正在检查后端服务</h2>
          <p className="text-gray-600">请稍候，正在连接后端服务...</p>
        </div>
      </div>
    );
  }

  // 如果后端离线，显示错误页面
  if (showOfflineError || (initialCheckCompleted && isBackendOnline === false)) {
    return (
      <BackendOfflineError 
        onBackendReady={handleBackendReady}
        showRetry={true}
      />
    );
  }

  // 后端在线或状态未知，渲染子组件
  return <>{children}</>;
};

export default BackendStatusWrapper;