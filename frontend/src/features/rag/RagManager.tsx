import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { isAxiosError } from 'axios';
import { ragApi, RagFile, RagFileStatusResponse } from '../../api/rag';
import { fileApi } from '../../api/file';
import { useTheme } from '@/context/ThemeContext';
import { Database } from 'lucide-react';
import { useProjects } from '@/context/ProjectContext';
import { useLanguage } from '@/context/LanguageContext';
import { resolveRagProjectId } from './ragProject';

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

const STATUS_TEXT: { [key: string]: { 'zh-CN': string; 'en-US': string } } = {
  pending: { 'zh-CN': '等待处理', 'en-US': 'Pending' },
  processing: { 'zh-CN': '处理中', 'en-US': 'Processing' },
  processed: { 'zh-CN': '已处理', 'en-US': 'Processed' }, 
  completed: { 'zh-CN': '已完成', 'en-US': 'Completed' },
  failed: { 'zh-CN': '处理失败', 'en-US': 'Failed' },
  error: { 'zh-CN': '处理失败', 'en-US': 'Error' }
};

const ragFileMatches = (ragFile: RagFile, fileName: string): boolean => {
  if (typeof ragFile === 'string') {
    return ragFile === fileName;
  }
  return ragFile.filename === fileName ||
    ragFile.name === fileName ||
    ragFile.originalName === fileName ||
    ragFile.displayName === fileName;
};

const getApiErrorDetail = (error: unknown): string | undefined => {
  if (isAxiosError<{ detail?: string }>(error)) {
    return error.response?.data?.detail;
  }
  return undefined;
};

export default function RagManager({ onQueryComplete }: RagManagerProps) {
  const navigate = useNavigate();
  const { projectId: routeProjectId } = useParams<{ projectId: string }>();
  const { projects, loading: projectsLoading } = useProjects();
  const projectId = resolveRagProjectId(routeProjectId, projects[0]?.id);
  
  // 主题模式和语言检测
  const { isDarkMode } = useTheme();
  const { currentLanguage, t } = useLanguage();
  
  const getStatusText = (status: string) => {
    const statusConfig = STATUS_TEXT[status] || STATUS_TEXT[status?.toLowerCase()];
    return statusConfig ? statusConfig[currentLanguage as keyof typeof statusConfig] || statusConfig['zh-CN'] : (currentLanguage === 'zh-CN' ? '未知状态' : 'Unknown Status');
  };
  
  const [fileList, setFileList] = useState<string[]>([]);
  const [ragFileList, setRagFileList] = useState<RagFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [isImporting, setIsImporting] = useState(false);
  const [queryText, setQueryText] = useState('');
  const [queryResult, setQueryResult] = useState('');
  const [isQuerying, setIsQuerying] = useState(false);
  
  // 添加文件状态状态
  const [fileStatuses, setFileStatuses] = useState<RagFileStatusResponse['statuses']>({});
  const [isLoadingStatuses, setIsLoadingStatuses] = useState(false);

  // 文件列表获取
  const fetchFileList = useCallback(async () => {
    if (!projectId) return;
    try {
      const files = await fileApi.listFiles(projectId);
      setFileList(files.map(f => f.filename));
    } catch (err) {
      console.error('Failed to fetch file list:', err);
      toast.error(currentLanguage === 'zh-CN' ? '获取文件列表失败' : 'Failed to fetch file list');
    }
  }, [currentLanguage, projectId]);

  // RAG文件列表获取
  const fetchRagFileList = useCallback(async () => {
    if (!projectId) return;
    try {
      const response = await ragApi.getRagFiles(projectId);
      setRagFileList(response.files || []);
    } catch (err) {
      console.error('Failed to fetch RAG file list:', err);
      toast.error(currentLanguage === 'zh-CN' ? '获取知识库文件列表失败' : 'Failed to fetch knowledge base file list');
    }
  }, [currentLanguage, projectId]);
  
  // 文件状态获取
  const fetchFileStatuses = useCallback(async () => {
    if (!projectId) return;
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
  }, [projectId]);

  useEffect(() => {
    if (!projectId) {
      setFileList([]);
      setRagFileList([]);
      setFileStatuses({});
      return;
    }
    void fetchFileList();
    void fetchRagFileList();
    void fetchFileStatuses();
  }, [fetchFileList, fetchFileStatuses, fetchRagFileList, projectId]);

  // 智能轮询进度和状态（优化间隔）
  const startPolling = () => {
    if (!projectId) return () => undefined;
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
          pollingInterval = Math.max(pollingInterval / 1.2, 2000); // 有变化时减少间隔，最少2秒
          console.log(`[RagManager] 检测到状态变化，间隔调整为${pollingInterval}ms`);
        } else {
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
            toast.success(currentLanguage === 'zh-CN' 
              ? `知识库构建完成，${succeeded}个文件处理成功`
              : `Knowledge base built successfully, ${succeeded} files processed`
            );
          } else {
            toast.warning(currentLanguage === 'zh-CN' 
              ? `知识库构建部分完成，${succeeded}个成功，${failed}个失败`
              : `Knowledge base partially built, ${succeeded} successful, ${failed} failed`
            );
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
      const isInRag = ragFileList.some(ragFile => ragFileMatches(ragFile, fileName));
      
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
    if (!projectId) return;
    if (!selectedFiles.length) {
      toast.error(currentLanguage === 'zh-CN' ? '请选择要导入知识库的文件' : 'Please select files to import to knowledge base');
      return;
    }
    
    try {
      setIsImporting(true);
      // setImportProgress(0);
      
      const result = await ragApi.buildRag(projectId, selectedFiles);
      
      if (result.success) {
        toast.success(currentLanguage === 'zh-CN' ? '开始构建知识库' : 'Starting to build knowledge base');
        
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
        toast.error(currentLanguage === 'zh-CN' 
          ? `知识库构建失败: ${result.message}`
          : `Knowledge base build failed: ${result.message}`
        );
        setIsImporting(false);
      }
    } catch (err: unknown) {
      console.error('Import error:', err);
      toast.error(getApiErrorDetail(err) || (currentLanguage === 'zh-CN' ? '知识库导入失败' : 'Knowledge base import failed'));
      setIsImporting(false);
    }
  };

  // 查询知识库
  const handleQuery = async () => {
    if (!projectId) return;
    if (!queryText.trim()) {
      toast.error(currentLanguage === 'zh-CN' ? '请输入查询内容' : 'Please enter query content');
      return;
    }
    
    try {
      setIsQuerying(true);
      const result = await ragApi.queryRag(projectId, queryText);
      setQueryResult(result.result);
      if (onQueryComplete) {
        onQueryComplete(result.result);
      }
    } catch (err: unknown) {
      console.error('Query error:', err);
      toast.error(getApiErrorDetail(err) || (currentLanguage === 'zh-CN' ? '查询失败' : 'Query failed'));
    } finally {
      setIsQuerying(false);
    }
  };
  
  // 删除RAG文件
  const handleDeleteRagFile = async (fileId: string, fileName: string) => {
    if (!projectId) return;
    const confirmMessage = currentLanguage === 'zh-CN' 
      ? `确定要从知识库中删除文件 "${fileName}" 吗？`
      : `Are you sure you want to delete file "${fileName}" from knowledge base?`;
    
    if (!confirm(confirmMessage)) {
      return;
    }

    try {
      console.log(`删除RAG文件: ${fileId} (${fileName})`);
      const result = await ragApi.deleteRagFile(projectId, fileId);
      
      if (result.success) {
        toast.success(currentLanguage === 'zh-CN' 
          ? `文件 "${fileName}" 已从知识库中删除`
          : `File "${fileName}" has been deleted from knowledge base`
        );
        
        // 刷新所有相关数据
        await fetchFileList();
        await fetchRagFileList();
        await fetchFileStatuses();
      } else {
        toast.error(currentLanguage === 'zh-CN' 
          ? `删除失败: ${result.message}`
          : `Delete failed: ${result.message}`
        );
      }
    } catch (err: unknown) {
      console.error('删除RAG文件失败:', err);
      const errorMessage = err instanceof Error ? err.message : (currentLanguage === 'zh-CN' ? '未知错误' : 'Unknown error');
      toast.error(currentLanguage === 'zh-CN' 
        ? `删除失败: ${errorMessage}`
        : `Delete failed: ${errorMessage}`
      );
    }
  };

  // 手动刷新状态
  const refreshStatus = () => {
    if (!projectId) return;
    fetchFileList();
    fetchRagFileList();
    fetchFileStatuses();
  };

  if (!projectId) {
    return (
      <div className="flex h-full items-center justify-center overflow-y-auto bg-background p-6 text-foreground">
        <div className="w-full max-w-lg rounded-xl border bg-card p-8 text-center text-card-foreground shadow-sm" role="status">
          <Database className="mx-auto mb-4 h-10 w-10 text-muted-foreground" />
          <h1 className="text-2xl font-semibold">
            {projectsLoading ? t('loadingProjectInfo') : t('selectProjectForKnowledgeBase')}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {projectsLoading ? t('loading') : t('selectProjectForKnowledgeBaseDescription')}
          </p>
          {!projectsLoading && (
            <button
              type="button"
              className="mt-6 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
              onClick={() => navigate('/app/projects')}
            >
              {t('viewProjects')}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`h-full overflow-y-auto transition-colors duration-300 ${
      isDarkMode ? 'bg-[#212121] text-gray-100' : 'bg-white text-gray-900'
    }`}>
      <div className="max-w-7xl mx-auto p-6 space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              {t('rag')}
            </h1>
            <p className={`text-lg ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              {t('ragKnowledgeBase')}
            </p>
          </div>
          <button 
            onClick={refreshStatus} 
            className={`px-4 py-2 rounded-lg transition-colors ${
              isDarkMode 
                ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            }`}
            title={t('refreshStatus')}
          >
            {t('refresh')}
          </button>
        </div>
      
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* 左侧：文件选择和导入 */}
          <div className={`rounded-2xl border p-6 ${
            isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
          }`}>
            <h3 className={`text-lg font-semibold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
              {t('importFilesToKnowledgeBase')}
            </h3>
          
            <div className="mb-4">
              <div className="flex items-center justify-between mb-4">
                <label className="flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={getSelectableFiles().length === selectedFiles.length && selectedFiles.length > 0}
                    onChange={handleSelectAll}
                    className="mr-2 rounded"
                  />
                  <span className={isDarkMode ? 'text-gray-300' : 'text-gray-700'}>
                    {t('selectAll')}
                  </span>
                </label>
                <button
                  className="px-4 py-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={selectedFiles.length === 0 || isImporting}
                  onClick={handleImport}
                >
                  {isImporting 
                    ? t('importing')
                    : t('importSelectedFiles')
                  }
                </button>
              </div>
            
              <div className={`max-h-64 overflow-y-auto border rounded-lg p-3 ${
                isDarkMode ? 'border-gray-600 bg-gray-900' : 'border-gray-300 bg-gray-50'
              }`}>
                {fileList.length === 0 ? (
                  <p className={isDarkMode ? 'text-gray-400' : 'text-gray-600'}>
                    {t('noAvailableFiles')}
                  </p>
                ) : (
                fileList.map(file => {
                  // 检查文件是否已在知识库中或正在处理
                  const isInRag = ragFileList.some(ragFile => ragFileMatches(ragFile, file));
                  
                  const fileStatus = Object.values(fileStatuses).find(status => 
                    status.file_name === file
                  );
                  const isProcessedInRag = fileStatus?.status === 'processed';
                  const isProcessingRag = fileStatus?.status === 'processing';
                  
                  const disabled = isInRag || isProcessedInRag;
                  let statusText = '';
                  if (isProcessedInRag) statusText = currentLanguage === 'zh-CN' ? ' (已加入知识库)' : ' (In Knowledge Base)';
                  else if (isProcessingRag) statusText = currentLanguage === 'zh-CN' ? ' (处理中)' : ' (Processing)';
                  else if (isInRag) statusText = currentLanguage === 'zh-CN' ? ' (已加入知识库)' : ' (In Knowledge Base)';
                  
                  return (
                    <div 
                      key={file}
                      className={`
                        flex items-center p-2 rounded transition-colors
                        ${disabled ? (isDarkMode ? 'text-green-400' : 'text-green-600') : (isDarkMode ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-700 hover:bg-gray-100')}
                        ${isProcessingRag ? (isDarkMode ? 'text-blue-400' : 'text-blue-600') : ''}
                      `}
                    >
                      <input
                        type="checkbox"
                        checked={selectedFiles.includes(file)}
                        onChange={() => handleSelect(file)}
                        disabled={disabled}
                        className="mr-3 rounded"
                      />
                      <span className="truncate flex-1" title={file}>
                        {file}
                        <span className="text-xs opacity-75">{statusText}</span>
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
        
        {/* 右侧：知识库查询 */}
        <div className={`rounded-2xl border p-6 ${
          isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
        }`}>
          <h3 className={`text-lg font-semibold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
            {t('knowledgeBaseQuery')}
          </h3>
        
          <div className="mb-4">
            <div className="flex mb-2">
              <input
                type="text"
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                placeholder={t('queryPlaceholder')}
                className="mr-2 min-w-0 flex-1 rounded border border-input bg-background p-2 text-foreground"
              />
              <button
                onClick={handleQuery}
                disabled={!queryText.trim() || isQuerying}
                className="px-3 py-1 bg-blue-600 rounded text-white disabled:bg-gray-500 disabled:opacity-50"
              >
                {isQuerying ? t('querying') : t('query')}
              </button>
            </div>
            
            {queryResult && (
              <div className="p-3 bg-[#232325] border border-gray-700 rounded max-h-64 overflow-y-auto">
                <h4 className="font-semibold mb-1">{t('queryResult')}:</h4>
                <p className="whitespace-pre-wrap">{queryResult}</p>
              </div>
            )}
          </div>
          
          <div>
            <h4 className="font-semibold mb-1">
              {t('knowledgeBaseFileStatus')}:
              {isLoadingStatuses && <span className="ml-2 text-xs text-gray-400">({t('loading')}...)</span>}
            </h4>
            <div className="max-h-48 overflow-y-auto border border-gray-700 rounded p-2">
              {Object.keys(fileStatuses).length === 0 ? (
                <p className="text-gray-400">{t('noKnowledgeBaseFiles')}</p>
              ) : (
                Object.entries(fileStatuses).map(([fileId, status]) => (
                  <div key={fileId} className={`p-1 ${STATUS_COLORS[status.status] || STATUS_COLORS[status.status?.toLowerCase()] || 'text-gray-400'}`}>
                    <div className="flex justify-between items-center">
                      <span className="truncate flex-1" title={status.file_name || fileId}>
                        {status.file_name || fileId}
                      </span>
                      <div className="flex items-center ml-2 text-xs whitespace-nowrap">
                        <span>
                          {getStatusText(status.status)}
                          {(['failed', 'error'].includes(status.status)) && status.error && (
                            <span className="ml-1" title={status.error}>❌</span>
                          )}
                        </span>
                        {status.status === 'processed' && (
                          <button
                            onClick={() => handleDeleteRagFile(fileId, status.file_name || fileId)}
                            className="ml-2 px-1 py-0.5 bg-red-600 hover:bg-red-700 rounded text-xs"
                            title={t('deleteFromKnowledgeBase')}
                          >
                            {t('delete')}
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
    </div>
  );
}
