import React, { useState, useRef, useEffect } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { 
  MessageSquare, 
  FolderOpen, 
  Database, 
  Settings, 
  ChevronLeft, 
  Plus,
  Trash2,
  Search,
  Sun,
  Moon,
  Monitor,
  Globe,
  Check,
  Star,
  Shield,
  BarChart3,
  FileText,
  Menu
} from 'lucide-react';
import { deleteConversation } from '@/api/conversations';
import { useAuth } from '@/context/AuthContext';
import { useProjects } from '@/context/ProjectContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import ModernAccountModal from '@/components/ui/ModernAccountModal';
import { ModelSelector } from '@/components/model/ModelSelector';
import { ModelSelectionContext, useModel } from '@/hooks/useModel';
import { 
  supportedLanguages,
} from '@/utils/language';
import { useTheme } from '@/context/ThemeContext';
import { useLanguage } from '@/context/LanguageContext';
import { shouldCollapseSidebar } from './responsiveLayout';

interface MainLayoutProps {
  children: React.ReactNode;
}

interface ChatSession {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  projectId?: string;
  isStarred?: boolean;
  messageCount?: number;
}

export default function MainLayout({ children }: MainLayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();

  const [isCompactLayout, setIsCompactLayout] = useState(() =>
    typeof window !== 'undefined' && shouldCollapseSidebar(window.innerWidth),
  );
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window !== 'undefined' && shouldCollapseSidebar(window.innerWidth)) {
      return true;
    }
    const saved = localStorage.getItem('lumidoc_sidebar_collapsed');
    return saved ? JSON.parse(saved) : false;
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [showAccountModal, setShowAccountModal] = useState(false);
  const { currentLanguage, setLanguage, t } = useLanguage();
  const { themeMode, isDarkMode, toggleTheme } = useTheme();
  const [showLanguageMenu, setShowLanguageMenu] = useState(false);
  const sessionsRequest = useRef(0);
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [, setSelectedChatId] = useState<string | null>(null);
  const [showStarredOnly, setShowStarredOnly] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false); // 管理员状态
  
  const { user, token } = useAuth();
  const { projects } = useProjects();
  const {
    selectedModel,
    availableModels,
    loading: modelsLoading,
    error: modelsError,
    selectModel,
  } = useModel();
  const { projectId } = useParams<{ projectId: string }>();
  const currentProject = projects.find(project => project.id === projectId) ?? null;
  
  // 从路由路径确定当前页面
  const getCurrentSection = () => {
    const path = location.pathname;
    if (path.includes('/dashboard')) return 'dashboard';
    if (path.includes('/documents')) return 'documents';
    if (path.includes('/projects')) return 'projects';
    if (path.includes('/chat')) return 'chat';
    if (path.includes('/rag')) return 'rag';
    if (path.includes('/settings')) return 'settings';
    if (path.includes('/models')) return 'models';
    if (path.includes('/admin')) return 'admin';
    return 'dashboard'; // 默认
  };
  
  const currentSection = getCurrentSection();
  
  const sidebarRef = useRef<HTMLDivElement>(null);
  const languageMenuRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    const fetchChatSessions = async () => {
      if (currentSection !== 'chat') return;
      if (!token) {
        setChatSessions([]);
        setSessionsError(t('loginRequired'));
        return;
      }
      if (!currentProject?.id) {
        setChatSessions([]);
        setSessionsError(t('selectProjectFirst'));
        return;
      }

      const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
      const userId = user?.id || getStoredUserId() || 'unknown';
      const historyUrl = `${gatewayUrl}/chat/api/chat/conversations/${currentProject.id}?user_id=${userId}`;

      const requestVersion = ++sessionsRequest.current;
      setSessionsLoading(true);
      setSessionsError(null);

      try {
        const response = await fetch(historyUrl, {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${token}`
          }
        });
        if (!response.ok) {
          throw new Error(`${t('sessionLoadFailed')}: HTTP ${response.status}`);
        }

        const data = await response.json();
        if (requestVersion !== sessionsRequest.current) return;
        const sessions: ChatSession[] = (Array.isArray(data) ? data : []).map(item => ({
          ...item,
          timestamp: new Date(item.timestamp),
          projectId: currentProject.id,
        }));

        setChatSessions(sessions);
      } catch (error: unknown) {
        if (requestVersion !== sessionsRequest.current) return;
        console.error('[MainLayout] 加载会话失败:', error);
        setChatSessions([]);
        setSessionsError(error instanceof Error ? error.message : t('sessionLoadFailed'));
      } finally {
        if (requestVersion === sessionsRequest.current) setSessionsLoading(false);
      }
    };

    void fetchChatSessions();
    const refresh = () => { void fetchChatSessions(); };
    window.addEventListener('chat-updated', refresh);
    return () => { sessionsRequest.current++; window.removeEventListener('chat-updated', refresh); };
  }, [location.search, currentLanguage, currentProject?.id, currentSection, t, token, user?.id]);

  // 主题状态现在由 ThemeContext 管理

  // 侧边栏导航项
  const zh = currentLanguage === 'zh-CN';
  const navigationItems = [
    {key:'home',path:'/app/dashboard',label:zh ? '所有项目' : 'All projects',icon:FolderOpen,active:!projectId && ['dashboard','projects'].includes(currentSection)},
    ...(projectId ? [
      {key:'dashboard',path:`/project/${projectId}/dashboard`,label:zh ? '项目总览' : 'Project overview',icon:BarChart3,active:currentSection==='dashboard'},
      {key:'documents',path:`/project/${projectId}/documents`,label:t('documentAnalysis'),icon:FileText,active:currentSection==='documents'},
      {key:'rag',path:`/project/${projectId}/rag`,label:t('rag'),icon:Database,active:currentSection==='rag'},
      {key:'chat',path:`/project/${projectId}/chat`,label:t('chat'),icon:MessageSquare,active:currentSection==='chat'},
    ] : []),
    {key:'models',path:'/app/models',label:zh ? '模型管理' : 'Models',icon:Monitor,active:currentSection==='models'},
    ...(isAdmin ? [{key:'admin',path:'/app/admin',label:t('admin'),icon:Shield,active:currentSection==='admin'}] : []),
    {key:'settings',path:'/app/settings',label:t('settings'),icon:Settings,active:currentSection==='settings'},
  ];

  // 过滤聊天会话
  const filteredChatSessions = chatSessions
    .filter(session => {
      const matchesSearch = session.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          session.lastMessage.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStarred = !showStarredOnly || session.isStarred;
      return matchesSearch && matchesStarred;
    })
    .sort((a, b) => {
      const cutoff = Date.now() - 30 * 86400000;
      const archiveOrder = Number(a.timestamp.getTime() < cutoff) - Number(b.timestamp.getTime() < cutoff);
      if (archiveOrder) return archiveOrder;
      // 置顶收藏的对话
      if (a.isStarred && !b.isStarred) return -1;
      if (!a.isStarred && b.isStarred) return 1;
      return b.timestamp.getTime() - a.timestamp.getTime();
    });

  // 格式化时间
  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) {
      return date.toLocaleTimeString(currentLanguage, { hour: '2-digit', minute: '2-digit' });
    } else if (days === 1) {
      return t('yesterday');
    } else if (days < 7) {
      return currentLanguage === 'zh-CN' ? `${days}天前` : `${days}d ago`;
    } else {
      return date.toLocaleDateString(currentLanguage, { month: 'short', day: 'numeric' });
    }
  };

  // 切换侧边栏
  const toggleSidebar = () => {
    const newCollapsedState = !sidebarCollapsed;
    setSidebarCollapsed(newCollapsedState);
    if (!isCompactLayout) {
      localStorage.setItem('lumidoc_sidebar_collapsed', JSON.stringify(newCollapsedState));
    }
  };

  const navigateFromSidebar = (path: string) => {
    const section = path.split('/').pop();
    const conversation = projectId ? sessionStorage.getItem(`lumidoc-conversation:${projectId}`) : null;
    navigate(section === 'chat' && conversation ? `${path}?conversation=${encodeURIComponent(conversation)}` : path);
    if (isCompactLayout) setSidebarCollapsed(true);
  };

  // 创建新聊天
  const createNewChat = () => {
    setSelectedChatId(null);
    const path = currentProject ? `/project/${currentProject.id}/chat` : '/app/chat';
    navigate(`${path}?conversation=${crypto.randomUUID()}`);
  };

  // 删除聊天会话
  const deleteChatSession = async (chatId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!currentProject || deletingChatId) return;
    if (!confirm(currentLanguage === 'zh-CN' ? '确定要删除这个会话吗？' : 'Delete this conversation?')) return;
    setDeletingChatId(chatId);
    try {
      await deleteConversation(currentProject.id, chatId);
      setChatSessions(prev => prev.filter(session => session.id !== chatId));
    } catch (error) {
      setSessionsError(error instanceof Error ? error.message : '会话删除失败');
    } finally {
      setDeletingChatId(null);
    }
  };

  // 收藏/取消收藏聊天
  const toggleStarChat = (chatId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setChatSessions((prev) =>
      prev.map((session) =>
        session.id === chatId
          ? { ...session, isStarred: !session.isStarred }
          : session
      )
    );
  };

  // 切换语言
  const changeLanguage = (langCode: string) => {
    setLanguage(langCode);
    setShowLanguageMenu(false);
  };

  // 主题切换现在由 ThemeContext 管理

  // 主题初始化现在由 ThemeContext 管理

  // 检查管理员权限
  useEffect(() => {
    setIsAdmin(user?.role === 'admin');
  }, [user]);

  // 点击外部关闭语言菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (languageMenuRef.current && !languageMenuRef.current.contains(event.target as Node)) {
        setShowLanguageMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const handleResize = () => {
      const compact = shouldCollapseSidebar(window.innerWidth);
      setIsCompactLayout(compact);
      if (compact) {
        setSidebarCollapsed(true);
        return;
      }

      const saved = localStorage.getItem('lumidoc_sidebar_collapsed');
      setSidebarCollapsed(saved ? JSON.parse(saved) : false);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className={`flex flex-col h-dvh overflow-hidden bg-background text-foreground ${isDarkMode ? 'dark' : ''}`}>
      {/* 统一的顶部导航栏 - 充分利用界面版 */}
      <header className={`border-b transition-colors duration-300 ${
        isDarkMode ? 'border-gray-800 bg-[#343541]' : 'border-gray-200 bg-white'
      }`}>
        <div className="w-full px-2 sm:px-3">
          <div className="flex justify-between items-center h-12">
            {/* 左侧：动态显示Logo或汉堡菜单 */}
            <div className="flex items-center">
              {sidebarCollapsed ? (
                /* 收起状态：只显示汉堡菜单 */
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={toggleSidebar}
                  className={`p-2 rounded-md transition-colors ${
                    isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                  }`}
                  title={t('expandSidebar')}
                  aria-label={t('expandSidebar')}
                >
                  <Menu className="w-5 h-5" />
                </Button>
              ) : (
                /* 展开状态：显示Logo和品牌 */
                  <div className="flex items-center space-x-4">
                  <button
                    type="button"
                    className="flex items-center space-x-2 !border-0 !bg-transparent !p-0 text-left hover:opacity-80"
                    onClick={() => navigate('/app/dashboard')}
                    aria-label={t('intelligentWorkbench')}
                  >
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                      isDarkMode ? 'bg-gradient-to-r from-blue-600 to-purple-600' : 'bg-gradient-to-r from-blue-500 to-purple-500'
                    }`}>
                      <MessageSquare className="w-4 h-4 text-white" />
                    </div>
                    <span className="text-lg font-semibold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                      Lumidoc Intelligence
                    </span>
                  </button>
                  
                  {/* 收起按钮 */}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={toggleSidebar}
                    className={`p-1.5 rounded-md transition-colors ${
                      isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                    }`}
                    title={t('collapseSidebar')}
                    aria-label={t('collapseSidebar')}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                </div>
              )}
            </div>

            {/* 右侧：工具和用户操作 - 更靠右 */}
            <div className="flex items-center space-x-2">
              {/* 主题切换 */}
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleTheme}
                className={`p-1.5 rounded-md transition-colors ${
                  isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                }`}
                title={themeMode === 'light' ? t('lightMode') : themeMode === 'dark' ? t('darkMode') : t('autoMode')}
                aria-label={themeMode === 'light' ? t('lightMode') : themeMode === 'dark' ? t('darkMode') : t('autoMode')}
              >
                {themeMode === 'light' ? (
                  <Sun className="w-4 h-4" />
                ) : themeMode === 'dark' ? (
                  <Moon className="w-4 h-4" />
                ) : (
                  <Monitor className="w-4 h-4" />
                )}
              </Button>

              {/* 当前模型指示器 - 精简版 */}
              {selectedModel && (
                <div className={`px-2 py-1 rounded-md text-xs font-medium ${
                  isDarkMode ? 'bg-gray-800 text-gray-300' : 'bg-gray-100 text-gray-700'
                }`}>
                  <span className="text-xs">{selectedModel.displayName}</span>
                </div>
              )}

              {/* 语言切换 */}
              <div className="relative" ref={languageMenuRef}>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => setShowLanguageMenu(!showLanguageMenu)}
                    className={`p-1.5 rounded-md transition-colors ${
                      isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                    }`}
                    title={t('language')}
                    aria-label={t('language')}
                  >
                    <Globe className="w-4 h-4" />
                  </Button>
                  {showLanguageMenu && (
                    <div className={`absolute right-0 top-full mt-1 w-44 py-1 rounded-lg shadow-xl z-50 ${
                      isDarkMode ? 'bg-[#2a2a2a] border border-gray-700' : 'bg-white border border-gray-200'
                    }`}>
                      {supportedLanguages.map((lang) => (
                        <button
                          key={lang.code}
                          onClick={() => changeLanguage(lang.code)}
                          className={`w-full px-3 py-1.5 text-left flex items-center space-x-2 transition-colors ${
                            currentLanguage === lang.code
                              ? isDarkMode ? 'bg-gray-700 text-white' : 'bg-gray-100 text-gray-900'
                              : isDarkMode ? 'hover:bg-gray-700 text-gray-300' : 'hover:bg-gray-100 text-gray-600'
                          }`}
                        >
                          <span className="text-sm">{lang.flag}</span>
                          <span className="text-xs">{lang.name}</span>
                          {currentLanguage === lang.code && (
                            <Check className="w-3 h-3 ml-auto" />
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

              {/* 用户菜单 - 充分利用右侧空间 */}
              <Button
                variant="ghost"
                onClick={() => setShowAccountModal(true)}
                className={`flex items-center space-x-3 px-3 py-1.5 rounded-md transition-colors ${
                  isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                }`}
                aria-label={t('manageAccount')}
              >
                <div className="hidden sm:block text-right">
                  <p className={`text-xs font-medium ${isDarkMode ? 'text-gray-200' : 'text-gray-800'}`}>
                    {user?.username || t('user')}
                    {isAdmin && <span className="ml-1 text-xs text-yellow-500">Admin</span>}
                  </p>
                  <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                    {user?.email || (zh ? '账户设置' : 'Account settings')}
                  </p>
                </div>
                <div className={`w-7 h-7 ${isDarkMode ? 'bg-gray-600' : 'bg-gray-300'} rounded-full flex items-center justify-center text-sm font-medium ${isDarkMode ? 'text-white' : 'text-gray-700'} relative`}>
                  {user?.username?.charAt(0).toUpperCase() || 'U'}
                  {isAdmin && <Shield className="w-2.5 h-2.5 absolute -top-1 -right-1 text-yellow-500" />}
                  <div className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-green-500 rounded-full border-2 ${isDarkMode ? 'border-[#171717]' : 'border-white'}`}></div>
                </div>
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* 主要内容区域 */}
      {projectId && <div className="flex items-center gap-3 border-b px-3 py-2 bg-background">
        <label htmlFor="workspace-project" className="text-sm shrink-0">{zh ? '当前项目' : 'Current project'}</label>
        <select id="workspace-project" value={projectId} className="min-w-0 max-w-sm flex-1 rounded-md border bg-background px-2 py-1 text-sm" onChange={event => {
          const section = ['documents','rag','chat'].includes(currentSection) ? currentSection : 'dashboard';
          navigate(`/project/${event.target.value}/${section}`);
        }}>
          {!currentProject && <option value={projectId}>{zh ? '正在加载项目…' : 'Loading project…'}</option>}
          {projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
        <button className="text-sm underline shrink-0" onClick={() => navigate('/app/projects')}>{zh ? '所有项目' : 'All projects'}</button>
      </div>}

      <div className="relative flex min-h-0 flex-1 overflow-hidden">
        {isCompactLayout && !sidebarCollapsed && (
          <button
            type="button"
            className="absolute inset-0 z-30 !rounded-none !border-0 bg-black/40 !p-0"
            onClick={() => setSidebarCollapsed(true)}
            aria-label={t('collapseSidebar')}
          />
        )}
        {/* 左侧边栏 - 优化空间利用 */}
        <div 
          ref={sidebarRef}
          className={`${isDarkMode ? 'bg-background border-border' : 'bg-background border-border'} flex flex-col transition-all duration-300 ${
            isCompactLayout
              ? sidebarCollapsed
                ? 'w-0 overflow-hidden border-r-0'
                : 'absolute inset-y-0 left-0 z-40 w-64 border-r shadow-xl'
              : sidebarCollapsed
                ? 'w-12 shrink-0 border-r'
                : 'w-56 shrink-0 border-r'
          }`}
        >

          {/* 导航菜单 - 紧凑布局 */}
          <div className={`p-2 border-b ${isDarkMode ? 'border-gray-800' : 'border-gray-200'}`}>
          <div className="space-y-1">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              return (
                <Button
                  key={item.key}
                  variant="ghost"
                  size="sm"
                  className={`w-full justify-start h-9 ${sidebarCollapsed ? 'px-1.5' : 'px-3'} text-sm ${
                    item.active 
                      ? isDarkMode
                        ? 'bg-gray-800 text-white'
                        : 'bg-gray-200 text-gray-900'
                      : isDarkMode
                        ? 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  }`}
                  onClick={() => navigateFromSidebar(item.path)}
                  title={sidebarCollapsed ? item.label : undefined}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  {!sidebarCollapsed && <span className="ml-2 truncate">{item.label}</span>}
                </Button>
              );
            })}
          </div>
        </div>

        {/* 聊天会话列表（仅在聊天模式显示） - 紧凑布局 */}
        {currentSection === 'chat' && !sidebarCollapsed && (
          <div className="flex-1 flex flex-col">
            {/* 新建聊天按钮 - 紧凑版 */}
            <div className={`p-2 border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
              <Button 
                onClick={createNewChat}
                size="sm"
                className="w-full justify-start h-8 text-xs bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0"
              >
                <Plus className="w-3 h-3 mr-2" />
                {t('newChat')}
              </Button>
            </div>

            {/* 模型选择器 - 紧凑版 */}
            <div className={`p-2 border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
              <div className="mb-1">
                <label className={`text-xs font-medium ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                  {t('modelList')}
                </label>
              </div>
              <ModelSelector
                selectedModel={selectedModel}
                onModelSelect={selectModel}
                models={availableModels}
                loading={modelsLoading}
                error={modelsError}
                className="w-full text-xs"
              />
            </div>

            {/* 搜索框和过滤器 - 紧凑版 */}
            <div className={`p-2 border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-200'} space-y-2`}>
              <div className="relative">
                <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 text-gray-400 w-3 h-3" />
                <Input
                  placeholder={t('searchChats')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className={`pl-7 h-7 text-xs ${isDarkMode ? 'bg-gray-700 border-gray-600' : 'bg-white border-gray-300'}`}
                />
              </div>
              {/* 过滤按钮 */}
              <div className="flex items-center gap-1">
                <Button
                  variant={showStarredOnly ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setShowStarredOnly(!showStarredOnly)}
                  className="text-xs h-6 px-2"
                >
                  <Star className="w-3 h-3 mr-1" />
                  {t('starred')}
                </Button>
              </div>
            </div>

            {/* 聊天会话列表 - 紧凑布局 */}
            <div className="flex-1 overflow-y-auto">
              <div className="p-1 space-y-0.5">
                {sessionsLoading && (
                  <div className={`px-2 py-3 text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                    正在加载会话...
                  </div>
                )}
                {!sessionsLoading && sessionsError && (
                  <div className="px-2 py-3 text-xs text-red-500">
                    {sessionsError}
                  </div>
                )}
                {!sessionsLoading && !sessionsError && filteredChatSessions.length === 0 && (
                  <div className={`px-2 py-3 text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                    暂无历史会话
                  </div>
                )}
                {!sessionsLoading && !sessionsError && filteredChatSessions.map((session, index) => (
                  <React.Fragment key={session.id}>
                  {(index === 0 || (Date.now() - filteredChatSessions[index - 1].timestamp.getTime() > 30 * 86400000) !== (Date.now() - session.timestamp.getTime() > 30 * 86400000)) && (
                    <div className="px-2 pt-3 pb-1 text-xs text-gray-500">
                      {Date.now() - session.timestamp.getTime() > 30 * 86400000
                        ? (currentLanguage === 'zh-CN' ? '已归档会话' : 'Archived conversations')
                        : (currentLanguage === 'zh-CN' ? '最近会话' : 'Recent conversations')}
                    </div>
                  )}
                  <div
                    key={session.id}
                    className={`group p-2 rounded-md cursor-pointer transition-all duration-200 ${
                      (new URLSearchParams(location.search).get('conversation') || sessionStorage.getItem(`lumidoc-conversation:${currentProject?.id || 'default'}`) || 'legacy') === session.id
                        ? `${isDarkMode ? 'bg-gray-700 border-gray-600' : 'bg-blue-50 border-blue-200'} border`
                        : `hover:${isDarkMode ? 'bg-gray-700' : 'bg-gray-100'}`
                    }`}
                    onClick={() => {
                      setSelectedChatId(session.id);
                      navigate(`/project/${session.projectId}/chat?conversation=${encodeURIComponent(session.id)}`);
                    }}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1 mb-1">
                          <h3 className="font-medium text-xs truncate flex-1">
                            {session.title}
                          </h3>
                          {session.isStarred && (
                            <Star className="w-2.5 h-2.5 text-yellow-500 fill-current" />
                          )}
                        </div>
                        <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-500'} truncate mb-1 leading-tight`}>
                          {session.lastMessage}
                        </p>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1">
                            <span className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                              {formatTime(session.timestamp)}
                            </span>

                          </div>
                          {session.messageCount && (
                            <span className={`text-xs ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                              {session.messageCount}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="ml-1 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col gap-0.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-1 h-5 w-5"
                          onClick={(e) => toggleStarChat(session.id, e)}
                        >
                          <Star className={`w-2.5 h-2.5 ${session.isStarred ? 'text-yellow-500 fill-current' : ''}`} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-1 h-5 w-5 text-red-500 hover:text-red-600"
                          onClick={(e) => void deleteChatSession(session.id, e)}
                          disabled={deletingChatId !== null}
                          aria-label={`${currentLanguage === 'zh-CN' ? '删除会话' : 'Delete conversation'}: ${session.title}`}
                        >
                          <Trash2 className="w-2.5 h-2.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                  </React.Fragment>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 项目列表（仅在项目模式显示） */}


        </div>

        {/* 主内容区域 */}
        <main className="min-h-0 min-w-0 flex-1 overflow-hidden bg-background">
          <ModelSelectionContext.Provider value={{ selectedModel, selectModel }}>
            {children}
          </ModelSelectionContext.Provider>
        </main>
      </div>

      {/* 账号模态框 */}
      <ModernAccountModal 
        open={showAccountModal}
        onClose={() => setShowAccountModal(false)}
      />
    </div>
  );
}
