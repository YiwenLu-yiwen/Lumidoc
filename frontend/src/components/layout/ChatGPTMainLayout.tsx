import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  MessageSquare,
  Plus,
  Search,
  MoreHorizontal,
  Star,
  StarOff,
  FolderOpen,
  BarChart3,
  Database,
  Brain,
  Users,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  Monitor,
  LogOut
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar } from '@/components/ui/avatar';
import { useAuth } from '@/context/AuthContext';
import { useProjects } from '@/context/ProjectContext';
import { ChatGPTInterface } from '@/components/chat/ChatGPTInterface';
import { ModernDashboard } from '@/components/dashboard/ModernDashboard';
import { detectAutoTheme } from '@/utils/language';

// 使用现有的设计 tokens
const DESIGN_TOKENS = {
  spacing: {
    xs: '0.5rem',
    sm: '0.75rem', 
    md: '1rem',
    lg: '1.5rem',
    xl: '2rem',
    '2xl': '3rem',
  },
  colors: {
    sidebar: 'bg-gray-50 dark:bg-gray-900',
    sidebarBorder: 'border-gray-200 dark:border-gray-800',
    chatBackground: 'bg-white dark:bg-gray-950',
    hover: 'hover:bg-gray-100 dark:hover:bg-gray-800',
    active: 'bg-gray-200 dark:bg-gray-700',
    text: {
      primary: 'text-gray-900 dark:text-gray-100',
      secondary: 'text-gray-600 dark:text-gray-400',
      muted: 'text-gray-500 dark:text-gray-500'
    }
  },
  shadows: {
    sm: 'shadow-sm',
    md: 'shadow-md',
    lg: 'shadow-lg shadow-black/5'
  }
};

interface ChatSession {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  isStarred?: boolean;
  messageCount?: number;
  projectId?: string;
}

interface NavigationItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  path: string;
  badge?: string | number;
  isActive?: boolean;
}

type ActiveView = 'chat' | 'dashboard' | 'files' | 'graph' | 'projects' | 'settings';
type ThemeMode = 'light' | 'dark' | 'auto';

interface ChatHistoryItem {
  id?: string;
  role?: 'user' | 'assistant' | string;
  content?: string;
  timestamp?: string;
}

export default function ChatGPTMainLayout({ children }: { children?: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, token, logout } = useAuth();
  const { projects } = useProjects();
  const currentProject = projects[0] ?? null;
  
  // 状态管理
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeView, setActiveView] = useState<ActiveView>('chat');
  const [selectedChatId, setSelectedChatId] = useState('1');
  const [searchQuery, setSearchQuery] = useState('');
  const [themeMode, setThemeMode] = useState<ThemeMode>('auto');
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  // 导航项配置
  const navigationItems: NavigationItem[] = [
    {
      id: 'chat',
      label: '智能对话',
      icon: <MessageSquare className="w-5 h-5" />,
      path: '/chat',
      isActive: activeView === 'chat'
    },
    {
      id: 'dashboard', 
      label: 'Dashboard',
      icon: <BarChart3 className="w-5 h-5" />,
      path: '/dashboard',
      isActive: activeView === 'dashboard'
    },
    {
      id: 'files',
      label: '文件管理',
      icon: <FolderOpen className="w-5 h-5" />,
      path: '/files',
      badge: '12',
      isActive: activeView === 'files'
    },
    {
      id: 'graph',
      label: '知识图谱',
      icon: <Database className="w-5 h-5" />,
      path: '/graph',
      isActive: activeView === 'graph'
    },
    {
      id: 'projects',
      label: '项目管理',
      icon: <Users className="w-5 h-5" />,
      path: '/projects',
      isActive: activeView === 'projects'
    }
  ];

  const getStoredUserId = (): string | undefined => {
    try {
      const raw = localStorage.getItem('lumidoc_user');
      if (!raw) return undefined;
      const parsed = JSON.parse(raw) as { id?: string };
      return parsed.id;
    } catch {
      return undefined;
    }
  };

  // 根据URL同步当前激活视图，避免刷新后导航状态错位
  useEffect(() => {
    const path = location.pathname.toLowerCase();
    if (path.includes('/dashboard')) {
      setActiveView('dashboard');
    } else if (path.includes('/files')) {
      setActiveView('files');
    } else if (path.includes('/graph')) {
      setActiveView('graph');
    } else if (path.includes('/projects')) {
      setActiveView('projects');
    } else if (path.includes('/settings')) {
      setActiveView('settings');
    } else {
      setActiveView('chat');
    }
  }, [location.pathname]);

  // 从真实聊天历史构建侧边栏会话列表
  useEffect(() => {
    const fetchChatSessions = async () => {
      if (activeView !== 'chat') return;
      if (!token) {
        setChatSessions([]);
        setSessionsError('未检测到登录令牌');
        return;
      }
      if (!currentProject?.id) {
        setChatSessions([]);
        setSessionsError('请先创建或选择项目');
        return;
      }

      const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
      const targetProjectId = currentProject.id;
      const userId = user?.id || getStoredUserId() || 'unknown';
      const historyUrl = `${gatewayUrl}/chat/api/chat/history/${targetProjectId}?user_id=${userId}&include_archived=false&offset=0&limit=200`;

      setSessionsLoading(true);
      setSessionsError(null);

      try {
        const response = await fetch(historyUrl, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (!response.ok) {
          throw new Error(`会话加载失败: HTTP ${response.status}`);
        }

        const data = await response.json();
        const historyItems: ChatHistoryItem[] = Array.isArray(data) ? data : [];

        const safeDate = (value?: string): Date => {
          if (!value) return new Date();
          const d = new Date(value);
          return Number.isNaN(d.getTime()) ? new Date() : d;
        };

        const compact = (text?: string): string => (text || '').replace(/\s+/g, ' ').trim();
        const toTitle = (text?: string): string => {
          const normalized = compact(text);
          if (!normalized) return '新对话';
          return normalized.length > 22 ? `${normalized.slice(0, 22)}...` : normalized;
        };

        const sorted = historyItems
          .map((item, index) => ({
            ...item,
            _index: index,
            _date: safeDate(item.timestamp)
          }))
          .sort((a, b) => b._date.getTime() - a._date.getTime());

        const userMessages = sorted.filter((item) => item.role === 'user' && compact(item.content));

        const sessions: ChatSession[] = (userMessages.length > 0 ? userMessages : sorted)
          .slice(0, 30)
          .map((item, index) => ({
            id: String(item.id || `${targetProjectId}-${item._index || index}`),
            title: toTitle(item.content),
            lastMessage: compact(item.content) || '（空消息）',
            timestamp: item._date,
            messageCount: userMessages.length > 0 ? userMessages.length : sorted.length,
            projectId: targetProjectId
          }));

        setChatSessions(sessions);
      } catch (error: unknown) {
        console.error('[ChatGPTMainLayout] 加载会话失败:', error);
        setChatSessions([]);
        setSessionsError(error instanceof Error ? error.message : '加载会话失败');
      } finally {
        setSessionsLoading(false);
      }
    };

    fetchChatSessions();
  }, [activeView, currentProject?.id, token, user?.id]);

  // 当会话列表变化时，保证选择项有效
  useEffect(() => {
    if (chatSessions.length === 0) return;
    if (!chatSessions.some((session) => session.id === selectedChatId)) {
      setSelectedChatId(chatSessions[0].id);
    }
  }, [chatSessions, selectedChatId]);

  // 过滤聊天会话
  const filteredSessions = chatSessions.filter(session =>
    session.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    session.lastMessage.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // 格式化时间显示
  const formatTime = (date: Date) => {
    const now = new Date();
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);
    
    if (diffInHours < 24) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    } else if (diffInHours < 48) {
      return '昨天';
    } else {
      return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    }
  };

  // 切换主题
  const toggleTheme = () => {
    const themes: ThemeMode[] = ['light', 'dark', 'auto'];
    const currentIndex = themes.indexOf(themeMode);
    const nextTheme = themes[(currentIndex + 1) % themes.length];
    setThemeMode(nextTheme);
    if (nextTheme === 'auto') {
      detectAutoTheme();
    }
  };

  // 主题图标
  const getThemeIcon = () => {
    switch (themeMode) {
      case 'light': return <Sun className="w-4 h-4" />;
      case 'dark': return <Moon className="w-4 h-4" />;
      case 'auto': return <Monitor className="w-4 h-4" />;
    }
  };

  // 渲染聊天会话项
  const renderChatSession = (session: ChatSession) => (
    <div
      key={session.id}
      onClick={() => setSelectedChatId(session.id)}
      className={`
        group relative p-3 rounded-lg cursor-pointer transition-all duration-200
        ${selectedChatId === session.id 
          ? `${DESIGN_TOKENS.colors.active} ${DESIGN_TOKENS.shadows.sm}` 
          : DESIGN_TOKENS.colors.hover
        }
      `}
    >
      {/* 会话内容 */}
      <div className="flex items-start justify-between mb-2">
        <h4 className={`font-medium text-sm ${DESIGN_TOKENS.colors.text.primary} line-clamp-1`}>
          {session.title}
        </h4>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button
            size="sm"
            variant="ghost"
            className="w-6 h-6 p-0"
            onClick={(e) => {
              e.stopPropagation();
              // 收藏逻辑
            }}
          >
            {session.isStarred ? (
              <Star className="w-3 h-3 fill-yellow-400 text-yellow-400" />
            ) : (
              <StarOff className="w-3 h-3" />
            )}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="w-6 h-6 p-0"
            onClick={(e) => {
              e.stopPropagation();
              // 更多选项
            }}
          >
            <MoreHorizontal className="w-3 h-3" />
          </Button>
        </div>
      </div>

      <p className={`text-xs ${DESIGN_TOKENS.colors.text.muted} line-clamp-2 mb-2`}>
        {session.lastMessage}
      </p>

      <div className="flex items-center justify-between text-xs">
        <span className={DESIGN_TOKENS.colors.text.muted}>
          {formatTime(session.timestamp)}
        </span>
        {session.messageCount && (
          <span className={`${DESIGN_TOKENS.colors.text.muted} bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full`}>
            {session.messageCount}
          </span>
        )}
      </div>
    </div>
  );

  // 渲染导航项
  const renderNavigationItem = (item: NavigationItem) => (
    <Button
      key={item.id}
      variant="ghost"
      size="sm"
      className={`
        w-full justify-start gap-3 h-10 px-3
        ${item.isActive 
          ? `${DESIGN_TOKENS.colors.active} font-medium` 
          : DESIGN_TOKENS.colors.hover
        }
      `}
      onClick={() => {
        setActiveView(item.id as ActiveView);
        navigate(item.path);
      }}
    >
      {item.icon}
      {!sidebarCollapsed && (
        <>
          <span className="flex-1 text-left">{item.label}</span>
          {item.badge && (
            <span className="bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300 text-xs px-2 py-0.5 rounded-full">
              {item.badge}
            </span>
          )}
        </>
      )}
    </Button>
  );

  // 渲染主内容区域
  const renderMainContent = () => {
    switch (activeView) {
      case 'dashboard':
        return <ModernDashboard />;
      case 'chat':
      default:
        return (
          <div className="flex-1 flex flex-col h-full">
            <ChatGPTInterface />
          </div>
        );
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* 左侧边栏 */}
      <div className={`
        ${sidebarCollapsed ? 'w-16' : 'w-80'} 
        ${DESIGN_TOKENS.colors.sidebar} 
        ${DESIGN_TOKENS.colors.sidebarBorder} 
        border-r transition-all duration-300 flex flex-col
      `}>
        {/* 顶部区域 */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
          {!sidebarCollapsed && (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center">
                <Brain className="w-5 h-5 text-white" />
              </div>
              <h1 className={`font-bold text-lg ${DESIGN_TOKENS.colors.text.primary}`}>
                Lumidoc
              </h1>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="w-8 h-8 p-0"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          >
            {sidebarCollapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </Button>
        </div>

        {/* 新建对话按钮 */}
        {activeView === 'chat' && (
          <div className="p-4">
            <Button
              className="w-full gap-2 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white"
              onClick={() => {
                // 新建对话逻辑
              }}
            >
              <Plus className="w-4 h-4" />
              {!sidebarCollapsed && '新建对话'}
            </Button>
          </div>
        )}

        {/* 聊天会话列表（仅在聊天模式下显示） */}
        {activeView === 'chat' && !sidebarCollapsed && (
          <div className="flex-1 px-4 pb-4 overflow-y-auto">
            {/* 搜索框 */}
            <div className="mb-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  placeholder="搜索对话..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 h-9"
                />
              </div>
            </div>

            {/* 会话列表 */}
            <div className="space-y-2">
              {sessionsLoading && (
                <div className="text-sm text-gray-500 dark:text-gray-400 px-2 py-3">
                  正在加载会话...
                </div>
              )}
              {!sessionsLoading && sessionsError && (
                <div className="text-sm text-red-500 px-2 py-3">
                  {sessionsError}
                </div>
              )}
              {!sessionsLoading && !sessionsError && filteredSessions.length === 0 && (
                <div className="text-sm text-gray-500 dark:text-gray-400 px-2 py-3">
                  暂无历史会话
                </div>
              )}
              {!sessionsLoading && !sessionsError && filteredSessions.map(renderChatSession)}
            </div>
          </div>
        )}

        {/* 导航菜单 */}
        <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-800">
          <div className="space-y-1">
            {navigationItems.map(renderNavigationItem)}
          </div>
        </div>

        {/* 底部用户区域 */}
        <div className="border-t border-gray-200 dark:border-gray-800 p-4">
          <div className="flex items-center gap-3">
            {!sidebarCollapsed && (
              <>
                <Avatar className="w-8 h-8">
                  <img
                    src={user?.avatar || `https://ui-avatars.com/api/?name=${user?.username || 'User'}&background=3b82f6&color=fff`}
                    alt={user?.username || 'User'}
                  />
                </Avatar>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium ${DESIGN_TOKENS.colors.text.primary} truncate`}>
                    {user?.username || '用户'}
                  </p>
                  <p className={`text-xs ${DESIGN_TOKENS.colors.text.muted} truncate`}>
                    {currentProject?.name || '默认项目'}
                  </p>
                </div>
              </>
            )}
            
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="w-8 h-8 p-0"
                onClick={toggleTheme}
                title="切换主题"
              >
                {getThemeIcon()}
              </Button>
              
              {!sidebarCollapsed && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-8 h-8 p-0"
                  title="退出登录"
                  onClick={() => {
                    logout();
                    navigate('/auth');
                  }}
                >
                  <LogOut className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 主内容区域 */}
      <div className={`flex-1 ${DESIGN_TOKENS.colors.chatBackground} flex flex-col`}>
        {children ?? renderMainContent()}
      </div>
    </div>
  );
}
