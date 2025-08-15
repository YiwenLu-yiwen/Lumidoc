/**
 * WebSocket连接监控组件
 * 用于开发调试，显示所有WebSocket连接状态
 */

import React, { useState } from 'react';
import { useWebSocketStatus } from '../../hooks/useWebSocket';

interface WebSocketMonitorProps {
  className?: string;
}

export const WebSocketMonitor: React.FC<WebSocketMonitorProps> = ({ className }) => {
  const { connectionStatus, updateStatus, disconnectAll } = useWebSocketStatus();
  const [isExpanded, setIsExpanded] = useState(false);

  if (!isExpanded) {
    return (
      <div className={`fixed bottom-4 right-4 z-50 ${className}`}>
        <button
          onClick={() => setIsExpanded(true)}
          className="bg-blue-600 hover:bg-blue-700 text-white p-2 rounded-full shadow-lg transition-colors"
          title="打开WebSocket监控"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </button>
      </div>
    );
  }

  const totalConnections = Object.keys(connectionStatus).length;
  const activeConnections = Object.values(connectionStatus).filter(Boolean).length;

  return (
    <div className={`fixed bottom-4 right-4 z-50 bg-white shadow-xl rounded-lg border p-4 w-80 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-900">WebSocket监控</h3>
        <button
          onClick={() => setIsExpanded(false)}
          className="text-gray-400 hover:text-gray-600 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="mb-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">连接状态</span>
          <span className={`font-medium ${activeConnections > 0 ? 'text-green-600' : 'text-gray-500'}`}>
            {activeConnections}/{totalConnections} 活跃
          </span>
        </div>
      </div>

      <div className="space-y-2 mb-4 max-h-48 overflow-y-auto">
        {Object.entries(connectionStatus).length === 0 ? (
          <div className="text-gray-500 text-sm text-center py-2">
            没有WebSocket连接
          </div>
        ) : (
          Object.entries(connectionStatus).map(([key, isConnected]) => {
            const [type, ...rest] = key.split('-');
            const displayName = getDisplayName(type, rest.join('-'));
            
            return (
              <div key={key} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-900">
                    {displayName}
                  </div>
                  <div className="text-xs text-gray-500">
                    {key}
                  </div>
                </div>
                <div className={`w-3 h-3 rounded-full ${
                  isConnected ? 'bg-green-500' : 'bg-red-500'
                }`} title={isConnected ? '已连接' : '未连接'} />
              </div>
            );
          })
        )}
      </div>

      <div className="flex gap-2">
        <button
          onClick={updateStatus}
          className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm py-2 px-3 rounded transition-colors"
        >
          刷新状态
        </button>
        <button
          onClick={disconnectAll}
          className="flex-1 bg-red-600 hover:bg-red-700 text-white text-sm py-2 px-3 rounded transition-colors"
        >
          断开所有
        </button>
      </div>

      <div className="mt-3 text-xs text-gray-500">
        <div>• 绿点：已连接</div>
        <div>• 红点：未连接</div>
      </div>
    </div>
  );
};

function getDisplayName(type: string, identifier: string): string {
  switch (type) {
    case 'fileproc':
      return `文档处理 (${identifier})`;
    case 'graph':
      return `知识图谱 (${identifier})`;
    case 'monitoring':
      return identifier === 'admin' ? '系统监控 (管理员)' : `项目监控 (${identifier.replace('project-', '')})`;
    default:
      return `${type} (${identifier})`;
  }
}

export default WebSocketMonitor;