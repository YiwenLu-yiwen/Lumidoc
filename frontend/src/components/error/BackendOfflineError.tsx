/**
 * 后端服务离线错误页面
 * 显示后端未启动的提示和解决方案
 */

import React, { useState } from 'react';
import { ServiceStatus, BackendHealthStatus, checkBackendHealth, waitForBackend } from '../../api/health';

interface BackendOfflineErrorProps {
  onBackendReady?: () => void;
  showRetry?: boolean;
}

export const BackendOfflineError: React.FC<BackendOfflineErrorProps> = ({
  onBackendReady,
  showRetry = true
}) => {
  const [healthStatus, setHealthStatus] = useState<BackendHealthStatus | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [isWaiting, setIsWaiting] = useState(false);
  const [lastCheckTime, setLastCheckTime] = useState<string>('');

  // 检查后端状态
  const checkStatus = async () => {
    setIsChecking(true);
    try {
      const status = await checkBackendHealth();
      setHealthStatus(status);
      setLastCheckTime(new Date().toLocaleTimeString());
      
      // 如果后端恢复，通知父组件
      if (status.overall === 'healthy' || status.overall === 'degraded') {
        onBackendReady?.();
      }
    } catch (error) {
      console.error('[Backend Error] 检查后端状态失败:', error);
    } finally {
      setIsChecking(false);
    }
  };

  // 等待后端启动
  const waitForBackendStartup = async () => {
    setIsWaiting(true);
    try {
      const success = await waitForBackend(120000, 10000); // 等待2分钟，但检查间隔改为10秒
      if (success) {
        await checkStatus();
      }
    } catch (error) {
      console.error('[Backend Error] 等待后端启动失败:', error);
    } finally {
      setIsWaiting(false);
    }
  };

  // 移除自动检查，避免与BackendStatusWrapper重复检查
  // useEffect(() => {
  //   checkStatus();
  // }, []);

  // 渲染服务状态列表
  const renderServiceStatus = (services: ServiceStatus[]) => {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {services.map((service) => (
          <div
            key={service.name}
            className={`p-3 rounded-lg border ${
              service.status === 'online'
                ? 'border-green-200 bg-green-50'
                : service.status === 'offline'
                ? 'border-red-200 bg-red-50'
                : 'border-gray-200 bg-gray-50'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-medium text-sm">{service.name}</span>
              <div className={`w-3 h-3 rounded-full ${
                service.status === 'online' ? 'bg-green-500' :
                service.status === 'offline' ? 'bg-red-500' : 'bg-gray-400'
              }`} />
            </div>
            <div className="text-xs text-gray-600 mt-1">
              {service.status === 'online' 
                ? `${service.response_time}ms` 
                : service.error || '离线'}
            </div>
            <div className="text-xs text-gray-500">{service.url}</div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 flex items-center justify-center p-4">
      <div className="max-w-4xl w-full">
        {/* 主错误信息 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-24 h-24 bg-red-100 rounded-full mb-6">
            <svg className="w-12 h-12 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-4">后端服务未启动</h1>
          <p className="text-lg text-gray-600 mb-6 max-w-2xl mx-auto">
            Lumidoc 需要启动后端服务才能正常工作。请按照下面的步骤启动后端服务。
          </p>
        </div>

        {/* 启动步骤 */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">🚀 启动后端服务</h2>
          <div className="space-y-4">
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-bold">
                1
              </div>
              <div>
                <h3 className="font-medium text-gray-900">打开终端</h3>
                <p className="text-gray-600 text-sm">在项目根目录打开终端窗口</p>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-bold">
                2
              </div>
              <div>
                <h3 className="font-medium text-gray-900">运行启动脚本</h3>
                <div className="mt-2 p-3 bg-gray-100 rounded-md">
                  <code className="text-sm font-mono text-gray-800">./start_services.sh</code>
                </div>
                <p className="text-gray-600 text-sm mt-1">这将启动所有必需的后端服务</p>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-bold">
                3
              </div>
              <div>
                <h3 className="font-medium text-gray-900">等待服务启动</h3>
                <p className="text-gray-600 text-sm">
                  服务启动需要1-2分钟，请耐心等待。启动完成后页面将自动刷新。
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* 服务状态面板 */}
        {healthStatus && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900">📊 服务状态</h2>
              <div className={`px-3 py-1 rounded-full text-sm font-medium ${
                healthStatus.overall === 'healthy' ? 'bg-green-100 text-green-800' :
                healthStatus.overall === 'degraded' ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800'
              }`}>
                {healthStatus.overall === 'healthy' ? '健康' :
                 healthStatus.overall === 'degraded' ? '部分可用' : '离线'}
              </div>
            </div>

            {/* Gateway状态 */}
            <div className="mb-4">
              <h3 className="text-lg font-medium text-gray-900 mb-2">API网关</h3>
              <div className={`p-4 rounded-lg border ${
                healthStatus.gateway.status === 'online'
                  ? 'border-green-200 bg-green-50'
                  : 'border-red-200 bg-red-50'
              }`}>
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium">{healthStatus.gateway.name}</span>
                    <div className="text-sm text-gray-600">{healthStatus.gateway.url}</div>
                  </div>
                  <div className="flex items-center space-x-2">
                    {healthStatus.gateway.response_time && (
                      <span className="text-sm text-gray-600">
                        {healthStatus.gateway.response_time}ms
                      </span>
                    )}
                    <div className={`w-4 h-4 rounded-full ${
                      healthStatus.gateway.status === 'online' ? 'bg-green-500' : 'bg-red-500'
                    }`} />
                  </div>
                </div>
                {healthStatus.gateway.error && (
                  <div className="mt-2 text-sm text-red-600">
                    错误: {healthStatus.gateway.error}
                  </div>
                )}
              </div>
            </div>

            {/* 其他服务状态 */}
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">微服务</h3>
              {renderServiceStatus(healthStatus.services)}
            </div>

            <div className="mt-4 text-xs text-gray-500">
              最后检查时间: {lastCheckTime}
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        {showRetry && (
          <div className="text-center space-y-4">
            <div className="flex justify-center space-x-4">
              <button
                onClick={checkStatus}
                disabled={isChecking}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
              >
                {isChecking ? (
                  <>
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
                      <path fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" className="opacity-75" />
                    </svg>
                    <span>检查中...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    <span>重新检查</span>
                  </>
                )}
              </button>

              <button
                onClick={waitForBackendStartup}
                disabled={isWaiting}
                className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
              >
                {isWaiting ? (
                  <>
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
                      <path fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" className="opacity-75" />
                    </svg>
                    <span>等待启动中...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>等待后端启动</span>
                  </>
                )}
              </button>
            </div>

            <div className="text-sm text-gray-600">
              <p>💡 提示: 如果服务启动时间较长，可以点击"等待后端启动"按钮，系统会自动检测并在服务就绪后跳转。</p>
            </div>
          </div>
        )}

        {/* 故障排除 */}
        <div className="mt-8 bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-yellow-800 mb-3">🔧 故障排除</h3>
          <div className="space-y-3 text-yellow-700">
            <div>
              <strong>如果启动脚本无法执行：</strong>
              <br />
              <code className="bg-yellow-100 px-2 py-1 rounded text-sm">chmod +x start_services.sh</code>
            </div>
            
            <div>
              <strong>如果端口被占用：</strong>
              <br />
              运行停止脚本后重新启动：<code className="bg-yellow-100 px-2 py-1 rounded text-sm">./stop_services.sh && ./start_services.sh</code>
            </div>
            
            <div>
              <strong>如果需要查看服务状态：</strong>
              <br />
              运行诊断脚本：<code className="bg-yellow-100 px-2 py-1 rounded text-sm">python scripts/diagnose_services.py</code>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BackendOfflineError;
