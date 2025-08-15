/**
 * WebSocket功能演示组件
 * 展示如何使用文档处理进度、图谱更新和系统监控WebSocket
 */

import React, { useState, useEffect } from 'react';
import { 
  useFileProcessWebSocket, 
  useGraphWebSocket, 
  useMonitoringWebSocket 
} from '../../hooks/useWebSocket';

export const WebSocketDemo: React.FC = () => {
  const [currentProjectId, setCurrentProjectId] = useState('test_project');
  const [activeTab, setActiveTab] = useState<'fileproc' | 'graph' | 'monitoring'>('fileproc');

  // 文档处理WebSocket
  const {
    isConnected: fileConnected,
    lastUpdate: fileUpdate,
    error: fileError
  } = useFileProcessWebSocket(currentProjectId);

  // 知识图谱WebSocket
  const {
    isConnected: graphConnected,
    graphData,
    statistics: graphStats,
    processingStatus: graphProcessing,
    error: graphError,
    requestGraphState
  } = useGraphWebSocket(currentProjectId);

  // 系统监控WebSocket (管理员模式)
  const {
    isConnected: monitoringConnected,
    alerts,
    systemMetrics,
    serviceStatus,
    error: monitoringError,
    requestSystemMetrics,
    clearAlerts
  } = useMonitoringWebSocket('admin');

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">WebSocket实时功能演示</h1>
      
      {/* 项目选择 */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          当前项目ID:
        </label>
        <input
          type="text"
          value={currentProjectId}
          onChange={(e) => setCurrentProjectId(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          placeholder="输入项目ID"
        />
      </div>

      {/* 选项卡 */}
      <div className="mb-6">
        <nav className="flex space-x-8">
          {[
            { key: 'fileproc', label: '文档处理进度', connected: fileConnected },
            { key: 'graph', label: '知识图谱更新', connected: graphConnected },
            { key: 'monitoring', label: '系统监控', connected: monitoringConnected }
          ].map(({ key, label, connected }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key as any)}
              className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
                activeTab === key
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {label}
              <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
            </button>
          ))}
        </nav>
      </div>

      {/* 文档处理进度面板 */}
      {activeTab === 'fileproc' && (
        <div className="space-y-4">
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">文档处理进度监控</h2>
            
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-medium">连接状态:</span>
                <span className={`text-sm ${fileConnected ? 'text-green-600' : 'text-red-600'}`}>
                  {fileConnected ? '已连接' : '未连接'}
                </span>
              </div>
              
              {fileError && (
                <div className="text-sm text-red-600 mb-2">
                  错误: {fileError}
                </div>
              )}
            </div>

            {fileUpdate && (
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">最新进度更新</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium">状态:</span> {fileUpdate.status}
                  </div>
                  <div>
                    <span className="font-medium">进度:</span> {fileUpdate.progress}%
                  </div>
                  <div>
                    <span className="font-medium">阶段:</span> {fileUpdate.stage}
                  </div>
                  <div>
                    <span className="font-medium">消息:</span> {fileUpdate.message}
                  </div>
                  {fileUpdate.file_id && (
                    <div className="col-span-2">
                      <span className="font-medium">文件ID:</span> {fileUpdate.file_id}
                    </div>
                  )}
                  {fileUpdate.processing_time && (
                    <div>
                      <span className="font-medium">处理时间:</span> {fileUpdate.processing_time.toFixed(2)}秒
                    </div>
                  )}
                </div>
                {fileUpdate.error && (
                  <div className="mt-2 p-2 bg-red-100 text-red-700 rounded text-sm">
                    错误: {fileUpdate.error}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 知识图谱面板 */}
      {activeTab === 'graph' && (
        <div className="space-y-4">
          <div className="bg-white shadow rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">知识图谱实时更新</h2>
              <button
                onClick={requestGraphState}
                disabled={!graphConnected}
                className="px-4 py-2 bg-blue-600 text-white rounded disabled:bg-gray-400"
              >
                请求图谱状态
              </button>
            </div>
            
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-medium">连接状态:</span>
                <span className={`text-sm ${graphConnected ? 'text-green-600' : 'text-red-600'}`}>
                  {graphConnected ? '已连接' : '未连接'}
                </span>
              </div>
              
              {graphError && (
                <div className="text-sm text-red-600 mb-2">
                  错误: {graphError}
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* 图谱数据 */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">图谱数据</h3>
                {graphData ? (
                  <div className="text-sm">
                    <div>节点数: {graphData.nodes?.length || 0}</div>
                    <div>关系数: {graphData.relationships?.length || 0}</div>
                  </div>
                ) : (
                  <div className="text-sm text-gray-500">暂无数据</div>
                )}
              </div>

              {/* 统计信息 */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">统计信息</h3>
                {graphStats ? (
                  <div className="text-sm">
                    <pre className="whitespace-pre-wrap">{JSON.stringify(graphStats, null, 2)}</pre>
                  </div>
                ) : (
                  <div className="text-sm text-gray-500">暂无统计</div>
                )}
              </div>

              {/* 处理状态 */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">处理状态</h3>
                {graphProcessing ? (
                  <div className="text-sm">
                    <pre className="whitespace-pre-wrap">{JSON.stringify(graphProcessing, null, 2)}</pre>
                  </div>
                ) : (
                  <div className="text-sm text-gray-500">暂无状态</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 系统监控面板 */}
      {activeTab === 'monitoring' && (
        <div className="space-y-4">
          <div className="bg-white shadow rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">系统监控 (管理员)</h2>
              <div className="flex gap-2">
                <button
                  onClick={requestSystemMetrics}
                  disabled={!monitoringConnected}
                  className="px-4 py-2 bg-blue-600 text-white rounded disabled:bg-gray-400"
                >
                  刷新指标
                </button>
                <button
                  onClick={clearAlerts}
                  className="px-4 py-2 bg-red-600 text-white rounded"
                >
                  清空告警
                </button>
              </div>
            </div>
            
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-medium">连接状态:</span>
                <span className={`text-sm ${monitoringConnected ? 'text-green-600' : 'text-red-600'}`}>
                  {monitoringConnected ? '已连接' : '未连接'}
                </span>
              </div>
              
              {monitoringError && (
                <div className="text-sm text-red-600 mb-2">
                  错误: {monitoringError}
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 系统指标 */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-medium mb-3">系统指标</h3>
                {systemMetrics ? (
                  <div className="space-y-3">
                    <div>
                      <div className="text-sm font-medium">CPU使用率</div>
                      <div className="text-2xl font-bold text-blue-600">{systemMetrics.cpu.usage_percent.toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="text-sm font-medium">内存使用率</div>
                      <div className="text-2xl font-bold text-green-600">{systemMetrics.memory.usage_percent.toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="text-sm font-medium">磁盘使用率</div>
                      <div className="text-2xl font-bold text-orange-600">{systemMetrics.disk.usage_percent.toFixed(1)}%</div>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-gray-500">暂无指标数据</div>
                )}
              </div>

              {/* 告警列表 */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-medium mb-3">最新告警 ({alerts.length})</h3>
                <div className="max-h-64 overflow-y-auto space-y-2">
                  {alerts.length > 0 ? (
                    alerts.slice(0, 10).map((alert, index) => (
                      <div key={alert.id || index} className={`p-2 rounded text-sm ${
                        alert.level === 'critical' ? 'bg-red-100 text-red-800' :
                        alert.level === 'error' ? 'bg-red-50 text-red-700' :
                        alert.level === 'warning' ? 'bg-yellow-50 text-yellow-700' :
                        'bg-blue-50 text-blue-700'
                      }`}>
                        <div className="font-medium">{alert.title}</div>
                        <div className="text-xs opacity-75">{alert.message}</div>
                        <div className="text-xs opacity-50 mt-1">
                          {alert.category} | {new Date(alert.timestamp || '').toLocaleTimeString()}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-gray-500">暂无告警</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default WebSocketDemo;