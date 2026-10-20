import { FileRecoveryStatus } from '@/features/files/components/FileRecoveryStatus';
import React, { useState, useCallback, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useProjects } from '@/context/ProjectContext';
import { fileApi, type FileInfo } from '@/api/file';
import {
  Upload,
  FileText,
  Image,
  File,
  X,
  CheckCircle,
  AlertCircle,
  Clock,
  Eye,
  Download,
  Search,
  Trash2,
  Zap,
  Brain,
  BarChart3,
  PieChart,
  TrendingUp,
  Tag,
  Share2,
  RefreshCw
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useTheme } from '@/context/ThemeContext';
import { useLanguage } from '@/context/LanguageContext';

interface DocumentFile {
  id: string;
  name: string;
  type: 'pdf' | 'docx' | 'txt' | 'image' | 'xlsx' | 'pptx';
  size: number;
  uploadTime: Date;
  status: 'uploading' | 'processing' | 'completed' | 'error';
  progress?: number;
  ocrResult?: {
    text: string;
    confidence: number;
    language: string;
    pageCount?: number;
  };
  analysis?: {
    summary: string;
    keyPoints: string[];
    entities: { name: string; type: string; count: number }[];
    sentiment: 'positive' | 'neutral' | 'negative';
    topics: string[];
    readingTime: number;
  };
  preview?: string;
}

interface AnalysisStats {
  totalDocuments: number;
  processedToday: number;
  averageProcessingTime: number | null;
  successRate: number | null;
  totalSize: number;
  languages: { [key: string]: number };
  documentTypes: { [key: string]: number };
}

const DOCUMENT_TYPES = new Set<DocumentFile['type']>([
  'pdf',
  'docx',
  'txt',
  'image',
  'xlsx',
  'pptx'
]);

function getDocumentType(filename: string): DocumentFile['type'] {
  const extension = filename.split('.').pop()?.toLowerCase();
  if (extension && ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(extension)) return 'image';
  if (extension === 'doc') return 'docx';
  if (extension === 'xls') return 'xlsx';
  if (extension === 'ppt') return 'pptx';
  return extension && DOCUMENT_TYPES.has(extension as DocumentFile['type'])
    ? extension as DocumentFile['type']
    : 'txt';
}

export function DocumentAnalysis() {
  // 获取当前主题和语言
  const { isDarkMode } = useTheme();
  const { currentLanguage, t } = useLanguage();

  const { projectId: routeProjectId } = useParams<{ projectId: string }>();
  const { projects, loading: projectsLoading } = useProjects();
  const projectId = routeProjectId || projects[0]?.id;
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sharedFile = searchParams.get('file');
  const activeProject = useRef<string | undefined>(projectId);
  activeProject.current = projectId;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [preview, setPreview] = useState<{ text: string } | null>(null);
  const [shareLink, setShareLink] = useState('');

  const [documents, setDocuments] = useState<DocumentFile[]>([]);

  const [selectedDocument, setSelectedDocument] = useState<DocumentFile | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'completed' | 'processing' | 'error'>('all');
  const [dragActive, setDragActive] = useState(false);

  const loadDocuments = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const files = await fileApi.listFiles(projectId);
      if (activeProject.current !== projectId) return;
      const records = files.map((file: FileInfo): DocumentFile => ({
        id: file.file_hash,
        name: file.display_name || file.filename,
        type: getDocumentType(file.filename),
        size: file.size,
        uploadTime: new Date(file.created_at),
        status: ['completed', 'processed', 'imported'].includes(file.status || '')
          ? 'completed' : ['failed', 'error'].includes(file.status || '') ? 'error' : 'processing',
      }));
      setDocuments(records);
      setSelectedDocument(previous => records.find(doc => doc.id === (sharedFile || previous?.id)) || null);
      setError(null);
    } catch (err) {
      if (activeProject.current === projectId) setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      if (activeProject.current === projectId) setLoading(false);
    }
  }, [projectId, sharedFile]);

  useEffect(() => {
    setDocuments([]);
    setSelectedDocument(null);
    setPreview(null);
    setShareLink('');
    activeProject.current = projectId;
    void loadDocuments();
    return () => { activeProject.current = undefined; };
  }, [loadDocuments, projectId]);

  useEffect(() => {
    if (!documents.some(doc => doc.status === 'processing')) return;
    const timer = setInterval(() => void loadDocuments(), 3000);
    return () => clearInterval(timer);
  }, [documents, loadDocuments]);

  useEffect(() => {
    const refresh = (event: Event) => {
      if ((event as CustomEvent).detail?.projectId === projectId) void loadDocuments();
    };
    window.addEventListener('file-operations-updated', refresh);
    return () => window.removeEventListener('file-operations-updated', refresh);
  }, [projectId, loadDocuments]);

  const handleDelete = async (doc: DocumentFile) => {
    if (!projectId || deletingId) return;
    const confirmed = window.confirm(currentLanguage === 'zh-CN'
      ? `确定从当前项目删除“${doc.name}”吗？`
      : `Delete “${doc.name}” from this project?`);
    if (!confirmed) return;
    setDeletingId(doc.id);
    setError(null);
    try {
      const result = await fileApi.deleteFile(projectId, doc.id);
      if (!result.success) throw new Error(result.message || (currentLanguage === 'zh-CN' ? '删除失败，请重试' : 'Deletion failed. Please retry.'));
      if (activeProject.current !== projectId) return;
      if (selectedDocument?.id === doc.id) {
        setSelectedDocument(null);
        setPreview(null);
        setShareLink('');
      }
      await loadDocuments();
    } catch (error) {
      if (activeProject.current === projectId) setError(error instanceof Error ? error.message : 'Deletion failed');
    } finally {
      setDeletingId(null);
    }
  };

  const handleDocumentAction = async (action: 'preview' | 'download' | 'share') => {
    if (!selectedDocument || !projectId) return;
    setError(null);
    try {
      if (action === 'share') {
        const link = new URL(`/project/${projectId}/documents`, window.location.origin);
        link.searchParams.set('file', selectedDocument.id);
        setShareLink(link.toString());
        // 链接不包含凭据，接收者仍需登录并具备项目权限。
        await navigator.clipboard?.writeText(link.toString()).catch(() => undefined);
      } else {
        const text = await fileApi.getFileContent(projectId, selectedDocument.id);
        if (activeProject.current !== projectId) return;
        if (action === 'preview') setPreview({ text });
        else {
          const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `${selectedDocument.name.replace(/\.[^.]+$/, '')}.processed.md`;
          link.click();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
        }
      }
    } catch {
      setError(currentLanguage === 'zh-CN'
        ? '处理结果暂不可用，请等待 OCR/文档处理完成；处理失败的文件请重新上传。'
        : 'Processed content is unavailable. Wait for OCR/document processing to finish, or re-upload failed files.');
    }
  };

  const stats: AnalysisStats = {
    totalDocuments: documents.length,
    processedToday: documents.filter(doc =>
      doc.status === 'completed'
      && doc.uploadTime > new Date(Date.now() - 24 * 60 * 60 * 1000)
    ).length,
    averageProcessingTime: null,
    successRate: documents.some(doc => doc.status === 'completed' || doc.status === 'error')
      ? Math.round((documents.filter(doc => doc.status === 'completed').length
        / documents.filter(doc => doc.status === 'completed' || doc.status === 'error').length) * 1000) / 10
      : null,
    totalSize: documents.reduce((sum, doc) => sum + doc.size, 0),
    languages: documents.reduce<Record<string, number>>((counts, doc) => {
      const language = doc.ocrResult?.language;
      if (language) counts[language] = (counts[language] || 0) + 1;
      return counts;
    }, {}),
    documentTypes: documents.reduce<Record<string, number>>((counts, doc) => {
      counts[doc.type] = (counts[doc.type] || 0) + 1;
      return counts;
    }, {})
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'processing':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getFileIcon = (type: string) => {
    switch (type) {
      case 'pdf':
        return <FileText className="w-5 h-5 text-red-500" />;
      case 'docx':
        return <FileText className="w-5 h-5 text-blue-500" />;
      case 'xlsx':
        return <BarChart3 className="w-5 h-5 text-green-500" />;
      case 'pptx':
        return <PieChart className="w-5 h-5 text-orange-500" />;
      case 'image':
        return <Image className="w-5 h-5 text-purple-500" />;
      default:
        return <File className="w-5 h-5 text-gray-500" />;
    }
  };

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleFiles = async (files: FileList) => {
    if (!projectId || uploading) return;
    setUploading(true);
    setUploadProgress(0);
    setError(null);
    try {
      const result = await fileApi.uploadFiles(projectId, Array.from(files), progress => {
        setUploadProgress(progress.percentage);
      });
      await loadDocuments();
      const failures = result.files.filter(file => !file.success);
      if (!result.success || failures.length) {
        throw new Error(failures.map(file => file.message).join('; ') || 'Upload failed');
      }
    } catch (err) {
      if (activeProject.current === projectId) setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);
    if (event.dataTransfer.files.length) void handleFiles(event.dataTransfer.files);
  };

  const filteredDocuments = documents.filter(doc => {
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = filterStatus === 'all' || doc.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="mx-auto max-w-7xl space-y-8 p-4 sm:p-6">
        {projectId && <FileRecoveryStatus projectId={projectId} />}
        {/* 页面标题 */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{t('documentAnalysis')}</h1>
            <p className={`text-lg ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              {currentLanguage === 'zh-CN' ? 'OCR识别、智能分析、内容提取一站式服务' : 'One-stop service for OCR recognition, intelligent analysis, and content extraction'}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" onClick={() => void loadDocuments()} disabled={!projectId || loading} className={`${isDarkMode ? 'border-gray-600 text-gray-300 hover:bg-gray-700' : ''}`}>
              <RefreshCw className="w-4 h-4 mr-2" />
              {currentLanguage === 'zh-CN' ? '刷新状态' : 'Refresh Status'}
            </Button>
            <Button onClick={() => document.getElementById('file-input')?.click()} disabled={!projectId || uploading} className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0">
              <Upload className="w-4 h-4 mr-2" />
              {t('uploadDocument')}
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <label htmlFor="document-project">{currentLanguage === 'zh-CN' ? '项目' : 'Project'}</label>
          <select id="document-project" value={projectId || ''} onChange={event => navigate(`/project/${event.target.value}/documents`)} className="rounded border bg-background p-2">
            {!projectId && <option value="">{projectsLoading ? 'Loading...' : 'Select a project'}</option>}
            {projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
          {!projectId && !projectsLoading && <Button onClick={() => navigate('/app/projects')}>{currentLanguage === 'zh-CN' ? '创建项目后上传文件' : 'Create a project to upload files'}</Button>}
        </div>
        {error && <p role="alert" className="text-red-600">{error}</p>}
        {uploading && <p role="status">{currentLanguage === 'zh-CN' ? '正在上传' : 'Uploading'} {uploadProgress}%</p>}
        {loading && <p role="status">{currentLanguage === 'zh-CN' ? '正在读取文件' : 'Loading documents...'}</p>}

        {/* 统计概览 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className={`p-6 rounded-2xl border ${
            isDarkMode ? 'bg-[#2a2a2a] border-gray-700' : 'bg-white border-gray-200'
          }`}>
            <div className="flex items-center justify-between mb-4">
              <div className={`p-3 rounded-xl ${
                isDarkMode ? 'bg-blue-900/30' : 'bg-blue-100'
              }`}>
                <FileText className="w-6 h-6 text-blue-600" />
              </div>
              <span className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                {stats.totalDocuments}
              </span>
            </div>
            <h3 className={`text-lg font-semibold mb-1 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{t('totalDocuments')}</h3>
            <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              {currentLanguage === 'zh-CN' ? '累计处理文档' : 'Total processed documents'}
            </p>
          </div>

          <div className={`p-6 rounded-2xl border ${
            isDarkMode ? 'bg-[#2a2a2a] border-gray-700' : 'bg-white border-gray-200'
          }`}>
            <div className="flex items-center justify-between mb-4">
              <div className={`p-3 rounded-xl ${
                isDarkMode ? 'bg-green-900/30' : 'bg-green-100'
              }`}>
                <TrendingUp className="w-6 h-6 text-green-600" />
              </div>
              <span className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                {stats.processedToday}
              </span>
            </div>
            <h3 className={`text-lg font-semibold mb-1 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{currentLanguage === 'zh-CN' ? '今日处理' : 'Today Processed'}</h3>
            <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              {currentLanguage === 'zh-CN' ? '24小时内完成' : 'Completed in 24 hours'}
            </p>
          </div>

          <div className={`p-6 rounded-2xl border ${
            isDarkMode ? 'bg-[#2a2a2a] border-gray-700' : 'bg-white border-gray-200'
          }`}>
            <div className="flex items-center justify-between mb-4">
              <div className={`p-3 rounded-xl ${
                isDarkMode ? 'bg-purple-900/30' : 'bg-purple-100'
              }`}>
                <Zap className="w-6 h-6 text-purple-600" />
              </div>
              <span className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                {stats.averageProcessingTime === null ? '—' : `${stats.averageProcessingTime}s`}
              </span>
            </div>
            <h3 className={`text-lg font-semibold mb-1 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{t('averageProcessingTime')}</h3>
            <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              {currentLanguage === 'zh-CN' ? 'OCR + 分析' : 'OCR + Analysis'}
            </p>
          </div>

          <div className={`p-6 rounded-2xl border ${
            isDarkMode ? 'bg-[#2a2a2a] border-gray-700' : 'bg-white border-gray-200'
          }`}>
            <div className="flex items-center justify-between mb-4">
              <div className={`p-3 rounded-xl ${
                isDarkMode ? 'bg-orange-900/30' : 'bg-orange-100'
              }`}>
                <CheckCircle className="w-6 h-6 text-orange-600" />
              </div>
              <span className={`text-2xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                {stats.successRate === null ? '—' : `${stats.successRate}%`}
              </span>
            </div>
            <h3 className={`text-lg font-semibold mb-1 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{t('successRate')}</h3>
            <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              {currentLanguage === 'zh-CN' ? '处理成功率' : 'Processing success rate'}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* 左侧：文档上传和列表 */}
          <div className="lg:col-span-2 space-y-6">
            {/* 文档上传区 */}
            <div 
              className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all duration-300 ${
                dragActive 
                  ? isDarkMode 
                    ? 'border-blue-500 bg-blue-900/20' 
                    : 'border-blue-500 bg-blue-50'
                  : isDarkMode 
                    ? 'border-gray-600 hover:border-gray-500' 
                    : 'border-gray-300 hover:border-gray-400'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <Upload className={`w-12 h-12 mx-auto mb-4 ${
                dragActive ? 'text-blue-500' : isDarkMode ? 'text-gray-400' : 'text-gray-500'
              }`} />
              <h3 className={`text-lg font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                {dragActive 
                  ? (currentLanguage === 'zh-CN' ? '释放文件开始上传' : 'Release files to start upload')
                  : t('dropFilesHere')
                }
              </h3>
              <p className={`text-sm mb-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                {currentLanguage === 'zh-CN' 
                  ? '支持 PDF、Word、Excel、PowerPoint、图片等格式'
                  : 'Support PDF, Word, Excel, PowerPoint, images and other formats'
                }
              </p>
              <Button 
                className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0"
                onClick={() => document.getElementById('file-input')?.click()}
                disabled={!projectId || uploading}
              >
                <Upload className="w-4 h-4 mr-2" />
{currentLanguage === 'zh-CN' ? '选择文件' : 'Select Files'}
              </Button>
              <input
                id="file-input"
                type="file"
                multiple
                className="hidden"
                disabled={!projectId || uploading}
                onChange={event => { if (event.target.files) void handleFiles(event.target.files); event.target.value = ''; }}
                accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.gif"
              />
            </div>

            {/* 搜索和筛选 */}
            <div className={`p-6 rounded-2xl border ${
              isDarkMode ? 'bg-[#2a2a2a] border-gray-700' : 'bg-white border-gray-200'
            }`}>
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                  <Input
                    placeholder={currentLanguage === 'zh-CN' ? '搜索文档名称...' : 'Search documents...'}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Button 
                    variant={filterStatus === 'all' ? 'default' : 'outline'} 
                    size="sm"
                    onClick={() => setFilterStatus('all')}
                  >
{currentLanguage === 'zh-CN' ? '全部' : 'All'}
                  </Button>
                  <Button 
                    variant={filterStatus === 'completed' ? 'default' : 'outline'} 
                    size="sm"
                    onClick={() => setFilterStatus('completed')}
                  >
{currentLanguage === 'zh-CN' ? '已完成' : 'Completed'}
                  </Button>
                  <Button 
                    variant={filterStatus === 'processing' ? 'default' : 'outline'} 
                    size="sm"
                    onClick={() => setFilterStatus('processing')}
                  >
{currentLanguage === 'zh-CN' ? '处理中' : 'Processing'}
                  </Button>
                </div>
              </div>
            </div>

            {/* 文档列表 */}
            <div className={`rounded-2xl border ${
              isDarkMode ? 'bg-[#2a2a2a] border-gray-700' : 'bg-white border-gray-200'
            }`}>
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h2 className={`text-xl font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                  {currentLanguage === 'zh-CN' ? '文档列表' : 'Document List'}
                </h2>
                <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                  {currentLanguage === 'zh-CN' 
                    ? `共 ${filteredDocuments.length} 个文档`
                    : `${filteredDocuments.length} documents total`
                  }
                </p>
              </div>
              
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {filteredDocuments.length === 0 ? (
                  <div className="px-6 py-12 text-center" role="status">
                    <FileText className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
                    <h3 className="font-semibold text-foreground">{t('noDocuments')}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{t('uploadFirstDocument')}</p>
                  </div>
                ) : filteredDocuments.map((doc) => (
                  <div 
                    key={doc.id} 
                    className={`p-6 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors ${
                      selectedDocument?.id === doc.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                    }`}
                    onClick={() => setSelectedDocument(doc)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-4 flex-1">
                        {getFileIcon(doc.type)}
                        <div className="flex-1 min-w-0">
                          <h3 className="font-medium text-sm mb-1 truncate">{doc.name}</h3>
                          <div className="flex items-center space-x-4 text-xs text-gray-500">
                            <span>{formatFileSize(doc.size)}</span>
                            <span>{doc.uploadTime.toLocaleString()}</span>
                            {doc.ocrResult && (
                              <span>
                                {currentLanguage === 'zh-CN' ? '识别率' : 'Recognition'}: {doc.ocrResult.confidence}%
                              </span>
                            )}
                          </div>
                          
                          {doc.status === 'processing' && doc.progress && (
                            <div className="mt-2">
                              <div className="flex items-center justify-between text-xs mb-1">
                                <span>{currentLanguage === 'zh-CN' ? '处理进度' : 'Progress'}</span>
                                <span>{doc.progress}%</span>
                              </div>
                              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                                <div 
                                  className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                                  style={{ width: `${doc.progress}%` }}
                                />
                              </div>
                            </div>
                          )}
                          
                          {doc.analysis && (
                            <div className="mt-2">
                              <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} line-clamp-2`}>
                                {doc.analysis.summary}
                              </p>
                              <div className="flex items-center space-x-3 mt-1 text-xs">
                                <span className="flex items-center space-x-1">
                                  <Clock className="w-3 h-3" />
                                  <span>{doc.analysis.readingTime}{currentLanguage === 'zh-CN' ? '分钟' : ' min'}</span>
                                </span>
                                <span className="flex items-center space-x-1">
                                  <Tag className="w-3 h-3" />
                                  <span>{doc.analysis.topics.join(', ')}</span>
                                </span>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-3">
                        {getStatusIcon(doc.status)}
                        <Button variant="ghost" size="sm" className="p-1 text-red-600 hover:text-red-700"
                          disabled={deletingId !== null}
                          aria-label={currentLanguage === 'zh-CN' ? `删除 ${doc.name}` : `Delete ${doc.name}`}
                          title={currentLanguage === 'zh-CN' ? '删除文档' : 'Delete document'}
                          onClick={event => { event.stopPropagation(); void handleDelete(doc); }}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 右侧：详细分析结果 */}
          <div className="space-y-6">
            {selectedDocument ? (
              <>
                {/* 文档详情 */}
                <div className={`rounded-2xl border ${
                  isDarkMode ? 'bg-[#2a2a2a] border-gray-700' : 'bg-white border-gray-200'
                }`}>
                  <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                    <div className="flex items-center justify-between">
                      <h2 className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                        {currentLanguage === 'zh-CN' ? '文档详情' : 'Document Details'}
                      </h2>
                      <Button variant="ghost" size="sm" onClick={() => setSelectedDocument(null)}>
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                  
                  <div className="p-6 space-y-4">
                    <div className="flex items-center space-x-3">
                      {getFileIcon(selectedDocument.type)}
                      <div>
                        <h3 className="font-medium">{selectedDocument.name}</h3>
                        <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                          {formatFileSize(selectedDocument.size)} • {selectedDocument.uploadTime.toLocaleString()}
                        </p>
                      </div>
                    </div>
                    
                    {selectedDocument.ocrResult && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className={`text-sm font-medium ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                            {currentLanguage === 'zh-CN' ? 'OCR识别结果' : 'OCR Recognition Result'}
                          </span>
                          <span className="text-xs text-green-600">
                            {currentLanguage === 'zh-CN' ? '置信度' : 'Confidence'}: {selectedDocument.ocrResult.confidence}%
                          </span>
                        </div>
                        <div className={`p-3 rounded-lg text-xs ${
                          isDarkMode ? 'bg-gray-800' : 'bg-gray-100'
                        }`}>
                          {selectedDocument.ocrResult.text}
                        </div>
                        {selectedDocument.ocrResult.pageCount && (
                          <p className="text-xs text-gray-500">
                            {currentLanguage === 'zh-CN' 
                              ? `共 ${selectedDocument.ocrResult.pageCount} 页`
                              : `${selectedDocument.ocrResult.pageCount} pages total`
                            }
                          </p>
                        )}
                      </div>
                    )}
                    
                    <div className="flex items-center space-x-2">
                      <Button size="sm" variant="outline" onClick={() => void handleDocumentAction('preview')}>
                        <Eye className="w-4 h-4 mr-1" />
{currentLanguage === 'zh-CN' ? '预览' : 'Preview'}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => void handleDocumentAction('download')}>
                        <Download className="w-4 h-4 mr-1" />
{currentLanguage === 'zh-CN' ? '下载' : 'Download'}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => void handleDocumentAction('share')}>
                        <Share2 className="w-4 h-4 mr-1" />
{currentLanguage === 'zh-CN' ? '分享' : 'Share'}
                      </Button>
                    </div>
                  </div>
                </div>

                {shareLink && <div className="space-y-2"><p>{currentLanguage === 'zh-CN' ? '项目成员登录后可通过此链接查看文件' : 'Project members can open this link after signing in'}</p><Input aria-label="Share link" readOnly value={shareLink} /></div>}
                {preview && <section aria-label="Document preview" className="space-y-2">
                  <Button variant="outline" onClick={() => setPreview(null)}>{currentLanguage === 'zh-CN' ? '关闭预览' : 'Close preview'}</Button>
                  <h3 className="font-medium">{currentLanguage === 'zh-CN' ? '处理结果 / OCR 识别内容' : 'Processed document / OCR text'}</h3>
                  <div className="prose dark:prose-invert max-w-none max-h-[600px] overflow-auto break-words rounded border p-4">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{preview.text}</ReactMarkdown>
                  </div>
                </section>}

                {/* 智能分析结果 */}
                {selectedDocument.analysis && (
                  <div className={`rounded-2xl border ${
                    isDarkMode ? 'bg-[#2a2a2a] border-gray-700' : 'bg-white border-gray-200'
                  }`}>
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                      <div className="flex items-center space-x-2">
                        <Brain className="w-5 h-5 text-purple-500" />
                        <h2 className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                          {currentLanguage === 'zh-CN' ? '智能分析' : 'Intelligent Analysis'}
                        </h2>
                      </div>
                    </div>
                    
                    <div className="p-6 space-y-6">
                      {/* 摘要 */}
                      <div>
                        <h3 className={`text-sm font-medium mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                          {currentLanguage === 'zh-CN' ? '内容摘要' : 'Content Summary'}
                        </h3>
                        <p className={`text-sm ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>
                          {selectedDocument.analysis.summary}
                        </p>
                      </div>
                      
                      {/* 关键点 */}
                      <div>
                        <h3 className={`text-sm font-medium mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                          {currentLanguage === 'zh-CN' ? '关键要点' : 'Key Points'}
                        </h3>
                        <ul className="space-y-1">
                          {selectedDocument.analysis.keyPoints.map((point, index) => (
                            <li key={index} className={`text-sm flex items-start space-x-2 ${
                              isDarkMode ? 'text-gray-300' : 'text-gray-700'
                            }`}>
                              <span className="w-1.5 h-1.5 bg-blue-500 rounded-full mt-2 flex-shrink-0" />
                              <span>{point}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      
                      {/* 实体识别 */}
                      <div>
                        <h3 className={`text-sm font-medium mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                          {currentLanguage === 'zh-CN' ? '实体识别' : 'Entity Recognition'}
                        </h3>
                        <div className="space-y-2">
                          {selectedDocument.analysis.entities.map((entity, index) => (
                            <div key={index} className="flex items-center justify-between text-sm">
                              <div className="flex items-center space-x-2">
                                <span className={`px-2 py-1 rounded text-xs ${
                                  isDarkMode ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-700'
                                }`}>
                                  {entity.type}
                                </span>
                                <span>{entity.name}</span>
                              </div>
                              <span className="text-xs text-gray-500">
                                {entity.count}{currentLanguage === 'zh-CN' ? '次' : ' times'}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                      
                      {/* 情感分析和主题 */}
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <h3 className={`text-sm font-medium mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                            {currentLanguage === 'zh-CN' ? '情感倾向' : 'Sentiment'}
                          </h3>
                          <span className={`px-3 py-1 rounded-full text-xs ${
                            selectedDocument.analysis.sentiment === 'positive' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                            selectedDocument.analysis.sentiment === 'negative' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                            'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                          }`}>
                            {selectedDocument.analysis.sentiment === 'positive' 
                              ? (currentLanguage === 'zh-CN' ? '积极' : 'Positive')
                              : selectedDocument.analysis.sentiment === 'negative' 
                                ? (currentLanguage === 'zh-CN' ? '消极' : 'Negative')
                                : (currentLanguage === 'zh-CN' ? '中性' : 'Neutral')
                            }
                          </span>
                        </div>
                        <div>
                          <h3 className={`text-sm font-medium mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                            {currentLanguage === 'zh-CN' ? '阅读时间' : 'Reading Time'}
                          </h3>
                          <div className="flex items-center space-x-1 text-sm">
                            <Clock className="w-4 h-4 text-gray-400" />
                            <span>
                              {selectedDocument.analysis.readingTime} {currentLanguage === 'zh-CN' ? '分钟' : 'minutes'}
                            </span>
                          </div>
                        </div>
                      </div>
                      
                      {/* 主题标签 */}
                      <div>
                        <h3 className={`text-sm font-medium mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                          {currentLanguage === 'zh-CN' ? '主题标签' : 'Topic Tags'}
                        </h3>
                        <div className="flex flex-wrap gap-2">
                          {selectedDocument.analysis.topics.map((topic, index) => (
                            <span key={index} className={`px-2 py-1 rounded-full text-xs ${
                              isDarkMode ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-100 text-blue-700'
                            }`}>
                              {topic}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className={`rounded-2xl border ${
                isDarkMode ? 'bg-[#2a2a2a] border-gray-700' : 'bg-white border-gray-200'
              } p-8 text-center`}>
                <FileText className={`w-12 h-12 mx-auto mb-4 ${
                  isDarkMode ? 'text-gray-600' : 'text-gray-400'
                }`} />
                <h3 className={`text-lg font-semibold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                  {currentLanguage === 'zh-CN' ? '选择文档查看详情' : 'Select Document to View Details'}
                </h3>
                <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                  {currentLanguage === 'zh-CN'
                    ? '点击左侧文档列表中的任意文档查看详细分析结果'
                    : 'Click any document in the left list to view detailed analysis results'
                  }
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
