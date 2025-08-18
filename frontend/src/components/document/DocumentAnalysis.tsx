import React, { useState, useCallback } from 'react';
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
  MoreHorizontal,
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
import { detectBrowserLanguage, getTranslation } from '@/utils/language';
import { useTheme } from '@/context/ThemeContext';

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
  averageProcessingTime: number;
  successRate: number;
  totalSize: number;
  languages: { [key: string]: number };
  documentTypes: { [key: string]: number };
}

export function DocumentAnalysis() {
  // 获取当前主题和语言
  const { isDarkMode } = useTheme();
  const currentLanguage = detectBrowserLanguage();
  
  // 翻译函数
  const t = (key: keyof typeof import('@/utils/language').translations['zh-CN']) => {
    return getTranslation(currentLanguage, key);
  };

  const [documents, setDocuments] = useState<DocumentFile[]>([
    {
      id: '1',
      name: '2024年度财务报告.pdf',
      type: 'pdf',
      size: 2.4 * 1024 * 1024,
      uploadTime: new Date(Date.now() - 2 * 60 * 60 * 1000),
      status: 'completed',
      ocrResult: {
        text: '2024年度财务报告显示公司整体运营状况良好...',
        confidence: 96.5,
        language: 'zh-CN',
        pageCount: 45
      },
      analysis: {
        summary: '财务状况稳健，净利润同比增长15.2%，现金流充裕，主营业务收入增长稳定。建议关注市场扩张和成本控制。',
        keyPoints: [
          '净利润同比增长15.2%，达到3.2亿元',
          '现金流充裕，经营现金流净额2.1亿元',
          '主营业务收入增长12.8%',
          '毛利率稳定在35.6%'
        ],
        entities: [
          { name: '净利润', type: '财务指标', count: 12 },
          { name: '现金流', type: '财务指标', count: 8 },
          { name: '营业收入', type: '财务指标', count: 15 }
        ],
        sentiment: 'positive',
        topics: ['财务分析', '业绩报告', '投资价值'],
        readingTime: 25
      }
    },
    {
      id: '2',
      name: '合同模版集合.docx',
      type: 'docx',
      size: 1.8 * 1024 * 1024,
      uploadTime: new Date(Date.now() - 4 * 60 * 60 * 1000),
      status: 'processing',
      progress: 65
    },
    {
      id: '3',
      name: '产品需求文档.pdf',
      type: 'pdf',
      size: 3.1 * 1024 * 1024,
      uploadTime: new Date(Date.now() - 24 * 60 * 60 * 1000),
      status: 'completed',
      ocrResult: {
        text: '产品需求规格说明书 v2.1...',
        confidence: 94.2,
        language: 'zh-CN',
        pageCount: 28
      },
      analysis: {
        summary: '产品需求明确，功能设计合理，预计开发周期6个月。需要重点关注用户体验和性能优化。',
        keyPoints: [
          '核心功能模块设计完整',
          '用户界面原型清晰',
          '性能要求明确定义',
          '安全性考虑充分'
        ],
        entities: [
          { name: '用户界面', type: '功能模块', count: 18 },
          { name: '数据库', type: '技术组件', count: 12 },
          { name: 'API接口', type: '技术组件', count: 9 }
        ],
        sentiment: 'neutral',
        topics: ['产品设计', '需求分析', '技术规范'],
        readingTime: 18
      }
    },
    {
      id: '4',
      name: '市场调研报告.xlsx',
      type: 'xlsx',
      size: 856 * 1024,
      uploadTime: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000),
      status: 'completed',
      analysis: {
        summary: '市场前景乐观，目标用户群体明确，竞争对手分析详细。建议加快产品上市节奏。',
        keyPoints: [
          '目标市场规模达50亿元',
          '用户需求增长趋势明显',
          '竞争格局相对分散',
          '技术门槛适中'
        ],
        entities: [
          { name: '市场规模', type: '市场指标', count: 5 },
          { name: '用户群体', type: '市场指标', count: 8 },
          { name: '竞争对手', type: '市场指标', count: 12 }
        ],
        sentiment: 'positive',
        topics: ['市场分析', '竞争研究', '商业机会'],
        readingTime: 12
      }
    }
  ]);

  const [selectedDocument, setSelectedDocument] = useState<DocumentFile | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'completed' | 'processing' | 'error'>('all');
  const [dragActive, setDragActive] = useState(false);

  const stats: AnalysisStats = {
    totalDocuments: documents.length,
    processedToday: documents.filter(doc => 
      doc.uploadTime > new Date(Date.now() - 24 * 60 * 60 * 1000)
    ).length,
    averageProcessingTime: 3.2,
    successRate: 98.5,
    totalSize: documents.reduce((sum, doc) => sum + doc.size, 0),
    languages: { 'zh-CN': 3, 'en-US': 1 },
    documentTypes: { 'pdf': 2, 'docx': 1, 'xlsx': 1 }
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

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(e.dataTransfer.files);
    }
  }, []);

  const handleFiles = (files: FileList) => {
    Array.from(files).forEach(file => {
      const newDoc: DocumentFile = {
        id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
        name: file.name,
        type: file.name.split('.').pop()?.toLowerCase() as any || 'txt',
        size: file.size,
        uploadTime: new Date(),
        status: 'uploading',
        progress: 0
      };

      setDocuments(prev => [...prev, newDoc]);

      // 模拟上传和处理过程
      setTimeout(() => {
        setDocuments(prev => prev.map(doc => 
          doc.id === newDoc.id 
            ? { ...doc, status: 'processing', progress: 30 }
            : doc
        ));
      }, 1000);

      setTimeout(() => {
        setDocuments(prev => prev.map(doc => 
          doc.id === newDoc.id 
            ? { ...doc, status: 'completed', progress: 100 }
            : doc
        ));
      }, 5000);
    });
  };

  const filteredDocuments = documents.filter(doc => {
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = filterStatus === 'all' || doc.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="max-w-7xl mx-auto p-6 space-y-8">
        {/* 页面标题 */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{t('documentAnalysis')}</h1>
            <p className={`text-lg ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              {currentLanguage === 'zh-CN' ? 'OCR识别、智能分析、内容提取一站式服务' : 'One-stop service for OCR recognition, intelligent analysis, and content extraction'}
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <Button variant="outline" className={`${isDarkMode ? 'border-gray-600 text-gray-300 hover:bg-gray-700' : ''}`}>
              <RefreshCw className="w-4 h-4 mr-2" />
              {currentLanguage === 'zh-CN' ? '刷新状态' : 'Refresh Status'}
            </Button>
            <Button className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0">
              <Upload className="w-4 h-4 mr-2" />
              {t('uploadDocument')}
            </Button>
          </div>
        </div>

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
                {stats.averageProcessingTime}s
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
                {stats.successRate}%
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
              >
                <Upload className="w-4 h-4 mr-2" />
{currentLanguage === 'zh-CN' ? '选择文件' : 'Select Files'}
              </Button>
              <input
                id="file-input"
                type="file"
                multiple
                className="hidden"
                onChange={(e) => e.target.files && handleFiles(e.target.files)}
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
                {filteredDocuments.map((doc) => (
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
                        <Button variant="ghost" size="sm" className="p-1">
                          <MoreHorizontal className="w-4 h-4" />
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
                      <Button size="sm" variant="outline">
                        <Eye className="w-4 h-4 mr-1" />
{currentLanguage === 'zh-CN' ? '预览' : 'Preview'}
                      </Button>
                      <Button size="sm" variant="outline">
                        <Download className="w-4 h-4 mr-1" />
{currentLanguage === 'zh-CN' ? '下载' : 'Download'}
                      </Button>
                      <Button size="sm" variant="outline">
                        <Share2 className="w-4 h-4 mr-1" />
{currentLanguage === 'zh-CN' ? '分享' : 'Share'}
                      </Button>
                    </div>
                  </div>
                </div>

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