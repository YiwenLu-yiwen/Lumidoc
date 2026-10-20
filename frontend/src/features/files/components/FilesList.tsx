import React, { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { fileApi } from '../../../api/file';
import { ragApi, RagBuildResponse } from '../../../api/rag';
import { useAuth } from '../../../context/AuthContext';
import { Eye, Download, RefreshCw, Trash } from 'lucide-react';
import { Spinner } from '../../../components/ui';
import { useTheme } from '../../../context/ThemeContext';

// 导入或定义缺失的组件和函数
const FileTypeIcon = ({ type }: { type: string }) => {
  // 简单的文件类型图标实现
  const getIconClass = () => {
    if (type.includes('pdf')) return '📄';
    if (type.includes('image')) return '🖼️';
    if (type.includes('text')) return '📝';
    if (type.includes('word') || type.includes('document')) return '📘';
    if (type.includes('excel') || type.includes('sheet')) return '📊';
    if (type.includes('powerpoint') || type.includes('presentation')) return '📋';
    if (type.includes('zip') || type.includes('archive')) return '🗄️';
    return '📄';
  };

  return <span className="text-lg">{getIconClass()}</span>;
};

// 格式化文件大小
const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
};

// 格式化日期
const formatDate = (dateStr: string): string => {
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString();
  } catch {
    return dateStr;
  }
};

type UnknownRecord = Record<string, unknown>;

const asRecord = (value: unknown): UnknownRecord | null => {
  if (typeof value === 'object' && value !== null) {
    return value as UnknownRecord;
  }
  return null;
};

const asString = (value: unknown, fallback = ''): string => {
  return typeof value === 'string' ? value : fallback;
};

const asNumber = (value: unknown): number | undefined => {
  return typeof value === 'number' ? value : undefined;
};

export interface FilesListProps {
  fileType: 'regular' | 'rag';
  projectId?: string;
  onTabChange?: (tab: 'uploaded' | 'rag') => void;
}

interface FilePreview {
  fileName: string;
  content?: string;
  url?: string;
  loading: boolean;
  error?: string;
  originalName: string;
  displayName?: string;
  metadata?: unknown;
  isProcessed?: boolean;
  fileId?: string;
  fileHash?: string;
  path?: string;
  size?: number;
}

// 自定义文件项接口，使字段名与组件内部逻辑匹配
interface FileItem {
  originalName: string;   // 用于API调用的原始文件名
  displayName: string;    // 用于显示的文件名
  size?: number;          // 文件大小
  fileType?: string;      // 文件类型
  contentType?: string;   // 文件内容类型
  createdAt?: string;     // 创建时间
  status?: string;        // 文件状态
  fileId?: string;        // 文件ID
  fileHash?: string;      // 文件哈希值
  path?: string;          // 文件路径
  // 🔧 新增：导入状态相关字段
  isImporting?: boolean;     // 是否正在导入
  importedAt?: string;       // 导入时间
  errorMessage?: string;     // 错误消息
  ragStatus?: string;        // RAG索引状态 (pending/processing/completed/failed)
  isInRag?: boolean;         // 是否已在知识库中
  docId?: string;            // RAG文档ID
}

// 文件状态常量
const FileStatus = {
  PENDING: 'pending',
  UPLOADED: 'uploaded',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed'
};

// RAG状态常量
const RagStatus = {
  PENDING: 'pending',      // 等待索引
  PROCESSING: 'processing', // 索引中
  COMPLETED: 'completed',  // 已索引
  FAILED: 'failed'        // 索引失败
};

export const FILE_TYPE_STORAGE_KEY = 'lumidoc_file_list_type';

const FilesList: React.FC<FilesListProps> = ({ fileType, projectId, onTabChange }) => {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<FileItem[]>([]);
  // 文件预览状态
  const [previewingFile, setPreviewingFile] = useState<FilePreview | null>(null);
  // 添加RAG服务状态追踪
  const [ragServiceAvailable, setRagServiceAvailable] = useState<boolean>(true);
  // 添加退避策略计数器
  const [errorCount, setErrorCount] = useState<number>(0);
  const filesRef = useRef(files);
  const errorCountRef = useRef(errorCount);
  filesRef.current = files;
  errorCountRef.current = errorCount;
  // 持久化文件类型，解决刷新问题
  const [currentFileType, setCurrentFileType] = useState<'regular' | 'rag'>(fileType);
  // 添加防重复提交保护
  const [isImporting, setIsImporting] = useState<boolean>(false);
  useAuth(); // 保持认证上下文的连接

  // 主题检测
  const { isDarkMode } = useTheme();

  // 在组件挂载和文件类型变化时保存到本地存储
  useEffect(() => {
    try {
      localStorage.setItem(FILE_TYPE_STORAGE_KEY, fileType);
      setCurrentFileType(fileType);
      console.log(`[FilesList] 保存文件类型: ${fileType}`);
    } catch (e) {
      console.error('保存文件类型失败:', e);
    }
  }, [fileType]);

  // 在组件挂载时，尝试从本地存储恢复文件类型
  useEffect(() => {
    try {
      const savedType = localStorage.getItem(FILE_TYPE_STORAGE_KEY) as 'regular' | 'rag' | null;
      if (savedType && (savedType === 'regular' || savedType === 'rag')) {
        console.log(`[FilesList] 从本地存储恢复文件类型: ${savedType}`);
        setCurrentFileType(savedType);
      }
    } catch (e) {
      console.error('读取保存的文件类型失败:', e);
    }
  }, []);

  // 🔧 监听导入文件事件
  useEffect(() => {
    const handleAddImportingFiles = (event: CustomEvent) => {
      const { files: importingFiles } = event.detail;

      // 只有RAG文件列表才响应这个事件
      if (currentFileType === 'rag' && importingFiles && Array.isArray(importingFiles)) {
        console.log(`[FilesList RAG] 收到添加导入文件事件，文件数量: ${importingFiles.length}`);

        setFiles(prev => {
          // 移除重复的文件，添加新的处理中文件
          const existing = prev.filter(f => !importingFiles.some((pf: FileItem) =>
            getFileUniqueId(f) === getFileUniqueId(pf)
          ));
          return [...existing, ...importingFiles];
        });
      }
    };

    // 添加事件监听器
    document.addEventListener('addImportingFiles', handleAddImportingFiles as EventListener);

    // 清理函数
    return () => {
      document.removeEventListener('addImportingFiles', handleAddImportingFiles as EventListener);
    };
  }, [currentFileType]);

  // 检查用户是否有编辑权限
  const canEdit = true; // 临时设置所有用户拥有编辑权限，解决删除按钮显示问题

  // 获取文件状态文本 - 改进版
  const getStatusText = (file: FileItem) => {
    // 优先显示RAG状态（如果存在）
    if (file.ragStatus) {
      switch (file.ragStatus) {
        case RagStatus.PENDING:
          return '等待索引';
        case RagStatus.PROCESSING:
          return '索引中';
        case RagStatus.COMPLETED:
          return '已索引';
        case RagStatus.FAILED:
          return '索引失败';
      }
    }

    // 如果正在导入，显示导入状态
    if (file.isImporting) {
      return '索引中';
    }

    // 显示基础文件处理状态
    switch (file.status) {
      case FileStatus.PENDING:
        return '等待处理';
      case FileStatus.UPLOADED:
        return '已上传';
      case FileStatus.PROCESSING:
        return '处理中';
      case FileStatus.COMPLETED:
        return currentFileType === 'rag' ? '已完成' : '已完成';
      case FileStatus.FAILED:
        return '处理失败';
      case 'imported':
        return '已索引';
      default:
        return '未知状态';
    }
  };

  // 获取状态样式 - 改进版
  const getStatusClassName = (file: FileItem) => {
    // 优先显示RAG状态样式
    if (file.ragStatus) {
      switch (file.ragStatus) {
        case RagStatus.PENDING:
          return 'bg-yellow-800 text-yellow-200 border-yellow-700';
        case RagStatus.PROCESSING:
          return 'bg-blue-800 text-blue-200 border-blue-700 animate-pulse';
        case RagStatus.COMPLETED:
          return 'bg-green-800 text-green-200 border-green-700';
        case RagStatus.FAILED:
          return 'bg-red-800 text-red-200 border-red-700';
      }
    }

    // 如果正在导入，显示动画效果
    if (file.isImporting) {
      return 'bg-blue-800 text-blue-200 border-blue-700 animate-pulse';
    }

    // 基础状态样式
    switch (file.status) {
      case FileStatus.PENDING:
      case FileStatus.UPLOADED:
        return 'bg-yellow-800 text-yellow-200 border-yellow-700';
      case FileStatus.PROCESSING:
        return 'bg-blue-800 text-blue-200 border-blue-700 animate-pulse';
      case FileStatus.COMPLETED:
      case 'imported':
        return 'bg-green-800 text-green-200 border-green-700';
      case FileStatus.FAILED:
        return 'bg-red-800 text-red-200 border-red-700';
      default:
        return 'bg-gray-800 text-gray-200 border-gray-700';
    }
  };

  // 判断文件是否可操作
  const isFileActionable = (file: FileItem) => {
    return file.status === FileStatus.COMPLETED ||
           file.status === FileStatus.FAILED ||
           !file.status;
  };

  // 🔧 新增：判断文件是否可以导入到知识库
  const canImportToRag = (file: FileItem) => {
    // 只有已完成处理的文件才能导入，且不能重复导入
    return file.status === FileStatus.COMPLETED &&
           !file.isInRag &&
           !file.isImporting &&
           file.ragStatus !== RagStatus.COMPLETED;
  };

  // 🔧 新增：判断文件是否已在知识库中
  const isFileInRag = (file: FileItem) => {
    return file.isInRag || file.ragStatus === RagStatus.COMPLETED;
  };

  // 获取文件的唯一标识符 - 支持FileItem和FilePreview
  const getFileUniqueId = (file: {originalName: string, fileId?: string, fileHash?: string, path?: string, size?: number}): string => {
    // 优先使用fileHash，其次是fileId，最后才用originalName加上其他信息确保唯一性
    if (file.fileHash) return file.fileHash;
    if (file.fileId) return `id-${file.fileId}`;
    // 最后的备选方案是使用原始名称、路径和大小的组合
    return `name-${file.originalName}-path-${file.path || ''}-size-${file.size || '0'}`;
  };

  // 刷新文件列表
  const refreshFiles = async () => {
    if (!projectId) return;

    setLoading(true);
    setError(null);
    try {
      // 使用持久化的文件类型，而不是传入的fileType
      if (currentFileType === 'regular') {
        console.log(`[FilesList] 刷新项目${projectId}的常规文件列表`);
        const result = await fileApi.listFiles(projectId);
        if (!result || !Array.isArray(result)) {
          throw new Error('获取到的文件列表格式无效');
        }

        // 检查文件对象的结构
        const hasValidStructure = result.every(f => f && typeof f.filename === 'string');
        if (!hasValidStructure) {
          throw new Error('文件数据结构异常');
        }

        console.log(`[FilesList] 获取到${result.length}个文件`);

        // 🔧 更新：映射常规文件数据，包含RAG状态
        setFiles(result.map(f => ({
          originalName: f.filename, // 保留原始文件名用于API调用
          displayName: f.display_name || f.filename, // 使用显示名称或原始名称
          size: f.size,
          fileType: f.file_type,
          contentType: f.content_type,
          createdAt: f.created_at,
          status: f.status || 'pending', // 添加文件状态
          fileId: f.file_id,
          fileHash: f.file_hash,
          // 🔧 新增：RAG状态相关字段（从数据库获取）
          ragStatus: f.rag_status, // RAG索引状态
          isInRag: f.is_in_rag || false, // 是否已在知识库中
          isImporting: false, // 默认不在导入中
          docId: f.doc_id || '', // RAG文档ID
          importedAt: f.rag_processed_at, // RAG处理时间
          errorMessage: f.rag_error_message || '' // RAG错误信息
        } as FileItem)));
      } else {
        console.log(`[FilesList] 刷新项目${projectId}的RAG文件列表`);
        const response = await ragApi.getRagFiles(projectId);
        console.log(`[FilesList] RAG文件API响应:`, response);

        // 成功获取结果，重置错误计数并标记服务可用
        setRagServiceAvailable(true);
        setErrorCount(0);

        // 处理API响应
        let resultArray: unknown[] = [];
        if (response && typeof response === 'object') {
          // 如果是新格式 {success: true, files: Array}
          if (response.success && Array.isArray(response.files)) {
            resultArray = response.files;
          }
          // 如果直接是数组格式(兼容旧版)
          else if (Array.isArray(response)) {
            resultArray = response;
          }
          // 处理404 Not Found响应格式
          else if ((response as { detail?: string }).detail === 'Not Found') {
            console.log('[FilesList] RAG服务返回404 Not Found，使用空数组');
            resultArray = [];
          }
          else {
            console.warn('[FilesList] RAG文件API响应格式不符合预期:', response);
            resultArray = [];
          }
        }

        console.log(`[FilesList] 处理后的RAG文件数组:`, resultArray);

        // 🔧 更新：映射RAG文件数据，包含完整的状态信息
        if (resultArray.length > 0) {
          setFiles(resultArray.map((file) => {
            const fileRecord = asRecord(file);
            return ({
            originalName: typeof file === 'string' ? file : asString(fileRecord?.filename ?? fileRecord?.name, ''),
            displayName: typeof file === 'string' ? file : asString(fileRecord?.display_name ?? fileRecord?.filename ?? fileRecord?.name, ''),
            size: asNumber(fileRecord?.size),
            fileType: asString(fileRecord?.file_type, 'unknown'),
            contentType: asString(fileRecord?.content_type ?? fileRecord?.file_type, 'text/markdown'),
            createdAt: asString(fileRecord?.created_at),
            status: asString(fileRecord?.status, 'completed'),
            fileId: fileRecord?.file_id ? String(fileRecord.file_id) : '',
            fileHash: asString(fileRecord?.file_hash),
            path: asString(fileRecord?.path),
            // 🔧 新增：RAG状态相关字段
            ragStatus: asString(fileRecord?.rag_status, RagStatus.COMPLETED), // RAG文件默认已完成
            isInRag: true, // RAG列表中的文件都已在知识库中
            isImporting: false, // 显示的文件不应该在导入中
            docId: asString(fileRecord?.doc_id), // RAG文档ID
            importedAt: asString(fileRecord?.selected_at ?? fileRecord?.rag_processed_at), // 导入时间
            errorMessage: asString(fileRecord?.rag_error_message) // 错误信息
          } as FileItem);
          }));
        } else {
          console.log('[FilesList] RAG文件列表为空');
          setFiles([]);
        }
      }
    } catch (err) {
      console.error(`获取${currentFileType === 'regular' ? '普通' : 'RAG'}文件列表失败:`, err);
      setError(err instanceof Error ? err.message : '获取文件列表失败');
      toast.error(err instanceof Error ? err.message : '获取文件列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const refreshed = (event: Event) => {
      if ((event as CustomEvent).detail?.projectId === projectId) void refreshFiles();
    };
    window.addEventListener('file-operations-updated', refreshed);
    return () => window.removeEventListener('file-operations-updated', refreshed);
    // refreshFiles reads this project's current filters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, currentFileType]);

  useEffect(() => {
    const loadFiles = async () => {
      if (!projectId) return;

      setLoading(true);
      setError(null);

      try {
        let fileList: FileItem[] = [];

        // 使用持久化的文件类型，而不是传入的fileType
        if (currentFileType === 'regular') {
          // 获取常规文件
          console.log(`[FilesList] 加载项目${projectId}的常规文件列表`);
          const result = await fileApi.listFiles(projectId);
          console.log(`[FilesList] 获取到${result.length}个文件:`, result);

          fileList = result.map(file => {
            // 确保文件名不为空
            const originalName = file.filename || '';
            let displayName = '';

            try {
              // 尝试使用display_name或解码filename
              displayName = file.display_name || decodeURIComponent(originalName);

              // 如果displayName为空或无效，尝试从路径中提取文件名
              if (!displayName || displayName === 'undefined' || displayName === 'null') {
                if (file.path) {
                  const pathParts = file.path.split('/');
                  if (pathParts && pathParts.length > 0) {
                    // 检查最后一部分是否为哈希值（通常是64位十六进制字符）
                    const lastPart = pathParts[pathParts.length - 1];
                    if (/^[a-f0-9]{64}\.\w+$/i.test(lastPart)) {
                      // 如果是哈希值文件名，使用原始上传时的文件名或默认名称
                      displayName = file.name || '未命名文件';
                    } else {
                      displayName = lastPart || originalName;
                    }
                  } else {
                    displayName = originalName;
                  }
                } else {
                  // 如果没有路径，使用原始文件名
                  displayName = originalName;
                }
              }

              // 检查displayName是否为哈希值（通常是64位十六进制字符）
              if (/^[a-f0-9]{64}\.\w+$/i.test(displayName)) {
                // 如果是哈希值，使用更友好的名称
                displayName = file.name || '未命名文件';
              }

              // 如果仍然为空，设置为未命名文件
              if (!displayName) {
                displayName = '未命名文件';
              }

              console.log(`[FilesList] 处理文件名: 原始名=${originalName}, 显示名=${displayName}, 路径=${file.path || '无'}`);
            } catch (e) {
              console.warn(`[FilesList] 文件名解码失败:`, e);
              displayName = originalName || '未命名文件';
            }

            return {
              originalName: originalName,
              displayName: displayName,
              size: file.size,
              fileType: file.file_type,
              contentType: file.content_type,
              createdAt: file.created_at,
              status: file.status || 'pending',
              fileId: file.file_id ? String(file.file_id) : '',
              fileHash: file.file_hash || '',
              path: file.path || ''
            } as FileItem;
          });

          console.log('[FilesList] 处理后的文件列表:', fileList);
          setFiles(fileList);
        } else {
          // 获取RAG文件
          console.log(`[FilesList] 加载项目${projectId}的RAG文件列表`);
          try {
            const response = await ragApi.getRagFiles(projectId);
            console.log(`[FilesList] RAG文件API响应:`, response);

            // 检查是否有错误
            if (!response.success) {
              console.warn(`[FilesList] RAG文件API返回错误:`, response.error);

              // 处理认证错误
              if (response.authError) {
                setError(response.error || '认证失败，请重新登录');
                setRagServiceAvailable(false);
                fileList = [];
              }
              // 处理其他错误
              else {
                setError(response.error || 'RAG服务暂时不可用');
                setRagServiceAvailable(false);
                fileList = [];
              }
            } else {
              // 成功获取结果，重置错误计数并标记服务可用
              setRagServiceAvailable(true);
              setErrorCount(0);
              setError(null);

              // 处理成功响应
              const resultArray: unknown[] = response.files || [];
              console.log(`[FilesList] 处理后的RAG文件数组:`, resultArray);

              // 确保result是数组，否则使用空数组
              if (resultArray.length > 0) {
                fileList = resultArray.map((file) => {
                  const fileRecord = asRecord(file);
                  return ({
                  originalName: typeof file === 'string' ? file : asString(fileRecord?.filename ?? fileRecord?.name, ''),
                  displayName: typeof file === 'string' ? file : asString(fileRecord?.display_name ?? fileRecord?.displayName ?? fileRecord?.filename ?? fileRecord?.name, ''),
                  size: asNumber(fileRecord?.size),
                  fileType: asString(fileRecord?.file_type ?? fileRecord?.fileType, 'unknown'),
                  contentType: asString(fileRecord?.content_type ?? fileRecord?.contentType ?? fileRecord?.file_type ?? fileRecord?.fileType, 'text/markdown'),
                  createdAt: asString(fileRecord?.created_at ?? fileRecord?.createdAt),
                  status: asString(fileRecord?.status ?? fileRecord?.rag_status, 'completed'),
                  fileId: (fileRecord?.file_id || fileRecord?.id) ? String(fileRecord?.file_id || fileRecord?.id) : '',
                  fileHash: asString(fileRecord?.file_hash ?? fileRecord?.fileHash),
                  path: asString(fileRecord?.path)
                } as FileItem);
                });
              } else {
                console.log('[FilesList] RAG文件列表为空');
                fileList = [];
              }
            }
          } catch (ragError: unknown) {
            console.error('[FilesList] 获取RAG文件失败:', ragError);

            // 增加错误计数
            setErrorCount(prev => prev + 1);

            // 如果是404错误，标记RAG服务状态
            const errorRecord = asRecord(ragError);
            const errorStatus = errorRecord?.status;
            if (errorStatus === 404) {
              console.log('[FilesList] RAG文件服务返回404错误');

              // 检查响应内容，区分"无文件"和"服务不可用"
              const ragErrorData = asRecord(errorRecord?.data);
              const errorDetail = asString(ragErrorData?.detail, '');
              if (typeof errorDetail === 'string' && errorDetail.toLowerCase().includes('not found')) {
                // 很可能是服务不可用
                setRagServiceAvailable(false);
                setError('RAG知识库服务不可用，请联系管理员');
              } else {
                // 可能只是没有文件
                setRagServiceAvailable(true);
                setError(null);
              }

              fileList = [];
            } else {
              // 其他错误
              setRagServiceAvailable(false);
              throw ragError;
            }
          }
        }

        // 确保所有文件都有显示名称，如果没有则使用原始文件名
        fileList = fileList.map(file => ({
          ...file,
          displayName: file.displayName || decodeURIComponent(file.originalName || '')
        }));

        console.log('[FilesList] 处理后的文件列表:', fileList);
        setFiles(fileList);
      } catch (err: unknown) {
        console.error('获取文件列表错误:', err);
        const errorMessage = err instanceof Error ? err.message : '未知错误';
        setError(errorMessage || '获取文件列表失败');
        toast.error('获取文件列表失败: ' + (errorMessage || '未知错误'));
      } finally {
        setLoading(false);
      }
    };

    loadFiles();

    // 🔧 智能刷新机制：根据文件状态和用户活动动态调整刷新频率
    let consecutiveNoChanges = 0; // 连续无变化次数
    let lastFileStates = new Map<string, string>(); // 记录上次文件状态
    let userLastActive = Date.now(); // 用户最后活动时间
    let isTabVisible = true; // 标签页是否可见

    // 监听用户活动
    const updateUserActivity = () => {
      userLastActive = Date.now();
    };

    // 监听标签页可见性
    const handleVisibilityChange = () => {
      isTabVisible = !document.hidden;
      if (isTabVisible) {
        userLastActive = Date.now();
        // 标签页重新可见时立即刷新一次
        setTimeout(loadFiles, 100);
      }
    };

    // 添加事件监听器
    document.addEventListener('mousemove', updateUserActivity);
    document.addEventListener('keydown', updateUserActivity);
    document.addEventListener('click', updateUserActivity);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    // 智能计算刷新间隔
    const updateInterval = () => {
      const hasProcessingFiles = filesRef.current.some(file =>
        file.status === FileStatus.PROCESSING || file.status === FileStatus.PENDING || file.isImporting
      );

      const isUserInactive = (Date.now() - userLastActive) > 60000; // 用户1分钟内无活动

      // 如果RAG服务不可用，使用退避策略
      if (currentFileType === 'rag' && (!ragServiceAvailable || errorCountRef.current > 0)) {
        return Math.min(60000 * Math.pow(2, Math.min(errorCountRef.current, 4)), 600000); // 1分钟到10分钟（增加基础间隔）
      }

      // 如果标签页不可见，大幅减少刷新频率
      if (!isTabVisible) {
        return hasProcessingFiles ? 60000 : 600000; // 1分钟或10分钟（大幅减少）
      }

      // 如果连续多次无变化，逐渐增加间隔
      if (consecutiveNoChanges > 3) {
        const backoffMultiplier = Math.min(consecutiveNoChanges - 3, 5);
        return hasProcessingFiles ?
          Math.min(30000 + (backoffMultiplier * 15000), 120000) : // 30秒到2分钟
          Math.min(120000 + (backoffMultiplier * 60000), 600000); // 2分钟到10分钟
      }

      // 根据文件状态和用户活动决定刷新频率（大幅优化）
      if (hasProcessingFiles) {
        return isUserInactive ? 30000 : 15000; // 活跃时15秒，不活跃时30秒（从5秒改为15秒）
      } else {
        return isUserInactive ? 300000 : 120000; // 活跃时2分钟，不活跃时5分钟（从30秒改为2分钟）
      }
    };

    // 检测文件状态是否有变化
    const detectFileChanges = () => {
      const currentStates = new Map<string, string>();
      filesRef.current.forEach(file => {
        const key = getFileUniqueId(file);
        currentStates.set(key, `${file.status}:${file.isImporting}:${file.size}`);
      });

      // 比较状态变化
      let hasChanges = false;
      if (currentStates.size !== lastFileStates.size) {
        hasChanges = true;
      } else {
        for (const [key, value] of currentStates) {
          if (lastFileStates.get(key) !== value) {
            hasChanges = true;
            break;
          }
        }
      }

      if (hasChanges) {
        consecutiveNoChanges = 0;
        console.log('[FilesList] 检测到文件状态变化，重置连续无变化计数');
      } else {
        consecutiveNoChanges++;
        console.log(`[FilesList] 连续${consecutiveNoChanges}次无变化`);
      }

      lastFileStates = currentStates;
      return hasChanges;
    };

    // 增强的loadFiles函数，包含变化检测
    const smartLoadFiles = async () => {
      // 🔧 修复：避免在组件卸载后执行
      if (!document.body.contains(document.querySelector('[data-file-list]'))) {
        return;
      }

      await loadFiles();

      // 检测变化
      detectFileChanges();

      // 如果有变化，立即调整刷新间隔
      adjustInterval();
    };

    // 设置初始间隔
    let intervalTime = updateInterval();
    let intervalId = setInterval(smartLoadFiles, intervalTime);

    // 当文件列表变化时调整刷新间隔
    const adjustInterval = () => {
      clearInterval(intervalId);
      intervalTime = updateInterval();
      console.log(`[FilesList] 调整刷新间隔为${intervalTime}ms`);
      intervalId = setInterval(smartLoadFiles, intervalTime);
    };

    // 🔧 修复：减少调整频率，避免过度轮询
    const debounceTimer = setTimeout(adjustInterval, 1000);

    // 组件卸载时清除定时器和事件监听器
    return () => {
      clearInterval(intervalId);
      clearTimeout(debounceTimer);

      // 清除事件监听器
      document.removeEventListener('mousemove', updateUserActivity);
      document.removeEventListener('keydown', updateUserActivity);
      document.removeEventListener('click', updateUserActivity);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [projectId, currentFileType, ragServiceAvailable]); // 修复：移除errorCount依赖，避免无限循环

  // 选中/取消选中文件
  const handleSelect = (file: FileItem) => {
    const fileId = getFileUniqueId(file);
    setSelectedFiles(prev =>
      prev.some(f => getFileUniqueId(f) === fileId)
        ? prev.filter(f => getFileUniqueId(f) !== fileId)
        : [...prev, file]
    );
  };

  // 全选
  const handleSelectAll = () => {
    setSelectedFiles(
      selectedFiles.length === files.length ? [] : [...files]
    );
  };

  // 判断文件是否被选中 - 更新参数类型以匹配预览文件类型
  const isFileSelected = (file: {originalName: string, fileId?: string, fileHash?: string, path?: string, size?: number}): boolean => {
    return selectedFiles.some(f => getFileUniqueId(f) === getFileUniqueId(file));
  };

  // 导入知识库
  const handleImport = async () => {
    if (!projectId) return;

    // 防重复提交保护
    if (isImporting) {
      toast.warning('正在导入中，请勿重复操作');
      return;
    }

    if (selectedFiles.length === 0) {
      toast.error('请选择要导入知识库的文件');
      return;
    }

    // 🔧 新增：检查是否有已在知识库中的文件，防止重复导入
    const alreadyImportedFiles = selectedFiles.filter(file => isFileInRag(file));
    if (alreadyImportedFiles.length > 0) {
      const fileNames = alreadyImportedFiles.map(f => f.displayName || f.originalName).join(', ');
      toast.warning(`以下文件已在知识库中，无需重复导入：${fileNames}`);

      // 从选中文件中移除已导入的文件
      const filesToImport = selectedFiles.filter(file => !isFileInRag(file));
      if (filesToImport.length === 0) {
        return; // 所有文件都已导入，直接返回
      }
      // 继续处理可导入的文件
      setSelectedFiles(filesToImport);
    }

    // 🔧 新增：检查是否有不可导入的文件（未完成处理）
    const unprocessedFiles = selectedFiles.filter(file => !canImportToRag(file));
    if (unprocessedFiles.length > 0) {
      const fileNames = unprocessedFiles.map(f => f.displayName || f.originalName).join(', ');
      toast.warning(`以下文件尚未处理完成，无法导入：${fileNames}`);

      // 从选中文件中移除未处理的文件
      const readyFiles = selectedFiles.filter(file => canImportToRag(file));
      if (readyFiles.length === 0) {
        return; // 没有可导入的文件
      }
      setSelectedFiles(readyFiles);
    }

    try {
      // 设置导入状态，防止重复提交
      setIsImporting(true);

      // 显示导入中的状态
      const loadingToast = toast.loading('正在导入文件到知识库...');

      // 获取所选文件的fileHash或fileId (优先使用fileHash)
      const fileIdentifiers = selectedFiles.map(f => f.fileHash || f.fileId || f.originalName);

      console.log('[FilesList] 导入文件到知识库, 文件标识:', fileIdentifiers);

      // 🔧 修复：立即更新本地状态，显示处理中的文件
      const processingFiles = selectedFiles.map(file => ({
        ...file,
        status: FileStatus.PROCESSING,
        displayName: file.displayName || file.originalName,
        // 为RAG文件添加额外的标识
        isImporting: true,
        importedAt: new Date().toISOString()
      }));

      // 🔧 关键修复：立即切换到知识库文件标签页
      if (onTabChange) {
        console.log('[FilesList] 切换到知识库文件标签页');
        onTabChange('rag');
        // 发送事件通知FileManager切换标签页
        document.dispatchEvent(new CustomEvent('switchToRagTab'));
      }

      // 🔧 立即添加处理中的文件到RAG文件列表（无论当前在哪个标签页）
      // 通过自定义事件通知RAG文件列表组件添加这些文件
      const ragListEvent = new CustomEvent('addImportingFiles', {
        detail: { files: processingFiles }
      });
      document.dispatchEvent(ragListEvent);

      // 同时更新当前组件的文件列表（如果是RAG类型）
      if (currentFileType === 'rag') {
        setFiles(prev => {
          // 移除重复的文件，添加新的处理中文件
          const existing = prev.filter(f => !processingFiles.some(pf =>
            getFileUniqueId(f) === getFileUniqueId(pf)
          ));
          return [...existing, ...processingFiles];
        });
      }

      const response: RagBuildResponse = await ragApi.buildRag(projectId, fileIdentifiers);

      // 关闭加载提示
      toast.dismiss(loadingToast);

      // 检查响应结果
      if (response && response.success) {
        // 成功导入
        const processedCount = response.processed_count || 0;
        const failedFiles = response.failed_files || [];

        if (failedFiles.length > 0) {
          // 部分文件导入失败
          toast.warning(
            `已成功导入${processedCount}个文件，${failedFiles.length}个文件导入失败。`
          );

          // 🔧 修复：更新失败文件的状态
          if (currentFileType === 'rag') {
            setFiles(prev => prev.map(file => {
              const failedFile = failedFiles.find(f =>
                f.file_hash === file.fileHash ||
                f.file_hash === file.fileId ||
                f.file_hash === file.originalName
              );
              if (failedFile) {
                return {
                  ...file,
                  status: FileStatus.FAILED,
                  isImporting: false,
                  errorMessage: failedFile.error || '导入失败'
                };
              }
              return file;
            }));
          }
        } else {
          // 全部导入成功
          toast.success(`已成功导入${processedCount}个文件到知识库`);
        }

        // 🔧 修复：更新成功文件的状态
        if (currentFileType === 'rag') {
          setFiles(prev => prev.map(file => {
            if (file.isImporting) {
              return {
                ...file,
                status: FileStatus.COMPLETED,
                isImporting: false,
                importedAt: new Date().toISOString()
              };
            }
            return file;
          }));
        }

        // 清空选中状态
        setSelectedFiles([]);

        // 触发自定义事件，通知父组件切换到RAG标签页
        const event = new CustomEvent('switchToRagTab', {
          bubbles: true,
          detail: { success: true }
        });
        document.dispatchEvent(event);

        // 如果父组件提供了onTabChange回调，也调用它
        if (onTabChange) {
          onTabChange('rag');
        }

        // 🔧 修复：立即刷新RAG文件列表，确保状态同步
        setTimeout(() => {
          // 触发刷新RAG文件列表的事件
          const refreshEvent = new CustomEvent('refreshRagFiles', {
            bubbles: true,
            detail: { projectId }
          });
          document.dispatchEvent(refreshEvent);

          // 强制刷新当前文件列表
          refreshFiles();
        }, 500); // 给后端一点时间来更新状态

      } else {
        // 导入失败
        const errorMessage = response?.message || '导入失败';
        toast.error(`导入失败: ${errorMessage}`);

        // 🔧 修复：更新失败状态
        if (currentFileType === 'rag') {
          setFiles(prev => prev.map(file => {
            if (file.isImporting) {
              return {
                ...file,
                status: FileStatus.FAILED,
                isImporting: false,
                errorMessage: errorMessage
              };
            }
            return file;
          }));
        }
      }

    } catch (error) {
      console.error('[FilesList] 导入知识库失败:', error);
      toast.error(`导入失败: ${error instanceof Error ? error.message : '未知错误'}`);

      // 🔧 修复：错误情况下也要更新状态
      if (currentFileType === 'rag') {
        setFiles(prev => prev.map(file => {
          if (file.isImporting) {
            return {
              ...file,
              status: FileStatus.FAILED,
              isImporting: false,
              errorMessage: error instanceof Error ? error.message : '导入失败'
            };
          }
          return file;
        }));
      }
    } finally {
      // 重置导入状态，确保按钮可以再次使用
      setIsImporting(false);
    }
  };

  // 文件下载处理函数，支持FilePreview或文件对象
  const handleDownloadFile = async (file: { originalName: string, displayName?: string, isProcessed?: boolean, content?: string }) => {
    if (!projectId) return;

    // 确定显示名称
    const displayName = file.displayName || file.originalName;

    // 检查文件名是否有效
    if (!displayName && !file.originalName) {
      toast.error('文件名信息丢失，无法下载');
      console.error('文件名信息缺失:', file);
      return;
    }

    // 回退到原始文件下载的函数
    const fallbackToOriginalDownload = async (loadingToastId?: string) => {
      try {
        // 检查文件名是否有效
        const downloadFilename = file.originalName || displayName;
        if (!downloadFilename) {
          throw new Error('文件名信息丢失，无法下载原始文件');
        }

        toast.warning(`处理后的内容不可用，将下载原始文件`);

        const apiUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
        const downloadUrl = `${apiUrl}/api/file/projects/${projectId}/files/download/${encodeURIComponent(downloadFilename)}?download=true&t=${Date.now()}`;

        // 使用fetch获取文件，确保认证令牌被正确传递
        const token = localStorage.getItem('lumidoc_token');
        const headers: Record<string, string> = {};

        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(downloadUrl, { headers });

        if (response.status === 401) {
          console.warn('认证失败，需要重新登录');
          toast.error('认证已过期，请重新登录后再试');
          throw new Error('认证失败: 登录令牌已过期');
        }

        if (!response.ok) {
          throw new Error(`下载失败: ${response.status} ${response.statusText}`);
        }

        // 获取文件名
        const contentDisposition = response.headers.get('content-disposition');
        let responseFilename = displayName;
        if (contentDisposition) {
          const matches = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
          if (matches && matches[1]) {
            responseFilename = matches[1].replace(/['"]/g, '');
          }
        }

        // 创建Blob并下载
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = responseFilename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        // 关闭加载提示
        if (loadingToastId) {
          toast.dismiss(loadingToastId);
        }
        toast.success(`开始下载原始文件: ${responseFilename}`);
      } catch (err) {
        if (loadingToastId) {
          toast.dismiss(loadingToastId);
        }
        console.error('下载原始文件失败:', err);
        toast.error(`下载失败: ${err instanceof Error ? err.message : '未知错误'}`);
      }
    };

    // 如果文件已经OCR处理且有内容，直接下载处理后的内容
    if (file.isProcessed && file.content) {
      // 创建Blob并下载
      const blob = new Blob([file.content || ''], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${displayName.replace(/\.[^/.]+$/, '')}_OCR处理结果.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success(`开始下载OCR处理结果: ${displayName}`);
      return;
    }

    // 显示加载提示
    const loadingToastId = toast.loading(`正在准备下载文件: ${displayName}...`);

    try {
      // 首先尝试获取OCR处理后的内容
      const apiUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
      const filename = file.originalName || displayName;
      if (!filename) {
        throw new Error('文件名信息缺失，无法获取内容');
      }
      const contentUrl = `${apiUrl}/api/file/projects/${projectId}/files/content/${encodeURIComponent(filename)}`;

      console.log(`尝试获取处理后的内容: ${contentUrl}`);

      const token = localStorage.getItem('lumidoc_token');
      const headers: Record<string, string> = {
        'Accept': 'application/json',
        'Cache-Control': 'no-cache, no-store'
      };

      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(contentUrl, { headers });
      console.log(`内容响应状态: ${response.status}, 内容类型: ${response.headers.get('content-type')}`);
      if (response.status === 401) {
        console.warn('认证失败，需要重新登录');
        toast.error('认证已过期，请重新登录后再试');
        throw new Error('认证失败: 登录令牌已过期');
      }
      if (!response.ok) {
        throw new Error("获取处理结果失败");
      }

      // 检查内容类型
      const contentType = response.headers.get('content-type');

      let data;
      // 如果是JSON格式，按JSON处理
      if (contentType && contentType.includes('application/json')) {
        const jsonData = await response.json();
        if (jsonData.success && jsonData.content && jsonData.content.length > 0) {
          console.log(`成功获取处理后的内容，长度: ${jsonData.content.length}`);
          data = { content: jsonData.content };
        } else {
          console.warn('JSON响应不包含有效内容:', jsonData);
          throw new Error('处理后的内容不可用');
        }
      } else {
        // 其他格式，作为文本处理
        const text = await response.text();
        // 检查是否是HTML内容（通常是错误页面）
        if (text.trim().startsWith('<!DOCTYPE html>') || text.trim().startsWith('<html')) {
          console.warn('收到HTML内容而非预期的文件内容');
          throw new Error('服务器返回了HTML页面而非文件内容');
        }
        data = { content: text };
      }

      // 创建Blob并下载
      const content = data.content;
      const blob = new Blob([content], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${displayName.replace(/\.[^/.]+$/, '')}_OCR处理结果.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.dismiss(loadingToastId);
      toast.success(`开始下载OCR处理结果: ${displayName}`);
    } catch (err) {
      console.error('获取处理内容失败:', err);
      // 回退到原始文件下载
      await fallbackToOriginalDownload(loadingToastId.toString());
    }
  };

  // 预览文件
  const handlePreview = async (file: FileItem) => {
    if (!projectId) return;

    if (!isFileActionable(file)) {
      toast.error('此文件处理失败，无法预览');
      return;
    }

    // 文件处理中或等待处理时给予提示，但仍允许尝试预览
    if (file.status === FileStatus.PENDING || file.status === FileStatus.PROCESSING) {
      toast.warning('文件正在处理中，预览可能不完整');
    }

    setPreviewingFile({
      fileName: file.displayName,
      originalName: file.originalName,
      loading: true
    });

    try {
      console.log(`开始预览文件: ${file.displayName}, 原始名称: ${file.originalName}`);

      // 尝试两种方式获取文件内容：先尝试处理后的内容，如果失败则尝试原始文件
      const apiUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';

      // 1. 首先尝试获取处理后的内容
      const previewContentFilename = file.originalName || file.displayName;
      if (!previewContentFilename) {
        throw new Error('文件名信息缺失，无法获取内容进行预览');
      }
      const contentUrl = `${apiUrl}/api/file/projects/${projectId}/files/content/${encodeURIComponent(previewContentFilename)}`;
      console.log(`预览请求URL: ${contentUrl}`);

      try {
        const token = localStorage.getItem('lumidoc_token');
        const headers: Record<string, string> = {
          'Accept': 'application/json',
          'Cache-Control': 'no-cache, no-store'
        };

        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        const contentResponse = await fetch(contentUrl, { headers });
        console.log(`内容响应状态: ${contentResponse.status}, 内容类型: ${contentResponse.headers.get('content-type')}`);

        // Handle authentication errors
        if (contentResponse.status === 401) {
          console.warn('认证失败，需要重新登录');
          toast.error('认证已过期，请重新登录后再试');
          throw new Error('认证失败: 登录令牌已过期');
        }

        if (contentResponse.ok) {
          // 检查内容类型
          const contentType = contentResponse.headers.get('content-type');
          console.log(`文件内容类型: ${contentType}`);

          // 如果是JSON格式，按JSON处理
          if (contentType && contentType.includes('application/json')) {
            console.log('处理JSON格式内容');
            const contentData = await contentResponse.json();
            console.log('JSON内容:', contentData);

            if (contentData.success && contentData.content && contentData.content.length > 0) {
              // 使用处理后的Markdown内容
              setPreviewingFile({
                fileName: file.displayName,
                originalName: file.originalName,
                content: contentData.content,
                metadata: contentData.metadata || {},
                loading: false,
                isProcessed: true
              });
              console.log('成功设置JSON内容预览');
              return;
            } else {
              console.warn('JSON响应不包含有效内容:', contentData);
              throw new Error('处理后的内容不可用');
            }
          } else if (contentType && (contentType.includes('text/') || contentType.includes('application/markdown'))) {
            // 文本内容
            console.log('处理文本格式内容');
            const textContent = await contentResponse.text();
            console.log(`获取到文本内容，长度: ${textContent.length}`);

            // 检查是否是HTML内容（通常是错误页面）
            if (textContent.trim().startsWith('<!DOCTYPE html>') || textContent.trim().startsWith('<html')) {
              console.warn('收到HTML内容而非预期的文件内容，可能是错误页面');
              throw new Error('服务器返回了HTML页面而非文件内容');
            }

            setPreviewingFile({
              fileName: file.displayName,
              originalName: file.originalName,
              content: textContent,
              loading: false,
              isProcessed: true
            });
            console.log('成功设置文本内容预览');
            return;
          } else if (contentType && (contentType.includes('image/') || contentType.includes('application/pdf'))) {
            // 图片或PDF，使用URL预览
            console.log('处理图片或PDF内容');
            const blob = await contentResponse.blob();
            const blobUrl = URL.createObjectURL(blob);
            console.log(`创建Blob URL: ${blobUrl}`);

            setPreviewingFile({
              fileName: file.displayName,
              originalName: file.originalName,
              url: blobUrl,
              loading: false,
              isProcessed: true
            });
            console.log('成功设置二进制内容预览');
            return;
          } else {
            // 未知内容类型，尝试作为文本处理
            console.warn(`未知内容类型: ${contentType}, 尝试作为文本处理`);
            const textContent = await contentResponse.text();

            // 检查是否是HTML内容
            if (textContent.trim().startsWith('<!DOCTYPE html>') || textContent.trim().startsWith('<html')) {
              console.warn('收到HTML内容而非预期的文件内容，可能是错误页面');
              throw new Error('服务器返回了HTML页面而非文件内容');
            }

            setPreviewingFile({
              fileName: file.displayName,
              originalName: file.originalName,
              content: textContent,
              loading: false,
              isProcessed: true
            });
            return;
          }
        } else {
          console.warn(`内容响应错误: ${contentResponse.status}`);
          throw new Error(`获取处理后的内容失败: ${contentResponse.status}`);
        }
      } catch (contentErr) {
        console.warn('获取处理后的内容失败，尝试直接预览原始文件:', contentErr);
      }

      // 2. 如果处理后的内容无法获取或预览，尝试直接预览原始文件
      const previewFilename = file.originalName || file.displayName;
      if (!previewFilename) {
        throw new Error('文件名信息丢失，无法预览文件');
      }
      const downloadUrl = `${apiUrl}/api/file/projects/${projectId}/files/download/${encodeURIComponent(previewFilename)}?preview=true&t=${Date.now()}`;
      console.log(`尝试直接预览原始文件: ${downloadUrl}`);

      // 对于PDF和图片，直接使用URL预览
      if (file.displayName.match(/\.(pdf|jpg|jpeg|png|gif)$/i)) {
        setPreviewingFile({
          fileName: file.displayName,
          originalName: file.originalName,
          url: downloadUrl,
          loading: false,
          isProcessed: false
        });
        console.log('设置直接预览URL');
        return;
      }

      // 对于其他类型文件，尝试获取内容
      const token = localStorage.getItem('lumidoc_token');
      const headers: Record<string, string> = {
        'Accept': 'application/json',
        'Cache-Control': 'no-cache, no-store'
      };

      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const fileResponse = await fetch(downloadUrl, { headers });
      console.log(`原始文件响应状态: ${fileResponse.status}, 内容类型: ${fileResponse.headers.get('content-type')}`);

      if (!fileResponse.ok) {
        throw new Error("获取文件内容失败");
      }

      const fileType = fileResponse.headers.get('content-type');

      if (fileType && (fileType.includes('text/') || fileType.includes('application/json'))) {
        // 文本内容
        const textContent = await fileResponse.text();

        // 检查是否是HTML内容
        if (textContent.trim().startsWith('<!DOCTYPE html>') || textContent.trim().startsWith('<html')) {
          console.warn('收到HTML内容而非预期的文件内容，可能是错误页面');
          throw new Error('服务器返回了HTML页面而非文件内容');
        }

        setPreviewingFile({
          fileName: file.displayName,
          originalName: file.originalName,
          content: textContent,
          loading: false,
          isProcessed: false
        });
        console.log('成功设置原始文本内容预览');
      } else {
        // 二进制内容，使用URL
        setPreviewingFile({
          fileName: file.displayName,
          originalName: file.originalName,
          url: downloadUrl,
          loading: false,
          isProcessed: false
        });
        console.log('成功设置原始文件URL预览');
      }
    } catch (err) {
      console.error('预览文件失败:', err);
      setPreviewingFile({
        fileName: file.displayName,
        originalName: file.originalName,
        loading: false,
        error: err instanceof Error
          ? err.message
          : '预览失败，请稍后再试'
      });
      toast.error(`预览失败: ${err instanceof Error ? err.message : '文件内容不可用'}`);
    }
  };

  // 文件下载处理函数
  const handleDownload = (file: FileItem) => {
    if (!projectId) return;

    if (!isFileActionable(file)) {
      toast.error('此文件处理失败，无法下载');
      return;
    }

    // 文件处理中或等待处理时给予提示，但仍允许尝试下载
    if (file.status === FileStatus.PENDING || file.status === FileStatus.PROCESSING) {
      toast.warning('文件正在处理中，下载内容可能不完整');
    }

    handleDownloadFile(file);
  };

  // 删除文件处理函数，支持FilePreview或文件对象
  const handleDeleteFile = async (file: { originalName: string, fileName?: string, displayName?: string, fileHash?: string }) => {
    if (!projectId) return;

    // 确定显示名称
    const displayName = file.displayName || file.fileName || file.originalName;

    if (!confirm(`确定要删除文件 "${displayName}" 吗？此操作不可恢复。`)) {
      return;
    }

    try {
      // 优先使用文件哈希进行删除，如果没有哈希则使用原始文件名
      const fileIdentifier = file.fileHash || file.originalName;
      await fileApi.deleteFile(projectId, fileIdentifier);
      toast.success(`文件已删除: ${displayName}`);

      // 从选中文件列表中移除被删除的文件
      setSelectedFiles(prev => prev.filter(f => getFileUniqueId(f) !== getFileUniqueId(file)));

      // 刷新文件列表
      refreshFiles();
      // 如果正在预览该文件，关闭预览
      if (previewingFile?.originalName === file.originalName) {
        setPreviewingFile(null);
      }
    } catch (err) {
      console.error('删除文件失败:', err);
      toast.error(`删除文件失败: ${err instanceof Error ? err.message : '未知错误'}`);
    }
  };

  // 删除文件 - 适配器函数
  const handleDelete = async (file: FileItem) => {
    if (!projectId || !isFileActionable(file)) {
      toast.warning('文件尚未处理完成，无法删除');
      return;
    }

    // 根据文件类型显示不同的确认信息
    const actionText = currentFileType === 'rag' ? '从知识库移除' : '删除';
    const warningText = currentFileType === 'rag'
      ? '此操作将从知识库中移除该文件，但不会删除原始文件。'
      : '此操作不可恢复。';

    if (!confirm(`确定要${actionText}文件 "${file.displayName}" 吗？${warningText}`)) {
      return;
    }

    try {
      console.log(`${actionText}文件: ${file.displayName}, 文件类型: ${currentFileType}`);
      // 显示加载中提示
      const loadingToastId = toast.loading(`正在${actionText}文件: ${file.displayName}...`);

      let result;

      if (currentFileType === 'rag') {
        // RAG文件：从知识库移除
        console.log(`从知识库移除文件: ${file.originalName}`);
        result = await ragApi.deleteRagFile(projectId, file.originalName);
      } else {
        // 普通文件：物理删除
        // 优先使用文件哈希进行删除，如果没有哈希则使用原始文件名
        const fileIdentifier = file.fileHash || file.originalName;
        console.log(`物理删除文件: ${fileIdentifier}`);
        result = await fileApi.deleteFile(projectId, fileIdentifier);
      }

      console.log("删除结果:", result);

      // 关闭加载提示
      toast.dismiss(loadingToastId);

      if (result && result.success) {
        // 显示成功消息和详细信息
        if (currentFileType === 'rag' && 'deleted_relations' in result) {
          // 类型保护：确保这是RAG删除响应
          const ragResult = result as { deleted_relations?: number; cleaned_entities?: number };
          const deletedRelations = ragResult.deleted_relations ?? 0;
          const cleanedEntities = ragResult.cleaned_entities ?? 0;
          toast.success(
            `文件已从知识库移除: ${file.displayName}` +
            (deletedRelations > 0 ? `\n删除了 ${deletedRelations} 个关系` : '') +
            (cleanedEntities > 0 ? `\n清理了 ${cleanedEntities} 个实体` : '')
          );
        } else {
          toast.success(`文件已${actionText}: ${file.displayName}`);
        }

        // 从选中文件列表中移除被删除的文件
        setSelectedFiles(prev => prev.filter(f => getFileUniqueId(f) !== getFileUniqueId(file)));

        // 刷新文件列表
        await refreshFiles();

        // 如果正在预览该文件，关闭预览
        if (previewingFile?.originalName === file.originalName) {
          setPreviewingFile(null);
        }
      } else {
        // 删除失败
        toast.error(`${actionText}失败: ${result?.message || '未知错误'}`);
      }
    } catch (err) {
      // 详细记录错误
      console.error(`${actionText}文件失败:`, err);
      const errorMessage = err instanceof Error ? err.message : '未知错误';
      console.error('错误详情:', errorMessage);

      // 显示错误消息
      toast.error(`${actionText}文件失败: ${errorMessage}`);
    }
  };

  // 关闭文件预览
  const closePreview = () => {
    setPreviewingFile(null);
  };

  // 手动触发文件处理
  const handleProcessFile = async (file: FileItem) => {
    if (!projectId || !file.fileId) {
      toast.error('无法处理文件：缺少项目ID或文件ID');
      return;
    }

    try {
      setLoading(true);
      toast.loading(`正在提交文件处理请求: ${file.displayName}`);

      // 调用处理API
      const response = await fileApi.processFile(projectId, file.fileId);

      if (response && response.success) {
        toast.success(`文件处理请求已提交: ${file.displayName}`);

        // 更新本地文件状态
        setFiles(prev => prev.map(f =>
          f.fileId === file.fileId
            ? { ...f, status: FileStatus.PROCESSING }
            : f
        ));

        // 立即刷新文件列表
        await refreshFiles();
      } else {
        toast.error(`提交处理请求失败: ${response?.message || '未知错误'}`);
      }
    } catch (error) {
      console.error('处理文件失败:', error);
      toast.error(`处理文件失败: ${error instanceof Error ? error.message : '未知错误'}`);
    } finally {
      setLoading(false);
    }
  };


  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
        <span className="ml-3 text-gray-400">加载中...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-red-400 bg-red-900 bg-opacity-20 rounded-md flex flex-col items-center justify-center h-64">
        <p>{error}</p>
        {currentFileType === 'rag' && !ragServiceAvailable && (
          <div className="mt-4">
            <button
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              onClick={() => {
                setRagServiceAvailable(true);
                setErrorCount(0);
                setError(null);
                toast.info('正在重新连接RAG知识库服务...');
              }}
            >
              重试连接
            </button>
          </div>
        )}
      </div>
    );
  }

  if (files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400">
        <p>暂无{currentFileType === 'regular' ? '上传' : 'RAG'}文件</p>
        {currentFileType === 'regular' && (
          <p className="mt-2">请先上传文件</p>
        )}
        {currentFileType === 'rag' && (
          <p className="mt-2">请先从文件管理导入文件到知识库</p>
        )}
      </div>
    );
  }

  return (
    <div className="overflow-auto h-full flex" data-file-list>
      {/* 文件列表区域 */}
      <div className={`${previewingFile ? 'w-1/2 pr-4' : 'w-full'} overflow-auto`}>

        {/* RAG文件类型的导入功能区域 */}
        {currentFileType === 'rag' && (
          <div className={`mb-6 rounded-lg p-4 ${
            isDarkMode ? 'bg-gray-800' : 'bg-gray-100'
          }`}>
            <div className="flex justify-between items-center mb-4">
              <h3 className={`text-lg font-semibold ${
                isDarkMode ? 'text-white' : 'text-gray-900'
              }`}>导入文件到知识库</h3>
              <button
                onClick={refreshFiles}
                className={`px-3 py-1.5 rounded text-sm flex items-center transition-colors ${
                  isDarkMode
                    ? 'bg-gray-600 text-white hover:bg-gray-700'
                    : 'bg-gray-200 text-gray-900 hover:bg-gray-300'
                }`}
              >
                <RefreshCw size={14} className="mr-1" />
                刷新
              </button>
            </div>
            <p className={`text-sm mb-3 ${
              isDarkMode ? 'text-gray-400' : 'text-gray-600'
            }`}>
              从"已上传文件"标签页选择文件并导入到知识库，或者在此查看已索引的文件。
            </p>
            <div className="flex items-center space-x-2 text-sm">
              <span className={`px-2 py-1 rounded text-xs ${
                isDarkMode ? 'bg-green-900 text-green-300' : 'bg-green-100 text-green-800'
              }`}>
                ✓ 已索引
              </span>
              <span className={isDarkMode ? 'text-gray-400' : 'text-gray-600'}>= 文件已添加到知识库并可用于查询</span>
            </div>
          </div>
        )}

        {/* 批量操作按钮 - 根据文件类型调整 */}
        {canEdit && selectedFiles.length > 0 && (
          <div className="mb-4 flex items-center gap-2 bg-gray-800 p-3 rounded-md">
            <span className="text-sm text-gray-400">已选择 {selectedFiles.length} 个文件</span>
            <div className="flex-1"></div>
            {currentFileType === 'regular' && (
              <button
                className="px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700 flex items-center"
                onClick={() => {
                  if (confirm(`确定要删除选中的 ${selectedFiles.length} 个文件吗？此操作不可恢复。`)) {
                    const deleteFiles = async () => {
                      // 显示批量删除进行中的提示
                      const loadingToastId = toast.loading(`正在删除 ${selectedFiles.length} 个文件...`);

                      try {
                        // 提取所有选中文件的哈希值并确保非空
                        const fileHashes: string[] = selectedFiles
                          .map(file => getFileUniqueId(file))
                          .filter((hash): hash is string => !!hash); // 类型保护确保所有值都是非空字符串

                        if (fileHashes.length === 0) {
                          // 如果没有有效的文件哈希，回退到逐个删除
                          toast.warning('无法使用批量删除，将逐个处理文件');
                          let successCount = 0;
                          let errorCount = 0;

                          for (const file of selectedFiles) {
                            try {
                              const result = await fileApi.deleteFile(projectId!, file.originalName);
                              if (result && result.success) {
                                successCount++;
                              } else {
                                errorCount++;
                              }
                            } catch (err) {
                              console.error(`删除文件 ${getFileUniqueId(file)} 失败:`, err);
                              errorCount++;
                            }
                          }

                          // 关闭加载提示
                          toast.dismiss(loadingToastId);

                          if (successCount > 0) {
                            toast.success(`成功删除 ${successCount} 个文件`);
                          }

                          if (errorCount > 0) {
                            toast.error(`${errorCount} 个文件删除失败`);
                          }
                        } else {
                          // 使用批量删除API
                          const result = await fileApi.batchDeleteFiles(projectId!, fileHashes);

                          // 关闭加载提示
                          toast.dismiss(loadingToastId);

                          if (result && result.success) {
                            const deletedCount = result.data?.deleted?.length || 0;
                            const failedCount = result.data?.failed?.length || 0;

                            if (deletedCount > 0) {
                              toast.success(`成功删除 ${deletedCount} 个文件`);
                            }

                            if (failedCount > 0) {
                              toast.error(`${failedCount} 个文件删除失败`);
                            }
                          } else {
                            toast.error(`批量删除失败: ${result?.message || '未知错误'}`);
                          }
                        }
                      } catch (err) {
                        // 关闭加载提示
                        toast.dismiss(loadingToastId);
                        console.error('批量删除文件失败:', err);
                        toast.error(`批量删除失败: ${err instanceof Error ? err.message : '未知错误'}`);
                      }

                      // 刷新文件列表
                      await refreshFiles();
                      // 清空选择
                      setSelectedFiles([]);
                      // 如果正在预览被删除的文件，关闭预览
                      if (previewingFile && selectedFiles.some(f => getFileUniqueId(f) === getFileUniqueId(previewingFile))) {
                        setPreviewingFile(null);
                      }
                    };

                    deleteFiles();
                  }
                }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                批量删除
              </button>
            )}
            {currentFileType === 'rag' && (
              <button
                className="px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700 flex items-center"
                onClick={() => {
                  if (confirm(`确定要从知识库移除选中的 ${selectedFiles.length} 个文件吗？此操作不会删除原始文件。`)) {
                    const deleteFiles = async () => {
                      // 显示批量移除进行中的提示
                      const loadingToastId = toast.loading(`正在从知识库移除 ${selectedFiles.length} 个文件...`);

                      try {
                        let successCount = 0;
                        let errorCount = 0;
                        let totalRelations = 0;
                        let totalEntities = 0;

                        for (const file of selectedFiles) {
                          try {
                            const result = await ragApi.deleteRagFile(projectId!, file.originalName);
                            if (result && result.success) {
                              successCount++;
                              if ('deleted_relations' in result) {
                                const ragResult = result as { deleted_relations?: number; cleaned_entities?: number };
                                totalRelations += ragResult.deleted_relations || 0;
                                totalEntities += ragResult.cleaned_entities || 0;
                              }
                            } else {
                              errorCount++;
                            }
                          } catch (err) {
                            console.error(`从知识库移除文件 ${file.originalName} 失败:`, err);
                            errorCount++;
                          }
                        }

                        // 关闭加载提示
                        toast.dismiss(loadingToastId);

                        if (successCount > 0) {
                          toast.success(
                            `成功从知识库移除 ${successCount} 个文件` +
                            (totalRelations > 0 ? `\n删除了 ${totalRelations} 个关系` : '') +
                            (totalEntities > 0 ? `\n清理了 ${totalEntities} 个实体` : '')
                          );
                        }

                        if (errorCount > 0) {
                          toast.error(`${errorCount} 个文件移除失败`);
                        }
                      } catch (err) {
                        // 关闭加载提示
                        toast.dismiss(loadingToastId);
                        console.error('批量移除文件失败:', err);
                        toast.error(`批量移除失败: ${err instanceof Error ? err.message : '未知错误'}`);
                      }

                      // 刷新文件列表
                      await refreshFiles();
                      // 清空选择
                      setSelectedFiles([]);
                      // 如果正在预览被删除的文件，关闭预览
                      if (previewingFile && selectedFiles.some(f => getFileUniqueId(f) === getFileUniqueId(previewingFile))) {
                        setPreviewingFile(null);
                      }
                    };

                    deleteFiles();
                  }
                }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                批量移除
              </button>
            )}
            {currentFileType === 'regular' && (
              <button
                className={`px-3 py-1.5 text-sm rounded ${
                  isImporting || selectedFiles.length === 0
                    ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                    : 'bg-green-600 text-white hover:bg-green-700'
                }`}
                onClick={handleImport}
                disabled={isImporting || selectedFiles.length === 0}
              >
                {isImporting ? '导入中...' : '导入到知识库'}
              </button>
            )}
          </div>
        )}

        <table className={`min-w-full border text-sm rounded-lg overflow-hidden shadow ${
          isDarkMode
            ? 'border-gray-700 bg-gray-900 text-white'
            : 'border-gray-300 bg-white text-gray-900'
        }`}>
          <thead>
            <tr className={`border-b ${
              isDarkMode
                ? 'bg-gray-800 text-white border-gray-700'
                : 'bg-gray-50 text-gray-900 border-gray-300'
            }`}>
              {canEdit && (
                <th className={`py-2 px-4 border-b w-[40px] text-center ${
                  isDarkMode ? 'border-gray-700' : 'border-gray-300'
                }`}>
                  <input
                    type="checkbox"
                    checked={selectedFiles.length === files.length && files.length > 0}
                    onChange={handleSelectAll}
                    className="accent-blue-500 bg-gray-700 border-gray-500 rounded"
                  />
                </th>
              )}
              <th className={`py-2 px-4 border-b text-left w-[60%] ${
                isDarkMode ? 'border-gray-700' : 'border-gray-300'
              }`}>文件名</th>
              {currentFileType === 'rag' && (
                <th className={`py-2 px-4 border-b text-center w-[80px] ${
                  isDarkMode ? 'border-gray-700' : 'border-gray-300'
                }`}>状态</th>
              )}
              <th className={`py-2 px-4 border-b text-center w-[120px] ${
                isDarkMode ? 'border-gray-700' : 'border-gray-300'
              }`}>操作</th>
            </tr>
          </thead>
          <tbody className={isDarkMode ? 'bg-gray-900' : 'bg-white'}>
            {files.map((file, index) => (
              <tr
                key={`${getFileUniqueId(file)}-${index}`}
                className={`border-b ${
                  isDarkMode ? 'border-gray-700' : 'border-gray-300'
                } ${
                  isFileSelected(file)
                    ? isDarkMode ? 'bg-blue-900/30' : 'bg-blue-100'
                    : isDarkMode ? 'hover:bg-gray-800' : 'hover:bg-gray-50'
                }`}
              >
                {/* 选择框 - 改进版：防止重复导入 */}
                {canEdit && (
                  <td className="py-3 text-center">
                    <input
                      type="checkbox"
                      checked={isFileSelected(file)}
                      onChange={() => handleSelect(file)}
                      disabled={currentFileType === 'regular' && isFileInRag(file)}
                      className={`rounded border-gray-500 bg-gray-700 text-blue-600 focus:ring-blue-500 ${
                        currentFileType === 'regular' && isFileInRag(file)
                          ? 'opacity-50 cursor-not-allowed'
                          : ''
                      }`}
                      title={
                        currentFileType === 'regular' && isFileInRag(file)
                          ? '该文件已在知识库中'
                          : '选择此文件'
                      }
                    />
                    {currentFileType === 'regular' && isFileInRag(file) && (
                      <div className="mt-1 text-xs text-green-400">已导入</div>
                    )}
                  </td>
                )}

                {/* 文件名 */}
                <td className="px-3 py-3 truncate">
                  <div className="flex items-center">
                    <div className="w-full">
                      <div className="flex items-center">
                        <FileTypeIcon type={file.contentType || file.fileType || 'unknown'} />
                        <span className="ml-2 text-sm font-medium text-white truncate">
                          {file.displayName || file.originalName || '未命名文件'}
                        </span>
                      </div>
                      <div className="flex items-center text-xs text-gray-300 mt-1">
                        {file.size && (
                          <span className="mr-2">{formatFileSize(file.size)}</span>
                        )}
                        {file.createdAt && (
                          <span>{formatDate(file.createdAt)}</span>
                        )}
                        {currentFileType === 'regular' && (
                          <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${getStatusClassName(file)}`}>
                            {getStatusText(file)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </td>

                {/* RAG文件状态列 - 改进版 */}
                {currentFileType === 'rag' && (
                  <td className="py-3 px-4 text-center">
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getStatusClassName(file)}`}>
                      {getStatusText(file)}
                    </span>
                    {file.errorMessage && (
                      <div className="mt-1 text-xs text-red-400" title={file.errorMessage}>
                        {file.errorMessage.length > 20 ? `${file.errorMessage.substring(0, 20)}...` : file.errorMessage}
                      </div>
                    )}
                  </td>
                )}

                {/* 操作按钮 */}
                <td className="px-3 py-3 text-center whitespace-nowrap">
                  <div className="flex space-x-3 justify-center">
                    {/* 预览按钮 */}
                    <button
                      onClick={() => handlePreview(file)}
                      disabled={!isFileActionable(file)}
                      className={`text-blue-400 hover:text-blue-300 ${!isFileActionable(file) ? 'opacity-50 cursor-not-allowed' : ''}`}
                      title="预览文件"
                    >
                      <Eye size={18} />
                    </button>

                    {/* 下载按钮 */}
                    <button
                      onClick={() => handleDownload(file)}
                      disabled={!isFileActionable(file)}
                      className={`text-green-400 hover:text-green-300 ${!isFileActionable(file) ? 'opacity-50 cursor-not-allowed' : ''}`}
                      title="下载文件"
                    >
                      <Download size={18} />
                    </button>

                    {/* 普通文件的处理按钮 */}
                    {currentFileType === 'regular' && (file.status === FileStatus.PENDING || file.status === FileStatus.UPLOADED || file.status === FileStatus.FAILED) && (
                      <button
                        onClick={() => handleProcessFile(file)}
                        className="text-yellow-400 hover:text-yellow-300"
                        title="处理文件"
                      >
                        <RefreshCw size={18} />
                      </button>
                    )}

                    {/* 删除按钮 - 根据文件类型显示不同文本 */}
                    <button
                      onClick={() => handleDelete(file)}
                      className="text-red-400 hover:text-red-300"
                      title={currentFileType === 'rag' ? '从知识库移除' : '删除文件'}
                    >
                      <Trash size={18} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 文件预览区域保持不变 */}
      {previewingFile && (
        <div className="w-1/2 pl-4 border-l border-gray-700 overflow-auto h-full max-h-[90vh]">
          <div className="bg-gray-800 rounded-lg p-4 h-full flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold text-lg">{previewingFile.fileName}</h3>
              <button
                className="text-gray-400 hover:text-white"
                onClick={closePreview}
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="flex-grow overflow-auto bg-gray-900 rounded p-3 max-h-[70vh]">
              {previewingFile.loading ? (
                <div className="flex items-center justify-center h-full">
                  <Spinner size="md" />
                  <span className="ml-2">加载中...</span>
                </div>
              ) : previewingFile.error ? (
                <div className="text-red-400 p-3">
                  {previewingFile.error}
                </div>
              ) : previewingFile.url ? (
                previewingFile.fileName.match(/\.(jpg|jpeg|png|gif)$/i) ? (
                  <img
                    src={previewingFile.url}
                    alt={previewingFile.fileName}
                    className="max-w-full max-h-[70vh] mx-auto"
                  />
                ) : (
                  <div className="w-full h-full flex justify-center items-center">
                    <div className="relative w-full h-[60vh] overflow-hidden border border-gray-700 rounded">
                      {/* 使用iframe嵌入PDF，通过查询参数传递认证令牌 */}
                      <iframe
                        src={`${previewingFile.url}&v=${new Date().getTime()}&token=${localStorage.getItem('lumidoc_token') || ''}`}
                        className="absolute inset-0 w-full h-full max-w-full max-h-[70vh]"
                        style={{ border: 'none' }}
                        title={previewingFile.fileName}
                        allowFullScreen
                      >
                        <p className="p-4 text-center">
                          您的浏览器不支持嵌入式PDF预览。
                          <button
                            className="text-blue-500 underline mx-1"
                            onClick={() => handleDownloadFile(previewingFile)}
                          >
                            点击此处下载文件
                          </button>
                        </p>
                      </iframe>
                    </div>
                  </div>
                )
              ) : previewingFile.content ? (
                <div className="markdown-preview overflow-auto">
                  <div className="whitespace-pre-wrap text-sm text-gray-300 p-4 font-mono">
                    {previewingFile.content.split('\n').map((line, i) => (
                      <div key={i} className="mb-1">
                        {line || '\u00A0'}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-gray-400">
                  <p>无法预览此文件类型或文件内容为空</p>
                </div>
              )}
            </div>

            <div className="mt-4 flex justify-end">
              <button
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 mr-2"
                onClick={() => previewingFile && handleDownloadFile(previewingFile)}
              >
                下载
              </button>
              {currentFileType === 'regular' && canEdit && (
                <button
                  className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
                  onClick={() => previewingFile && handleDeleteFile(previewingFile)}
                >
                  删除
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FilesList;
