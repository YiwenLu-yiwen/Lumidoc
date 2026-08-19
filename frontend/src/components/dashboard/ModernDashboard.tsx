import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Brain,
  Zap,
  FileText,
  Upload,
  BarChart3,
  MessageSquare,
  FolderOpen,
  Database,
  Cpu,
  HardDrive,
  Server,
  Wifi,
  ChevronRight,
  Plus,
  Search,
  MoreHorizontal,
  Eye,
  Download,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  RefreshCw
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { detectBrowserLanguage, getTranslation } from '@/utils/language';
import { useTheme } from '@/context/ThemeContext';
import { OllamaApi, type OllamaModel, type ModelPullStatus } from '@/api/ollama';
import { useAuth } from '@/context/AuthContext';
import { projectApi } from '@/api/project';
import { fileApi } from '@/api/file';

// 企业级设计系统 - Google Workspace 风格
const DESIGN_TOKENS = {
  // 标准化间距系统（基于 8px 网格）
  spacing: {
    xs: '0.5rem',    // 8px
    sm: '0.75rem',   // 12px  
    md: '1rem',      // 16px
    lg: '1.5rem',    // 24px
    xl: '2rem',      // 32px
    '2xl': '3rem',   // 48px
    section: 'space-y-8',
    grid: 'gap-6',
    cardPadding: 'p-6',
    cardPaddingSmall: 'p-4'
  },
  // 语义化字体系统
  typography: {
    displayLarge: 'text-4xl font-bold tracking-tight leading-tight',
    displayMedium: 'text-3xl font-bold tracking-tight leading-tight', 
    headlineLarge: 'text-2xl font-bold tracking-tight leading-snug',
    headlineMedium: 'text-xl font-semibold leading-snug',
    titleLarge: 'text-lg font-semibold leading-normal',
    titleMedium: 'text-base font-medium leading-normal',
    bodyLarge: 'text-base leading-relaxed',
    bodyMedium: 'text-sm leading-relaxed',
    labelLarge: 'text-sm font-medium leading-normal',
    labelMedium: 'text-xs font-medium leading-normal',
    caption: 'text-xs text-muted-foreground leading-normal'
  },
  // 语义化颜色系统
  colors: {
    primary: {
      gradient: 'bg-gradient-to-r from-blue-600 to-blue-700',
      text: 'text-blue-600',
      bg: 'bg-blue-50 dark:bg-blue-950/20',
      border: 'border-blue-200 dark:border-blue-800'
    },
    success: {
      text: 'text-emerald-600 dark:text-emerald-400',
      bg: 'bg-emerald-50 dark:bg-emerald-950/20',
      border: 'border-emerald-200 dark:border-emerald-800'
    },
    warning: {
      text: 'text-amber-600 dark:text-amber-400',
      bg: 'bg-amber-50 dark:bg-amber-950/20', 
      border: 'border-amber-200 dark:border-amber-800'
    },
    error: {
      text: 'text-red-600 dark:text-red-400',
      bg: 'bg-red-50 dark:bg-red-950/20',
      border: 'border-red-200 dark:border-red-800'
    },
    info: {
      text: 'text-blue-600 dark:text-blue-400',
      bg: 'bg-blue-50 dark:bg-blue-950/20',
      border: 'border-blue-200 dark:border-blue-800'
    }
  },
  // 统一阴影系统
  shadows: {
    sm: 'shadow-sm',
    md: 'shadow-md', 
    lg: 'shadow-lg shadow-black/5',
    xl: 'shadow-xl shadow-black/10'
  },
  // 现代圆角系统
  radius: {
    sm: 'rounded-lg',
    md: 'rounded-xl', 
    lg: 'rounded-2xl',
    full: 'rounded-full'
  },
  // 增强的12列响应式网格系统
  grid: {
    container: 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8',
    cols1: 'grid-cols-1',
    cols2: 'grid-cols-1 sm:grid-cols-2',
    cols3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    cols4: 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4',
    cols6: 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6',
    cols12: 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 2xl:grid-cols-12',
    // 新增的适应性布局类
    metricsGrid: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
    contentGrid: 'grid-cols-1 lg:grid-cols-3',
    actionGrid: 'grid-cols-2 gap-4'
  },
  // 动画和过渡
  transitions: {
    default: 'transition-all duration-200 ease-out',
    slow: 'transition-all duration-300 ease-out',
    fast: 'transition-all duration-150 ease-out'
  },
  // 可访问性增强
  accessibility: {
    focusRing: 'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background',
    skipLink: 'sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 z-50 bg-primary text-primary-foreground px-4 py-2 rounded-md',
    screenReader: 'sr-only',
    highContrast: 'data-high-contrast:border-4 data-high-contrast:border-primary',
    reducedMotion: 'motion-reduce:transition-none motion-reduce:animate-none'
  }
};

interface ProjectStats {
  id: string;
  name: string;
  status: 'active' | 'completed' | 'paused';
  progress: number;
  lastActivity: string;
  documentCount: number;
  chatCount: number;
}

interface DocumentInfo {
  id: string;
  name: string;
  type: 'pdf' | 'docx' | 'txt' | 'image';
  size: string;
  uploadTime: string;
  status: 'processed' | 'processing' | 'error';
  summary?: string;
}

const getFileTypeFromMime = (mimeType: string): 'pdf' | 'docx' | 'txt' | 'image' => {
  if (mimeType.includes('pdf')) return 'pdf';
  if (mimeType.includes('word') || mimeType.includes('document')) return 'docx';
  if (mimeType.includes('text')) return 'txt';
  if (mimeType.includes('image')) return 'image';
  return 'txt';
};

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

// 企业级指标卡片组件接口 - 升级版
interface MetricCardProps {
  icon: React.ReactNode;
  title: string;
  value: string;
  subtitle: string;
  status: 'success' | 'warning' | 'error' | 'info';
  trend?: {
    text: string;
    direction?: 'up' | 'down' | 'neutral';
    percentage?: string;
  };
  loading?: boolean;
  onClick?: () => void;
  priority?: 'high' | 'medium' | 'low';
  badge?: {
    text: string;
    variant: 'success' | 'warning' | 'error' | 'info';
  };
}

const MetricCard: React.FC<MetricCardProps> = ({
  icon,
  title,
  value,
  subtitle,
  status,
  trend,
  loading = false,
  onClick,
  priority = 'medium',
  badge
}) => {
  // 统一状态颜色系统
  const getStatusStyle = (statusType: string) => {
    const styles = {
      success: {
        iconBg: 'bg-emerald-50 dark:bg-emerald-950/30',
        iconColor: 'text-emerald-600 dark:text-emerald-400',
        dot: 'bg-emerald-500',
        trend: 'text-emerald-600 dark:text-emerald-400'
      },
      warning: {
        iconBg: 'bg-amber-50 dark:bg-amber-950/30',
        iconColor: 'text-amber-600 dark:text-amber-400',
        dot: 'bg-amber-500',
        trend: 'text-amber-600 dark:text-amber-400'
      },
      error: {
        iconBg: 'bg-red-50 dark:bg-red-950/30',
        iconColor: 'text-red-600 dark:text-red-400',
        dot: 'bg-red-500',
        trend: 'text-red-600 dark:text-red-400'
      },
      info: {
        iconBg: 'bg-blue-50 dark:bg-blue-950/30',
        iconColor: 'text-blue-600 dark:text-blue-400',
        dot: 'bg-blue-500',
        trend: 'text-blue-600 dark:text-blue-400'
      }
    };
    return styles[statusType as keyof typeof styles];
  };

  const statusStyle = getStatusStyle(status);
  const priorityBorder = {
    high: 'border-l-4 border-l-red-500',
    medium: 'border-l-4 border-l-blue-500', 
    low: 'border-l-4 border-l-gray-300'
  };

  return (
    <div 
      className={`
        relative overflow-hidden group
        ${DESIGN_TOKENS.radius.md} ${DESIGN_TOKENS.shadows.sm}
        border border-border/50 bg-card/80 backdrop-blur-sm
        ${DESIGN_TOKENS.transitions.default} ${DESIGN_TOKENS.accessibility.reducedMotion}
        ${onClick ? `cursor-pointer hover:shadow-lg hover:border-primary/30 hover:bg-card/90 ${DESIGN_TOKENS.accessibility.focusRing}` : ''}
        ${loading ? 'animate-pulse' : ''}
        ${priorityBorder[priority]}
        hover:scale-[1.02] hover:-translate-y-1 motion-reduce:hover:scale-100 motion-reduce:hover:translate-y-0
        min-h-[140px] sm:min-h-[160px]
        w-full
        ${DESIGN_TOKENS.accessibility.highContrast}
      `}
      onClick={onClick}
      role={onClick ? 'button' : 'article'}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      } : undefined}
      aria-label={`${title}: ${value} - ${subtitle}`}
      aria-describedby={trend ? `trend-${title.replace(/\s+/g, '-').toLowerCase()}` : undefined}
      aria-live={loading ? 'polite' : undefined}
      aria-busy={loading}
    >
      {/* 背景装饰渐变 */}
      <div className="absolute inset-0 bg-gradient-to-br from-background/10 to-transparent" />
      
      <div className={DESIGN_TOKENS.spacing.cardPadding}>
        {/* 头部区域 */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className={`
              ${DESIGN_TOKENS.radius.sm} p-3
              ${statusStyle.iconBg}
              ${DESIGN_TOKENS.transitions.default}
              group-hover:scale-110
            `}>
              <div className={`w-5 h-5 ${statusStyle.iconColor}`}>
                {icon}
              </div>
            </div>
            
            {badge && (
              <span className={`
                ${DESIGN_TOKENS.typography.labelMedium}
                px-2 py-1 ${DESIGN_TOKENS.radius.sm}
                ${getStatusStyle(badge.variant).iconBg}
                ${getStatusStyle(badge.variant).iconColor}
              `}>
                {badge.text}
              </span>
            )}
          </div>
          
          <div className={`
            w-2 h-2 ${DESIGN_TOKENS.radius.full} ${statusStyle.dot}
            ${DESIGN_TOKENS.transitions.default}
            group-hover:scale-125 group-hover:shadow-lg
          `} />
        </div>
        
        {/* 指标内容区域 */}
        <div className="space-y-2">
          <p className={`${DESIGN_TOKENS.typography.labelLarge} text-muted-foreground`}>
            {title}
          </p>
          
          {loading ? (
            <div className="space-y-2">
              <div className="h-8 w-20 bg-muted/50 rounded animate-pulse" />
              <div className="h-4 w-16 bg-muted/30 rounded animate-pulse" />
            </div>
          ) : (
            <>
              <p className={`${DESIGN_TOKENS.typography.displayMedium} text-foreground tracking-tight`}>
                {value}
              </p>
              <p className={`${DESIGN_TOKENS.typography.bodyMedium} text-muted-foreground`}>
                {subtitle}
              </p>
            </>
          )}
          
          {trend && !loading && (
            <div 
              className={`flex items-center space-x-2 pt-2`}
              id={`trend-${title.replace(/\s+/g, '-').toLowerCase()}`}
              role="status"
              aria-label={`趋势: ${trend.direction === 'up' ? '上升' : trend.direction === 'down' ? '下降' : '稳定'} ${trend.percentage || ''} ${trend.text}`}
            >
              {trend.direction && (
                <div className={`
                  w-4 h-4 ${DESIGN_TOKENS.radius.sm}
                  flex items-center justify-center
                  ${
                    trend.direction === 'up' ? 'bg-emerald-100 dark:bg-emerald-950/30' :
                    trend.direction === 'down' ? 'bg-red-100 dark:bg-red-950/30' :
                    'bg-[#f5f5f5] dark:bg-[#2d2d30]'
                  }
                `}
                aria-hidden="true"
                >
                  <ChevronRight className={`
                    w-3 h-3
                    ${
                      trend.direction === 'up' ? 'rotate-[-90deg] text-emerald-600' :
                      trend.direction === 'down' ? 'rotate-90 text-red-600' :
                      'text-gray-500'
                    }
                  `} />
                </div>
              )}
              <p className={`${DESIGN_TOKENS.typography.labelMedium} ${statusStyle.trend}`}>
                {trend.percentage && (
                  <span className="font-semibold mr-1" aria-label={`变化幅度 ${trend.percentage}`}>
                    {trend.percentage}
                  </span>
                )}
                <span aria-label={`趋势描述: ${trend.text}`}>
                  {trend.text}
                </span>
              </p>
              {/* 屏幕阅读器专用趋势描述 */}
              <span className={DESIGN_TOKENS.accessibility.screenReader}>
                {trend.direction === 'up' && '趋势向上'}
                {trend.direction === 'down' && '趋势向下'}
                {trend.direction === 'neutral' && '趋势平稳'}
                {trend.percentage && `, 变化幅度 ${trend.percentage}`}
                {`, ${trend.text}`}
              </span>
            </div>
          )}
        </div>
      </div>
      
      {/* 悬停时的微妙动画效果 */}
      {onClick && (
        <div className="absolute inset-0 bg-gradient-to-r from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      )}
    </div>
  );
};

export function ModernDashboard() {
  const { user, isAdmin } = useAuth();
  
  const { isDarkMode } = useTheme();
  const currentLanguage = detectBrowserLanguage();
  // 真实的数据更新时间戳
  const [lastDataUpdateTime, setLastDataUpdateTime] = useState(new Date());
  // 当前时间 - 用于计算真实的时间差
  const [currentTime, setCurrentTime] = useState(new Date());
  // 数据刷新状态
  const [isRefreshingData, setIsRefreshingData] = useState(false);
  
  // 调试语言检测（生产环境可删除）
  // console.log('🔍 当前检测到的语言:', currentLanguage);
  
  // 翻译函数
  const t = (key: keyof typeof import('@/utils/language').translations['zh-CN']) => {
    return getTranslation(currentLanguage, key);
  };
  
  // 真实时间格式化函数 - 基于当前时间和数据更新时间计算
  const formatTimeAgo = (updateTime: Date, currentTime: Date) => {
    const diffInSeconds = Math.floor((currentTime.getTime() - updateTime.getTime()) / 1000);
    
    if (diffInSeconds < 60) {
      return currentLanguage === 'zh-CN' ? `${diffInSeconds}秒前` : `${diffInSeconds}s ago`;
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60);
      return currentLanguage === 'zh-CN' ? `${minutes}分钟前` : `${minutes}m ago`;
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600);
      return currentLanguage === 'zh-CN' ? `${hours}小时前` : `${hours}h ago`;
    } else {
      const days = Math.floor(diffInSeconds / 86400);
      return currentLanguage === 'zh-CN' ? `${days}天前` : `${days}d ago`;
    }
  };
  
  // Ollama 模型管理状态
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [downloadingModels, setDownloadingModels] = useState<Set<string>>(new Set());
  const [downloadProgress, setDownloadProgress] = useState<Record<string, ModelPullStatus>>({});
  const [customModelName, setCustomModelName] = useState('');
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [ollamaStatus, setOllamaStatus] = useState<boolean | null>(null);

  // 真实数据状态
  const [projectStats, setProjectStats] = useState<ProjectStats[]>([]);
  const [recentDocuments, setRecentDocuments] = useState<DocumentInfo[]>([]);
  const userRef = useRef(user);
  const recentDocumentsRef = useRef(recentDocuments);
  userRef.current = user;
  recentDocumentsRef.current = recentDocuments;
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false);
  // 知识图谱统计
  const [knowledgeGraphStats, setKnowledgeGraphStats] = useState({
    entityCount: 0,
    relationCount: 0,
    isLoading: false,
    isConnected: false
  });
  
  // 统计真实的 Ollama 模型数量
  const actualModelStats = {
    thinking: ollamaModels.filter(model => OllamaApi.detectModelType(model.name) === 'thinking').length,
    fast: ollamaModels.filter(model => OllamaApi.detectModelType(model.name) === 'fast').length,
    total: ollamaModels.length
  };
  
  // 加载知识图谱统计数据
  const loadKnowledgeGraphStats = useCallback(async () => {
    setKnowledgeGraphStats(prev => ({ ...prev, isLoading: true }));
    
    try {
      // 尝试连接 Neo4j 并获取统计数据
      // 这里需要替换为真实的 Neo4j API 调用
      const response = await fetch('/api/v1/graph/stats', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('lumidoc_token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setKnowledgeGraphStats({
          entityCount: data.entities || 0,
          relationCount: data.relations || 0,
          isLoading: false,
          isConnected: true
        });
      } else {
        throw new Error('Failed to fetch graph stats');
      }
    } catch (error) {
      console.log('[Dashboard] Neo4j 连接失败，使用文档统计作为近似值:', error);
      // 如果 Neo4j 不可用，使用文档数量的近似估算
      const approximateEntities = recentDocumentsRef.current.length * 50; // 每个文档大约50个实体
      setKnowledgeGraphStats({
        entityCount: approximateEntities,
        relationCount: approximateEntities * 2, // 关系通常是实体的2倍
        isLoading: false,
        isConnected: false
      });
    }
  }, []);

  // 加载 Ollama 模型列表
  const loadOllamaModels = useCallback(async () => {
    setIsLoadingModels(true);
    try {
      const response = await OllamaApi.getInstalledModels();
      const filteredModels = response.models.filter(model => 
        !OllamaApi.isEmbeddingModel(model.name)
      );
      setOllamaModels(filteredModels);
      setOllamaStatus(true);
    } catch (error) {
      console.error('加载 Ollama 模型失败:', error);
      setOllamaStatus(false);
    } finally {
      setIsLoadingModels(false);
    }
  }, []);
  
  // 下载模型
  const downloadModel = async (modelName: string) => {
    if (downloadingModels.has(modelName)) return;
    
    setDownloadingModels(prev => new Set([...prev, modelName]));
    setDownloadProgress(prev => ({ ...prev, [modelName]: { status: 'started', percentage: 0, message: t('downloadStarted') } }));
    
    try {
      const response = await OllamaApi.pullModel({ name: modelName });
      
      if (response.status === 'success') {
        setDownloadProgress(prev => ({ ...prev, [modelName]: { status: 'completed', percentage: 100, message: t('downloadCompleted') } }));
        await loadOllamaModels(); // 重新加载模型列表
      } else {
        // 监控下载进度
        const checkProgress = setInterval(async () => {
          try {
            const status = await OllamaApi.getPullStatus(modelName);
            setDownloadProgress(prev => ({ ...prev, [modelName]: status }));
            
            if (status.status === 'completed') {
              clearInterval(checkProgress);
              await loadOllamaModels();
            } else if (status.status === 'error' || status.status === 'not_found') {
              clearInterval(checkProgress);
            }
          } catch (error) {
            console.error('检查下载进度失败:', error);
            clearInterval(checkProgress);
          }
        }, 2000);
        
        // 15分钟后清理
        setTimeout(() => {
          clearInterval(checkProgress);
          setDownloadingModels(prev => {
            const newSet = new Set(prev);
            newSet.delete(modelName);
            return newSet;
          });
        }, 15 * 60 * 1000);
      }
    } catch (error) {
      console.error('下载模型失败:', error);
      setDownloadProgress(prev => ({ ...prev, [modelName]: { status: 'error', percentage: 0, message: `错误: ${error}` } }));
    } finally {
      setTimeout(() => {
        setDownloadingModels(prev => {
          const newSet = new Set(prev);
          newSet.delete(modelName);
          return newSet;
        });
      }, 3000);
    }
  };
  
  // 处理自定义模型下载
  const handleCustomModelDownload = async () => {
    if (!customModelName.trim()) return;
    
    await downloadModel(customModelName.trim());
    setCustomModelName('');
    setShowCustomInput(false);
  };
  
  // 获取热门模型推荐
  const popularModels = OllamaApi.getPopularModels(currentLanguage);
  
  // 加载真实项目数据
  const loadProjectStats = useCallback(async () => {
    if (!userRef.current) return;
    
    setIsLoadingProjects(true);
    try {
      const projects = await projectApi.listProjects();
      
      // 转换项目数据格式以适配ProjectStats接口
      const stats: ProjectStats[] = projects.map(project => ({
        id: project.id,
        name: project.name,
        status: project.status as 'active' | 'completed' | 'paused',
        progress: 85, // 暂时使用模拟进度，可以后续从项目统计API获取
        lastActivity: new Date(project.updated_at).toLocaleString(),
        documentCount: 0, // 需要从文件API获取
        chatCount: 0 // 需要从聊天API获取
      }));
      
      setProjectStats(stats);
    } catch (error) {
      console.error('[Dashboard] 加载项目数据失败:', error);
      // 保持空数组，避免显示错误状态
    } finally {
      setIsLoadingProjects(false);
    }
  }, []);

  // 加载最近文档数据
  const loadRecentDocuments = useCallback(async () => {
    if (!userRef.current || projectStats.length === 0) return;
    
    setIsLoadingDocuments(true);
    try {
      // 获取所有项目的文件，然后取最近的几个
      const allFiles: DocumentInfo[] = [];
      
      for (const project of projectStats) {
        try {
          const files = await fileApi.listFiles(project.id);
          const projectFiles = files.slice(0, 5).map(file => ({
            id: file.file_id,
            name: file.display_name || file.filename,
            type: getFileTypeFromMime(file.content_type),
            size: formatFileSize(file.size),
            uploadTime: file.created_at, // 保存原始时间戳
            status: file.status as 'processed' | 'processing' | 'error',
            summary: file.metadata ? file.metadata.substring(0, 100) + '...' : undefined
          }));
          allFiles.push(...projectFiles);
        } catch (error) {
          console.error(`[Dashboard] 获取项目${project.id}文件失败:`, error);
        }
      }
      
      // 按时间排序并取前4个
      allFiles.sort((a, b) => new Date(b.uploadTime).getTime() - new Date(a.uploadTime).getTime());
      setRecentDocuments(allFiles.slice(0, 4));
    } catch (error) {
      console.error('[Dashboard] 加载文档数据失败:', error);
    } finally {
      setIsLoadingDocuments(false);
    }
  }, [projectStats]);

  // 全面的数据刷新函数
  const refreshAllData = useCallback(async () => {
    console.log('[Dashboard] 开始刷新所有数据...');
    setIsRefreshingData(true);

    try {
      await Promise.allSettled([
        loadOllamaModels(),
        userRef.current ? loadProjectStats() : Promise.resolve(),
        loadKnowledgeGraphStats()
      ]);
      setLastDataUpdateTime(new Date());
      console.log('[Dashboard] 数据刷新完成:', new Date().toLocaleString());
    } catch (error) {
      console.error('[Dashboard] 数据刷新失败:', error);
    } finally {
      setIsRefreshingData(false);
    }
  }, [loadKnowledgeGraphStats, loadOllamaModels, loadProjectStats]);


  // 组件挂载时初始化数据
  useEffect(() => {
    console.log('[Dashboard] 组件挂载，初始化数据...');
    void refreshAllData();
  }, [refreshAllData, user]);
  
  // 每秒更新当前时间 - 用于实时计算时间差
  useEffect(() => {
    const timeInterval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000); // 每秒更新一次
    
    return () => clearInterval(timeInterval);
  }, []);
  
  // 每10分钟自动刷新数据
  useEffect(() => {
    const dataRefreshInterval = setInterval(() => {
      console.log('[Dashboard] 10分钟定时刷新数据...');
      refreshAllData();
    }, 10 * 60 * 1000); // 10分钟刷新一次
    
    return () => clearInterval(dataRefreshInterval);
  }, [refreshAllData]);

  // 项目数据加载完成后加载文档数据
  useEffect(() => {
    if (projectStats.length > 0) {
      loadRecentDocuments();
    }
  }, [loadRecentDocuments, projectStats]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
      case 'online':
      case 'processed':
        return 'text-green-500';
      case 'paused':
      case 'busy':
      case 'processing':
        return 'text-yellow-500';
      case 'completed':
        return 'text-blue-500';
      case 'offline':
      case 'error':
        return 'text-red-500';
      default:
        return 'text-gray-500';
    }
  };

  const getStatusDot = (status: string) => {
    const color = getStatusColor(status);
    return <div className={`w-2 h-2 rounded-full ${color.replace('text-', 'bg-')}`} />;
  };

  const getFileIcon = (type: string) => {
    switch (type) {
      case 'pdf':
        return <FileText className="w-4 h-4 text-red-500" />;
      case 'docx':
        return <FileText className="w-4 h-4 text-blue-500" />;
      case 'txt':
        return <FileText className="w-4 h-4 text-gray-500" />;
      case 'image':
        return <FileText className="w-4 h-4 text-purple-500" />;
      default:
        return <FileText className="w-4 h-4 text-gray-500" />;
    }
  };

  return (
    <div className="h-full overflow-y-auto ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} dark:bg-gray-900 text-gray-900 dark:text-white">
      {/* 跳转链接 - 可访问性增强 */}
      <a 
        href="#main-content" 
        className={DESIGN_TOKENS.accessibility.skipLink}
        aria-label="跳转到主要内容"
      >
        跳转到主要内容
      </a>
      <a 
        href="#metrics-section" 
        className={DESIGN_TOKENS.accessibility.skipLink}
        aria-label="跳转到指标概览"
      >
        跳转到指标概览
      </a>
      
      <div className={DESIGN_TOKENS.grid.container}>
        <main 
          id="main-content"
          className={DESIGN_TOKENS.spacing.section}
          role="main"
          aria-label="智能工作台仪表盘"
        >
          {/* 企业级页面标题区域 - 响应式优化 */}
          <header className="space-y-4 sm:space-y-6">
            <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between space-y-4 xl:space-y-0">
              <div className="space-y-2">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex-shrink-0">
                    <Database className="w-6 h-6 sm:w-8 sm:h-8 text-white" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h1 className="text-2xl sm:text-4xl font-black text-gray-900 dark:text-white truncate">
                      {t('intelligentWorkbench')}
                    </h1>
                    <p className="text-sm sm:text-base font-medium text-gray-600 dark:text-gray-300 mt-1 hidden sm:block">
                      {t('aiDocumentPlatform')} • {currentLanguage === 'zh-CN' ? '实时监控与管理' : 'Real-time monitoring and management'}
                    </p>
                    <p className="text-sm font-medium text-gray-600 dark:text-gray-300 mt-1 sm:hidden">
                      {currentLanguage === 'zh-CN' ? 'AI 文档处理平台' : 'AI Document Platform'}
                    </p>
                  </div>
                </div>
                
                {/* 面包屑导航 - 移动端隐藏 */}
                <nav className="hidden md:flex items-center space-x-2 text-sm text-gray-500 dark:text-gray-400" aria-label="面包屑">
                  <span className="hover:text-gray-900 dark:hover:text-white cursor-pointer transition-colors text-gray-600 dark:text-gray-300 font-medium">
                    {currentLanguage === 'zh-CN' ? '首页' : 'Home'}
                  </span>
                  <ChevronRight className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                  <span className="text-gray-900 dark:text-white font-bold">
                    {currentLanguage === 'zh-CN' ? '仪表盘' : 'Dashboard'}
                  </span>
                </nav>
              </div>
              
            </div>
            
            {/* 分隔线 */}
            <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />
          </header>

          {/* Hero 指标区域 - 企业级设计 - 响应式优化 */}
          <section 
            id="metrics-section"
            className="space-y-4 sm:space-y-6" 
            aria-label="核心指标概览"
            role="region"
          >
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-2 sm:space-y-0">
              <div>
                <h2 className="text-base sm:text-lg font-black text-gray-900 dark:text-white">
                  {currentLanguage === 'zh-CN' ? '系统状态概览' : 'System Status Overview'}
                </h2>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-300 mt-1 hidden sm:block">
                  {currentLanguage === 'zh-CN' ? '实时监控核心业务指标和系统健康状态' : 'Real-time monitoring of core business metrics and system health'}
                </p>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-300 mt-1 sm:hidden">
                  {currentLanguage === 'zh-CN' ? '核心指标监控' : 'Core Metrics'}
                </p>
              </div>
              <div className="flex items-center space-x-3">
                <span className="text-xs font-medium text-gray-600 dark:text-gray-400 hidden md:inline">
                  {currentLanguage === 'zh-CN' ? '最近更新: ' : 'Last updated: '}{formatTimeAgo(lastDataUpdateTime, currentTime)}
                </span>
                <span className="text-xs font-medium text-gray-600 dark:text-gray-400 md:hidden">
                  {formatTimeAgo(lastDataUpdateTime, currentTime)}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={refreshAllData}
                  disabled={isRefreshingData}
                  className="h-6 w-6 p-0 hover:bg-gray-100 dark:hover:bg-gray-700"
                  title={currentLanguage === 'zh-CN' ? '手动刷新数据' : 'Manually refresh data'}
                >
                  <RefreshCw className={`w-3 h-3 ${isRefreshingData ? 'animate-spin' : ''}`} />
                </Button>
                <div className={`w-2 h-2 rounded-full ${isRefreshingData ? 'bg-blue-500 animate-spin' : 'bg-green-500 animate-pulse'}`} />
              </div>
            </div>
            
            <div className={`grid ${DESIGN_TOKENS.grid.metricsGrid} ${DESIGN_TOKENS.spacing.grid}`}>
              {/* AI模型性能指标 */}
              <MetricCard
                icon={<Brain className="w-6 h-6" />}
                title={t('thinkingModel')}
                value={`${actualModelStats.thinking}`}
                subtitle={t('deepReasoning')}
                status={ollamaStatus === false ? 'error' : 'success'}
                trend={{
                  text: currentLanguage === 'zh-CN' ? `共 ${actualModelStats.total} 个本地模型` : `${actualModelStats.total} local models total`,
                  direction: 'neutral'
                }}
                priority="high"
                badge={{
                  text: currentLanguage === 'zh-CN' ? 'AI核心' : 'AI Core',
                  variant: 'info'
                }}
                loading={isLoadingModels}
              />
              
              <MetricCard
                icon={<Zap className="w-6 h-6" />}
                title={t('fastModel')}
                value={`${actualModelStats.fast}`}
                subtitle={t('instantResponse')}
                status={ollamaStatus === false ? 'error' : 'success'}
                trend={{
                  text: ollamaStatus ? (currentLanguage === 'zh-CN' ? 'Ollama 服务在线' : 'Ollama service online') : (currentLanguage === 'zh-CN' ? 'Ollama 服务离线' : 'Ollama service offline'),
                  direction: ollamaStatus ? 'up' : 'down'
                }}
                priority="high"
                loading={isLoadingModels}
              />
              
              <MetricCard
                icon={<FileText className="w-6 h-6" />}
                title={t('documentProcessing')}
                value={recentDocuments.length.toString()}
                subtitle={currentLanguage === 'zh-CN' ? '智能解析与理解' : 'Intelligent parsing and understanding'}
                status={'success'}
                trend={{
                  text: currentLanguage === 'zh-CN' ? `最近文档: ${recentDocuments.length} 个` : `Recent docs: ${recentDocuments.length}`,
                  direction: 'neutral'
                }}
                priority="medium"
                badge={{
                  text: currentLanguage === 'zh-CN' ? '核心功能' : 'Core Feature',
                  variant: 'success'
                }}
                loading={isLoadingDocuments}
              />
              
              <MetricCard
                icon={<Database className="w-6 h-6" />}
                title={t('knowledgeGraph')}
                value={knowledgeGraphStats.entityCount.toLocaleString()}
                subtitle={t('entityRelations')}
                status={knowledgeGraphStats.isConnected ? 'success' : 'warning'}
                trend={{
                  text: knowledgeGraphStats.isConnected 
                    ? (currentLanguage === 'zh-CN' ? 'Neo4j 稳定运行' : 'Neo4j running stable')
                    : (currentLanguage === 'zh-CN' ? '基于文档估算' : 'Estimated from documents'),
                  direction: 'neutral'
                }}
                priority="medium"
                badge={knowledgeGraphStats.isConnected ? undefined : {
                  text: currentLanguage === 'zh-CN' ? '估算值' : 'Estimated',
                  variant: 'warning'
                }}
                loading={knowledgeGraphStats.isLoading}
              />
            </div>
          </section>

          {/* 主要内容区域 - 企业级布局 - 响应式优化 */}
          <div className={`grid ${DESIGN_TOKENS.grid.contentGrid} gap-8`}>
            {/* 左侧：模型管理和项目状态 */}
            <div className="lg:col-span-2 space-y-8">
              {/* 本地模型管理 - 分界线标题 */}
              <div className="space-y-4">
                <div className="flex items-center">
                  <div className="flex-1 h-px bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200"></div>
                  <h2 className="px-6 text-lg font-black text-gray-900 dark:text-white ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} dark:bg-gray-900">{t('localModelManagement')}</h2>
                  <div className="flex-1 h-px bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200"></div>
                </div>
                
                {/* Ollama 模型管理面板 */}
                <section 
                  className={`rounded-2xl border shadow-sm ${isDarkMode ? 'bg-[#343541] border-gray-700' : 'bg-white border-gray-100'}`}
                  aria-label="模型管理"
                  role="region"
                >
                <div className="p-6 border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-100'}">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <h3 className="text-xl font-black text-gray-950">{t('localModelManagement')}</h3>
                        {ollamaStatus === true && (
                          <CheckCircle className="w-5 h-5 text-green-500" />
                        )}
                        {ollamaStatus === false && (
                          <XCircle className="w-5 h-5 text-red-500" />
                        )}
                        {ollamaStatus === null && (
                          <AlertCircle className="w-5 h-5 text-yellow-500" />
                        )}
                      </div>
                      <p className="text-sm font-medium text-gray-800">
                        {t('modelAutoDownload')}
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={loadOllamaModels}
                        disabled={isLoadingModels}
                        className="bg-blue-50 hover:bg-blue-100 border-blue-200 text-gray-900 font-semibold"
                      >
                        {isLoadingModels ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                          <RefreshCw className="w-4 h-4 mr-2 text-blue-500" />
                        )}
                        {t('refresh')}
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => setShowCustomInput(!showCustomInput)}
                        className="bg-green-50 hover:bg-green-100 border-green-200 text-gray-900 font-semibold"
                      >
                        <Plus className="w-4 h-4 mr-2 text-green-500" />
                        {t('downloadModel')}
                      </Button>
                    </div>
                  </div>
                </div>
                
                <div className="p-6">
                  {/* 自定义模型下载输入框 */}
                  {showCustomInput && (
                    <div className="mb-6 p-4 rounded-xl border bg-gray-50 ${isDarkMode ? 'border-gray-600' : 'border-gray-200'}">
                      <div className="flex items-center space-x-2">
                        <Input
                          placeholder={`${t('enterModelName')} (例: llama3.2:latest)`}
                          value={customModelName}
                          onChange={(e) => setCustomModelName(e.target.value)}
                          onKeyPress={(e) => e.key === 'Enter' && handleCustomModelDownload()}
                          className="flex-1"
                        />
                        <Button 
                          onClick={handleCustomModelDownload}
                          disabled={!customModelName.trim()}
                          size="sm"
                          className="bg-blue-100 hover:bg-blue-200 border-blue-300 text-gray-900 font-semibold"
                        >
                          <Download className="w-4 h-4 mr-2 text-blue-500" />
                          {t('download')}
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => {
                            setShowCustomInput(false);
                            setCustomModelName('');
                          }}
                        >
                          {t('cancel')}
                        </Button>
                      </div>
                    </div>
                  )}
                  
                  {/* 已安装模型列表 */}
                  <div className="mb-6">
                    <h3 className="text-lg font-black text-gray-950 mb-3">{t('installedModels')}</h3>
                    {isLoadingModels ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin mr-2" />
                        <span>{currentLanguage === 'zh-CN' ? `${t('loading')}模型列表...` : `${t('loading')} models...`}</span>
                      </div>
                    ) : ollamaModels.length === 0 ? (
                      <div className="text-center py-8 font-medium text-gray-800">
                        {ollamaStatus === false ? t('cannotConnect') : t('noModelsInstalled')}
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {ollamaModels.map((model) => {
                          const modelType = OllamaApi.detectModelType(model.name);
                          
                          return (
                            <div
                              key={model.name}
                              className="p-4 rounded-xl border ${isDarkMode ? 'border-gray-600' : 'border-gray-200'} ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-50'} transition-all duration-200 hover:shadow-md"
                            >
                              <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center space-x-2">
                                  {modelType === 'thinking' ? (
                                    <Brain className="w-5 h-5 text-purple-500" />
                                  ) : (
                                    <Zap className="w-5 h-5 text-green-500" />
                                  )}
                                  <span className="font-bold text-sm text-gray-950">{model.name}</span>
                                </div>
                                <CheckCircle className="w-4 h-4 text-green-500" />
                              </div>
                              
                              <div className="space-y-2 text-xs">
                                <div className="flex justify-between">
                                  <span className="font-medium text-gray-700">
                                    {t('type')}
                                  </span>
                                  <span className="font-bold text-gray-950">
                                    {modelType === 'thinking' ? t('thinkingModel') : t('fastModel')}
                                  </span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="font-medium text-gray-700">
                                    {t('size')}
                                  </span>
                                  <span className="font-bold text-gray-950">
                                    {model.size ? OllamaApi.formatFileSize(model.size) : (currentLanguage === 'zh-CN' ? '未知' : 'Unknown')}
                                  </span>
                                </div>
                                {model.modified && (
                                  <div className="flex justify-between">
                                    <span className="font-medium text-gray-700">
                                      {t('modifiedTime')}
                                    </span>
                                    <span className="font-bold text-gray-950">
                                      {new Date(model.modified).toLocaleDateString()}
                                    </span>
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                  
                  {/* 热门模型推荐 */}
                  <div>
                    <h3 className="text-lg font-black text-gray-950 mb-3">{t('popularModels')}</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {popularModels.map((model) => {
                        const isInstalled = ollamaModels.some(installed => installed.name === model.name);
                        const isDownloading = downloadingModels.has(model.name);
                        const progress = downloadProgress[model.name];
                        
                        return (
                          <div
                            key={model.name}
                            className="p-4 rounded-xl border ${isDarkMode ? 'border-gray-600' : 'border-gray-200'} ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-50'} transition-all duration-200 hover:shadow-md"
                          >
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center space-x-2">
                                {model.type === 'thinking' ? (
                                  <Brain className="w-5 h-5 text-purple-500" />
                                ) : (
                                  <Zap className="w-5 h-5 text-green-500" />
                                )}
                                <span className="font-bold text-sm text-gray-950">{model.name}</span>
                              </div>
                              {isInstalled ? (
                                <CheckCircle className="w-4 h-4 text-green-500" />
                              ) : isDownloading ? (
                                <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                              ) : (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => downloadModel(model.name)}
                                  className="text-xs px-2 py-1 bg-blue-50 hover:bg-blue-100 border-blue-200 text-gray-900 font-bold"
                                >
                                  <Download className="w-3 h-3 mr-1 text-blue-500" />
                                  {t('download')}
                                </Button>
                              )}
                            </div>
                            
                            <p className="text-xs mb-2 font-medium text-gray-800">
                              {model.description}
                            </p>
                            
                            <div className="space-y-2 text-xs">
                              <div className="flex justify-between">
                                <span className="text-gray-500">
                                  {t('type')}
                                </span>
                                <span className="font-medium text-gray-900">
                                  {model.type === 'thinking' ? t('thinkingModel') : t('fastModel')}
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-500">
                                  {t('size')}
                                </span>
                                <span className="font-medium text-gray-900">{model.size}</span>
                              </div>
                              
                              {/* 下载进度条 */}
                              {isDownloading && progress && (
                                <div className="mt-2">
                                  <div className="flex justify-between text-xs mb-1">
                                    <span>{progress.message}</span>
                                    <span>{progress.percentage?.toFixed(1)}%</span>
                                  </div>
                                  <div className="w-full h-1.5 rounded-full bg-gray-200">
                                    <div 
                                      className={`h-full rounded-full transition-all duration-300 ${
                                        progress.status === 'completed' ? 'bg-green-500' :
                                        progress.status === 'error' ? 'bg-red-500' :
                                        'bg-blue-500'
                                      }`}
                                      style={{ width: `${progress.percentage || 0}%` }}
                                    />
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </section>
              </div>

              {/* 项目概述 - 分界线标题 */}
              <div className="space-y-4">
                <div className="flex items-center">
                  <div className="flex-1 h-px bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200"></div>
                  <h2 className="px-6 text-lg font-black text-gray-900 dark:text-white ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} dark:bg-gray-900">{t('projectOverview')}</h2>
                  <div className="flex-1 h-px bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200"></div>
                </div>
                
                {/* 项目状态面板 */}
                <section 
                  className="rounded-2xl border ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} ${isDarkMode ? 'border-gray-700' : 'border-gray-100'} shadow-sm"
                  aria-label="项目状态"
                  role="region"
                >
                <div className="p-6 border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-100'}">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-black text-gray-950">{t('projectOverview')}</h2>
                      <p className="text-sm font-medium text-gray-800">
                        {t('monitorProgress')}
                      </p>
                    </div>
                    <Button 
                      variant="outline" 
                      size="sm"
                      className="bg-purple-50 hover:bg-purple-100 border-purple-200 text-gray-900 font-semibold"
                    >
                      <Plus className="w-4 h-4 mr-2 text-purple-500" />
                      {t('newCreate')}
                    </Button>
                  </div>
                </div>
                
                <div className="p-6">
                  {isLoadingProjects ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin mr-2" />
                      <span className="text-gray-600 dark:text-gray-400">{currentLanguage === 'zh-CN' ? '加载项目数据...' : 'Loading project data...'}</span>
                    </div>
                  ) : projectStats.length === 0 ? (
                    <div className="text-center py-8 text-gray-600 dark:text-gray-400">
                      {currentLanguage === 'zh-CN' ? '暂无项目数据' : 'No project data available'}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {projectStats.map((project) => (
                      <div
                        key={project.id}
                        className="p-4 rounded-xl border ${isDarkMode ? 'border-gray-600' : 'border-gray-200'} ${isDarkMode ? 'hover:border-gray-500' : 'hover:border-gray-300'} ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-50'} transition-all duration-200 hover:shadow-lg"
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center space-x-3">
                            <FolderOpen className="w-5 h-5 text-blue-500" />
                            <div>
                              <h3 className="font-bold text-gray-950">{project.name}</h3>
                              <p className="text-sm font-medium text-gray-800">
                                {t('lastActivity')}: {project.lastActivity}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            {getStatusDot(project.status)}
                            <span className={`text-sm font-medium ${getStatusColor(project.status)}`}>
                              {project.status}
                            </span>
                          </div>
                        </div>
                        
                        <div className="mb-3">
                          <div className="flex justify-between text-sm mb-1">
                            <span className="font-medium text-gray-700">
                              {t('progress')}
                            </span>
                            <span className="font-bold text-gray-950">{project.progress}%</span>
                          </div>
                          <div className="w-full h-2 rounded-full bg-gray-200">
                            <div 
                              className="h-full rounded-full bg-gradient-to-r from-green-500 to-blue-500"
                              style={{ width: `${project.progress}%` }}
                            />
                          </div>
                        </div>
                        
                        <div className="flex items-center justify-between text-sm">
                          <div className="flex items-center space-x-4">
                            <div className="flex items-center space-x-1">
                              <FileText className={`w-4 h-4 ${isDarkMode ? 'text-blue-400' : 'text-blue-500'}`} />
                              <span>{project.documentCount}</span>
                            </div>
                            <div className="flex items-center space-x-1">
                              <MessageSquare className={`w-4 h-4 ${isDarkMode ? 'text-green-400' : 'text-green-500'}`} />
                              <span>{project.chatCount}</span>
                            </div>
                          </div>
                          <Button 
                            variant="ghost" 
                            size="sm"
                            className="bg-orange-50 hover:bg-orange-100 text-gray-900 font-semibold"
                          >
                            <Eye className="w-4 h-4 mr-1 text-orange-500" />
                            {t('view')}
                          </Button>
                        </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
              </div>
            </div>

            {/* 右侧：最近文档和快速操作 - 响应式优化 */}
            <div className="space-y-8">
              {/* 最近文档 - 分界线标题 */}
              <div className="space-y-4">
                <div className="flex items-center">
                  <div className="flex-1 h-px bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200"></div>
                  <h2 className="px-6 text-lg font-black text-gray-900 dark:text-white ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} dark:bg-gray-900">{t('recentDocuments')}</h2>
                  <div className="flex-1 h-px bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200"></div>
                </div>
                
                <div className="rounded-2xl border ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} ${isDarkMode ? 'border-gray-700' : 'border-gray-100'} shadow-sm">
                <div className="p-6 border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-100'}">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-black text-gray-950">{t('recentDocuments')}</h2>
                      <p className="text-sm font-medium text-gray-800">
                        {t('viewLatestDocs')}
                      </p>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="sm"
                      className="bg-blue-50 hover:bg-blue-100 text-gray-800"
                    >
                      <Search className="w-4 h-4 text-blue-500" />
                    </Button>
                  </div>
                </div>
                
                <div className="p-6">
                  {isLoadingDocuments ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin mr-2" />
                      <span className="text-gray-600 dark:text-gray-400">{currentLanguage === 'zh-CN' ? '加载文档数据...' : 'Loading document data...'}</span>
                    </div>
                  ) : recentDocuments.length === 0 ? (
                    <div className="text-center py-8 text-gray-600 dark:text-gray-400">
                      {currentLanguage === 'zh-CN' ? '暂无文档数据' : 'No document data available'}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {recentDocuments.map((doc) => (
                      <div
                        key={doc.id}
                        className="p-3 rounded-lg border ${isDarkMode ? 'border-gray-600' : 'border-gray-200'} ${isDarkMode ? 'hover:border-gray-500' : 'hover:border-gray-300'} ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-50'} transition-all duration-200 hover:shadow-md"
                      >
                        <div className="flex items-start space-x-3">
                          {getFileIcon(doc.type)}
                          <div className="flex-1 min-w-0">
                            <h4 className="font-bold text-sm text-gray-950 truncate">{doc.name}</h4>
                            <div className="flex items-center space-x-2 text-xs font-medium text-gray-700 mt-1">
                              <span>{doc.size}</span>
                              <span>•</span>
                              <span>{formatTimeAgo(new Date(doc.uploadTime), currentTime)}</span>
                              {getStatusDot(doc.status)}
                            </div>
                            {doc.summary && doc.status === 'processed' && (
                              <p className="text-xs mt-2 font-medium text-gray-800 line-clamp-2">
                                {doc.summary}
                              </p>
                            )}
                          </div>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="p-1 bg-gray-100 hover:bg-gray-200"
                          >
                            <MoreHorizontal className="w-4 h-4 text-gray-500" />
                          </Button>
                        </div>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {!isLoadingDocuments && recentDocuments.length > 0 && (
                    <div className="mt-4 text-center">
                      <Button 
                        variant="ghost" 
                        className="text-sm w-full bg-blue-50 hover:bg-blue-100 text-gray-900 font-semibold"
                      >
                        {t('viewAllDocs')}
                        <ChevronRight className="w-4 h-4 ml-1 text-blue-500" />
                      </Button>
                    </div>
                  )}
                </div>
                </div>
              </div>

              {/* 快速操作 - 分界线标题 */}
              <div className="space-y-4">
                <div className="flex items-center">
                  <div className="flex-1 h-px bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200"></div>
                  <h2 className="px-6 text-lg font-black text-gray-900 dark:text-white ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} dark:bg-gray-900">{t('quickActions')}</h2>
                  <div className="flex-1 h-px bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200"></div>
                </div>
                
                <div className="rounded-2xl border ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} ${isDarkMode ? 'border-gray-700' : 'border-gray-100'} shadow-sm">
                <div className="p-6 border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-100'}">
                  <h2 className="text-lg font-black text-gray-950">{t('quickActions')}</h2>
                  <p className="text-sm font-medium text-gray-800">
                    {t('commonFeatures')}
                  </p>
                </div>
                
                <div className="p-6">
                  <div className={`grid ${DESIGN_TOKENS.grid.actionGrid}`}>
                    <Button 
                      variant="outline" 
                      className="h-auto p-6 flex flex-col items-center space-y-3 min-h-[100px] bg-blue-50 hover:bg-blue-100 border-blue-200"
                    >
                      <Upload className="w-8 h-8 text-blue-500" />
                      <span className="text-sm font-bold text-center text-gray-950">{t('uploadDocument')}</span>
                    </Button>
                    
                    <Button 
                      variant="outline" 
                      className="h-auto p-6 flex flex-col items-center space-y-3 min-h-[100px] bg-green-50 hover:bg-green-100 border-green-200"
                    >
                      <MessageSquare className="w-8 h-8 text-green-500" />
                      <span className="text-sm font-bold text-center text-gray-950">{t('newConversation')}</span>
                    </Button>
                    
                    <Button 
                      variant="outline" 
                      className="h-auto p-6 flex flex-col items-center space-y-3 min-h-[100px] bg-purple-50 hover:bg-purple-100 border-purple-200"
                    >
                      <BarChart3 className="w-8 h-8 text-purple-500" />
                      <span className="text-sm font-bold text-center text-gray-950">{t('dataAnalysis')}</span>
                    </Button>
                    
                    <Button 
                      variant="outline" 
                      className="h-auto p-6 flex flex-col items-center space-y-3 min-h-[100px] bg-orange-50 hover:bg-orange-100 border-orange-200"
                    >
                      <Database className="w-8 h-8 text-orange-500" />
                      <span className="text-sm font-bold text-center text-gray-950">{t('knowledgeGraph')}</span>
                    </Button>
                  </div>
                </div>
                </div>
              </div>

              {/* 系统资源监控 - 仅管理员可见 */}
              {isAdmin() && (
                <div className="rounded-2xl border ${isDarkMode ? 'bg-[#343541]' : 'bg-white'} ${isDarkMode ? 'border-gray-700' : 'border-gray-100'} shadow-sm">
                  <div className="p-6 border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-100'}">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="text-lg font-black text-gray-950">{t('systemStatus')}</h2>
                        <p className="text-sm font-medium text-gray-800">
                          {t('realTimeMonitoring')}
                        </p>
                      </div>
                      <span className="text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-700">
                        {currentLanguage === 'zh-CN' ? '管理员专用' : 'Admin Only'}
                      </span>
                    </div>
                  </div>
                  
                  <div className="p-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Cpu className="w-4 h-4 text-blue-500" />
                        <span className="text-sm">{t('cpuUsage')}</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <div className="w-16 h-1.5 rounded-full bg-gray-200">
                          <div className="w-3/4 h-full rounded-full bg-blue-500" />
                        </div>
                        <span className="text-sm font-medium">75%</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <HardDrive className="w-4 h-4 text-green-500" />
                        <span className="text-sm">{t('memoryUsage')}</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <div className="w-16 h-1.5 rounded-full bg-gray-200">
                          <div className="w-1/2 h-full rounded-full bg-green-500" />
                        </div>
                        <span className="text-sm font-medium">45%</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Server className="w-4 h-4 text-purple-500" />
                        <span className="text-sm">{t('gpuLoad')}</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <div className="w-16 h-1.5 rounded-full bg-gray-200">
                          <div className="w-5/6 h-full rounded-full bg-purple-500" />
                        </div>
                        <span className="text-sm font-medium">85%</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Wifi className="w-4 h-4 text-orange-500" />
                        <span className="text-sm">{t('networkLatency')}</span>
                      </div>
                      <span className="text-sm font-medium text-green-600">12ms</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
          
          {/* 页脚信息 */}
          <footer className="mt-12 pt-8 border-t border-border/50">
            <div className="flex flex-col sm:flex-row justify-between items-center space-y-4 sm:space-y-0">
              <div className="text-xs font-medium text-gray-600 dark:text-gray-400">
                © 2024 Lumidoc {t('intelligentWorkbench')} • {currentLanguage === 'zh-CN' ? '版本' : 'Version'} v2.1.0 • {currentLanguage === 'zh-CN' ? '最后更新' : 'Last updated'}: {new Date().toLocaleDateString(currentLanguage === 'zh-CN' ? 'zh-CN' : 'en-US')}
              </div>
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full" />
                  <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                    {currentLanguage === 'zh-CN' ? '系统正常运行' : 'System running normally'}
                  </span>
                </div>
                <div className="text-xs font-medium text-gray-600 dark:text-gray-400">
                  {currentLanguage === 'zh-CN' ? '在线用户' : 'Online users'}: {user ? '1' : '0'}
                </div>
              </div>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}
