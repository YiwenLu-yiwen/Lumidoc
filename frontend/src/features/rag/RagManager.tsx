import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ragApi, RagFileStatusResponse } from '../../api/rag';
import { fileApi } from '../../api/file';

export interface RagManagerProps {
  onQueryComplete?: (result: string) => void;
}

// 添加文件状态颜色和文本映射
const STATUS_COLORS: { [key: string]: string } = {
  pending: 'text-yellow-400',
  processing: 'text-blue-400', 
  processed: 'text-green-400',
  completed: 'text-green-400',
  failed: 'text-red-400',
  error: 'text-red-400'
};

const STATUS_TEXT: { [key: string]: string } = {
  pending: '等待处理',
  processing: '处理中',
  processed: '已处理', 
  completed: '已完成',
  failed: '处理失败',
  error: '处理失败'
};

export default function RagManager({ onQueryComplete }: RagManagerProps) {
  const { projectId = '' } = useParams<{ projectId: string }>();
  
  const [fileList, setFileList] = useState<string[]>([]);
  const [ragFileList, setRagFileList] = useState<string[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [isImporting, setIsImporting] = useState(false);
  const [queryText, setQueryText] = useState('');
  const [queryResult, setQueryResult] = useState('');
  const [isQuerying, setIsQuerying] = useState(false);
  
  // 添加文件状态状态
  const [fileStatuses, setFileStatuses] = useState<RagFileStatusResponse['statuses']>({});
  const [isLoadingStatuses, setIsLoadingStatuses] = useState(false);

  useEffect(() => {
    fetchFileList();
    fetchRagFileList();
    fetchFileStatuses();
  }, [projectId]);

  // 文件列表获取
  const fetchFileList = async () => {
    try {
      const files = await fileApi.listFiles(projectId);
      setFileList(files.map(f => f.filename));
    } catch (err) {
      console.error('Failed to fetch file list:', err);
      toast.error('获取文件列表失败');
    }
  };

  // RAG文件列表获取
  const fetchRagFileList = async () => {
    try {
      const response = await ragApi.getRagFiles(projectId);
      setRagFileList(response.files || []);
    } catch (err) {
      console.error('Failed to fetch RAG file list:', err);
      toast.error('获取知识库文件列表失败');
    }
  };
  
  // 文件状态获取
  const fetchFileStatuses = async () => {
    try {
      setIsLoadingStatuses(true);
      const response = await ragApi.getRagFileStatus(projectId);
      if (response.success) {
        setFileStatuses(response.statuses);
      } else {
        console.warn('Failed to fetch file statuses:', response.error);
      }
    } catch (err) {
      console.error('Failed to fetch file statuses:', err);
    } finally {
      setIsLoadingStatuses(false);
    }
  };

  // 智能轮询进度和状态（优化间隔）
  const startPolling = () => {
    let consecutiveNoChanges = 0;
    let pollingInterval = 3000; // 起始间隔：3秒，更快响应
    let pollTimeoutId: NodeJS.Timeout | null = null;
    
    const poll = async () => {
      try {
        const previousStatuses = { ...fileStatuses };
        console.log('[RagManager] 开始轮询检查状态...');
        
        // 同时获取状态和文件列表，避免竞态条件
        const [statusResult, fileListResult] = await Promise.all([
          (async () => {
            try {
              const response = await ragApi.getRagFileStatus(projectId);
              if (response.success) {
                setFileStatuses(response.statuses);
                return response.statuses;
              }
              return {};
            } catch (err) {
              console.error('[RagManager] 获取状态失败:', err);
              return {};
            }
          })(),
          (async () => {
            try {
              await fetchRagFileList();
              return true;
            } catch (err) {
              console.error('[RagManager] 刷新文件列表失败:', err);
              return false;
            }
          })()
        ]);
        
        // 使用最新获取的状态进行比较
        const currentStatuses = statusResult;
        const hasChanges = JSON.stringify(previousStatuses) !== JSON.stringify(currentStatuses);
        
        console.log('[RagManager] 轮询结果:', {
          hasChanges,
          statusCount: Object.keys(currentStatuses).length,
          fileListRefreshed: fileListResult
        });
        
        if (hasChanges) {
          consecutiveNoChanges = 0;
          pollingInterval = Math.max(pollingInterval / 1.2, 2000); // 有变化时减少间隔，最少2秒
          console.log(`[RagManager] 检测到状态变化，间隔调整为${pollingInterval}ms`);
        } else {
          consecutiveNoChanges++;
          pollingInterval = Math.min(pollingInterval * 1.3, 30000); // 无变化时增加间隔，最多30秒
        }
        
        // 检查是否所有文件都已完成处理（处理成功或失败）
        const allFinished = Object.values(currentStatuses).every(
          status => status.status === 'processed' || status.status === 'failed'
        );
        
        if (allFinished && Object.keys(currentStatuses).length > 0) {
          console.log('[RagManager] 所有文件处理完成，停止轮询');
          setIsImporting(false);
          
          // 计算成功和失败数量
          const succeeded = Object.values(currentStatuses).filter(s => s.status === 'processed').length;
          const failed = Object.values(currentStatuses).filter(s => s.status === 'failed').length;
          
          if (failed === 0) {
            toast.success(`知识库构建完成，${succeeded}个文件处理成功`);
          } else {
            toast.warning(`知识库构建部分完成，${succeeded}个成功，${failed}个失败`);
          }
          
          // 最终刷新所有数据
          await Promise.all([
            fetchFileList(),
            fetchRagFileList(),
            fetchFileStatuses()
          ]);
          console.log('[RagManager] 最终数据刷新完成');
          return; // 结束轮询
        }
        
        // 继续轮询，使用动态间隔
        pollTimeoutId = setTimeout(poll, pollingInterval);
        
      } catch (err) {
        console.error('Failed during polling:', err);
        pollingInterval = Math.min(pollingInterval * 2, 30000); // 出错时增加间隔
        pollTimeoutId = setTimeout(poll, pollingInterval);
      }
    };
    
    // 开始首次轮询
    poll();
    
    // 返回清理函数
    return () => {
      if (pollTimeoutId) {
        clearTimeout(pollTimeoutId);
      }
    };
  };

  // 选择/取消选择文件
  const handleSelect = (file: string) => {
    setSelectedFiles(prev => 
      prev.includes(file) 
        ? prev.filter(f => f !== file) 
        : [...prev, file]
    );
  };

  // 获取可选择的文件（排除已在知识库中的文件）
  const getSelectableFiles = () => {
    return fileList.filter(fileName => {
      // 检查是否已在RAG文件列表中（按文件名匹配）
      const isInRag = ragFileList.some(ragFile => {
        if (typeof ragFile === 'string') {
          return ragFile === fileName;
        }
        // 如果是对象格式，检查多个可能的文件名字段
        const fileObj = ragFile as any;
        return fileObj.filename === fileName || 
               fileObj.name === fileName || 
               fileObj.originalName === fileName ||
               fileObj.displayName === fileName;
      });
      
      // 检查文件状态中是否已完成RAG处理
      const fileStatus = Object.values(fileStatuses).find(status => 
        status.file_name === fileName
      );
      const isProcessedInRag = fileStatus?.status === 'processed';
      
      return !isInRag && !isProcessedInRag;
    });
  };

  // 全选/取消全选
  const handleSelectAll = () => {
    const selectableFiles = getSelectableFiles();
    setSelectedFiles(
      selectedFiles.length === selectableFiles.length ? [] : selectableFiles
    );
  };

  // 导入知识库
  const handleImport = async () => {
    if (!selectedFiles.length) {
      toast.error('请选择要导入知识库的文件');
      return;
    }
    
    try {
      setIsImporting(true);
      // setImportProgress(0);
      
      const result = await ragApi.buildRag(projectId, selectedFiles);
      
      if (result.success) {
        toast.success('开始构建知识库');
        
        // 立即更新选中文件的状态为"处理中"
        const newStatuses = { ...fileStatuses };
        selectedFiles.forEach(file => {
          newStatuses[file] = { 
            status: 'processing', 
            file_name: file,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          };
        });
        setFileStatuses(newStatuses);
        
        // 立即强制刷新所有数据
        try {
          await Promise.all([
            fetchFileList(),
            fetchRagFileList(),
            fetchFileStatuses()
          ]);
          console.log('[RagManager] 导入启动后立即刷新完成');
        } catch (refreshErr) {
          console.error('[RagManager] 导入后刷新失败:', refreshErr);
        }
        
        // 然后开始轮询监控
        const cleanupPolling = startPolling();
        
        // 5分钟后自动停止轮询
        setTimeout(() => {
          if (cleanupPolling) {
            cleanupPolling();
          }
          setIsImporting(false);
        }, 5 * 60 * 1000);
        
        setSelectedFiles([]);
      } else {
        toast.error(`知识库构建失败: ${result.message}`);
        setIsImporting(false);
      }
    } catch (err: any) {
      console.error('Import error:', err);
      toast.error(err.response?.data?.detail || '知识库导入失败');
      setIsImporting(false);
    }
  };

  // 查询知识库
  const handleQuery = async () => {
    if (!queryText.trim()) {
      toast.error('请输入查询内容');
      return;
    }
    
    try {
      setIsQuerying(true);
      const result = await ragApi.queryRag(projectId, queryText);
      setQueryResult(result.result);
      if (onQueryComplete) {
        onQueryComplete(result.result);
      }
    } catch (err: any) {
      console.error('Query error:', err);
      toast.error(err.response?.data?.detail || '查询失败');
    } finally {
      setIsQuerying(false);
    }
  };
  
  // 删除RAG文件
  const handleDeleteRagFile = async (fileId: string, fileName: string) => {
    if (!confirm(`确定要从知识库中删除文件 "${fileName}" 吗？`)) {
      return;
    }

    try {
      console.log(`删除RAG文件: ${fileId} (${fileName})`);
      const result = await ragApi.deleteRagFile(projectId, fileId);
      
      if (result.success) {
        toast.success(`文件 "${fileName}" 已从知识库中删除`);
        
        // 刷新所有相关数据
        await fetchFileList();
        await fetchRagFileList();
        await fetchFileStatuses();
      } else {
        toast.error(`删除失败: ${result.message}`);
      }
    } catch (err: any) {
      console.error('删除RAG文件失败:', err);
      toast.error(`删除失败: ${err.message || '未知错误'}`);
    }
  };

  // 手动刷新状态
  const refreshStatus = () => {
    fetchFileList();
    fetchRagFileList();
    fetchFileStatuses();
  };

  return (
    <div className="text-white">
      <h2 className="text-xl font-bold mb-4">
        知识库管理
        <button 
          onClick={refreshStatus} 
          className="ml-2 text-sm px-2 py-1 bg-gray-700 rounded hover:bg-gray-600"
          title="刷新状态"
        >
          刷新
        </button>
      </h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 左侧：文件选择和导入 */}
        <div>
          <h3 className="text-lg font-semibold mb-2">导入文件到知识库</h3>
          
          <div className="mb-4">
            <div className="flex items-center mb-2">
              <input
                type="checkbox"
                checked={getSelectableFiles().length === selectedFiles.length && selectedFiles.length > 0}
                onChange={handleSelectAll}
                className="mr-2"
              />
              <span>全选</span>
              <button
                className="ml-auto px-3 py-1 bg-blue-600 rounded text-white disabled:bg-gray-500 disabled:opacity-50"
                disabled={selectedFiles.length === 0 || isImporting}
                onClick={handleImport}
              >
                {isImporting ? `导入中...` : '导入所选文件'}
              </button>
            </div>
            
            <div className="max-h-64 overflow-y-auto border border-gray-700 rounded p-2">
              {fileList.length === 0 ? (
                <p className="text-gray-400">没有可用文件</p>
              ) : (
                fileList.map(file => {
                  // 检查文件是否已在知识库中或正在处理
                  const isInRag = ragFileList.some(ragFile => {
                    if (typeof ragFile === 'string') {
                      return ragFile === file;
                    }
                    const fileObj = ragFile as any;
                    return fileObj.filename === file || 
                           fileObj.name === file || 
                           fileObj.originalName === file ||
                           fileObj.displayName === file;
                  });
                  
                  const fileStatus = Object.values(fileStatuses).find(status => 
                    status.file_name === file
                  );
                  const isProcessedInRag = fileStatus?.status === 'processed';
                  const isProcessingRag = fileStatus?.status === 'processing';
                  
                  const disabled = isInRag || isProcessedInRag;
                  let statusText = '';
                  if (isProcessedInRag) statusText = ' (已加入知识库)';
                  else if (isProcessingRag) statusText = ' (处理中)';
                  else if (isInRag) statusText = ' (已加入知识库)';
                  
                  return (
                    <div 
                      key={file}
                      className={`
                        flex items-center p-1
                        ${disabled ? 'text-green-400' : ''}
                        ${isProcessingRag ? 'text-blue-400' : ''}
                      `}
                    >
                      <input
                        type="checkbox"
                        checked={selectedFiles.includes(file)}
                        onChange={() => handleSelect(file)}
                        disabled={disabled}
                        className="mr-2"
                      />
                      <span className="truncate" title={file}>
                        {file}{statusText}
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
        
        {/* 右侧：知识库查询 */}
        <div>
          <h3 className="text-lg font-semibold mb-2">知识库查询</h3>
          
          <div className="mb-4">
            <div className="flex mb-2">
              <input
                type="text"
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                placeholder="输入查询内容"
                className="flex-1 p-2 bg-[#232325] border border-gray-700 rounded mr-2 text-white"
              />
              <button
                onClick={handleQuery}
                disabled={!queryText.trim() || isQuerying}
                className="px-3 py-1 bg-blue-600 rounded text-white disabled:bg-gray-500 disabled:opacity-50"
              >
                {isQuerying ? '查询中...' : '查询'}
              </button>
            </div>
            
            {queryResult && (
              <div className="p-3 bg-[#232325] border border-gray-700 rounded max-h-64 overflow-y-auto">
                <h4 className="font-semibold mb-1">查询结果:</h4>
                <p className="whitespace-pre-wrap">{queryResult}</p>
              </div>
            )}
          </div>
          
          <div>
            <h4 className="font-semibold mb-1">
              知识库文件状态:
              {isLoadingStatuses && <span className="ml-2 text-xs text-gray-400">(加载中...)</span>}
            </h4>
            <div className="max-h-48 overflow-y-auto border border-gray-700 rounded p-2">
              {Object.keys(fileStatuses).length === 0 ? (
                <p className="text-gray-400">知识库中没有文件</p>
              ) : (
                Object.entries(fileStatuses).map(([fileId, status]) => (
                  <div key={fileId} className={`p-1 ${STATUS_COLORS[status.status] || STATUS_COLORS[status.status?.toLowerCase()] || 'text-gray-400'}`}>
                    <div className="flex justify-between items-center">
                      <span className="truncate flex-1" title={status.file_name || fileId}>
                        {status.file_name || fileId}
                      </span>
                      <div className="flex items-center ml-2 text-xs whitespace-nowrap">
                        <span>
                          {STATUS_TEXT[status.status] || STATUS_TEXT[status.status?.toLowerCase()] || '未知状态'}
                          {(['failed', 'error'].includes(status.status)) && status.error && (
                            <span className="ml-1" title={status.error}>❌</span>
                          )}
                        </span>
                        {status.status === 'processed' && (
                          <button
                            onClick={() => handleDeleteRagFile(fileId, status.file_name || fileId)}
                            className="ml-2 px-1 py-0.5 bg-red-600 hover:bg-red-700 rounded text-xs"
                            title="从知识库中删除"
                          >
                            删除
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 