import React, { useState, useRef, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { 
  MessageSquare, 
  FolderOpen, 
  Database, 
  Settings, 
  ChevronLeft, 
  Plus,
  Trash2,
  Search,
  MoreHorizontal,
  Sun,
  Moon,
  Monitor,
  Globe,
  Brain,
  Zap,
  Check,
  Star,
  Shield,
  BarChart3,
  FileText,
  Menu
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { useProjects } from '@/context/ProjectContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { AccountModal } from '@/components/ui';
import { ModelSelector } from '@/components/model/ModelSelector';
import { useModel } from '@/hooks/useModel';
import { 
  detectBrowserLanguage, 
  detectAutoTheme, 
  saveLanguage, 
  supportedLanguages,
  getTranslation 
} from '@/utils/language';

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
  model?: 'thinking' | 'fast';
}

type ThemeMode = 'light' | 'dark' | 'auto';

// 模拟聊天会话数据
const mockChatSessions: ChatSession[] = [
  {
    id: '1',
    title: '文档分析讨论',
    lastMessage: '请帮我分析这份财务报告...',
    timestamp: new Date('2024-01-15T10:30:00'),
    projectId: 'proj1',
    isStarred: true,
    messageCount: 15,
    model: 'thinking'
  },
  {
    id: '2', 
    title: '代码重构建议',
    lastMessage: '如何优化这段Python代码？',
    timestamp: new Date('2024-01-14T16:45:00'),
    projectId: 'proj2',
    messageCount: 8,
    model: 'fast'
  },
  {
    id: '3',
    title: '新项目规划',
    lastMessage: '我想创建一个新的AI项目...',
    timestamp: new Date('2024-01-13T09:15:00'),
    messageCount: 23,
    model: 'thinking'
  }
];


export default function MainLayout({ children }: MainLayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const saved = localStorage.getItem('stp_sidebar_collapsed');
    return saved ? JSON.parse(saved) : false;
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [showAccountModal, setShowAccountModal] = useState(false);
  const [themeMode, setThemeMode] = useState<ThemeMode>('auto');
  const [currentLanguage, setCurrentLanguage] = useState<string>(detectBrowserLanguage());
  const [showLanguageMenu, setShowLanguageMenu] = useState(false);
  const [chatSessions] = useState<ChatSession[]>(mockChatSessions);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [showStarredOnly, setShowStarredOnly] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false); // 管理员状态
  
  const { user } = useAuth();
  const { projects } = useProjects();
  const { selectedModel, selectModel } = useModel();
  
  // 从路由路径确定当前页面
  const getCurrentSection = () => {
    const path = location.pathname;
    if (path.includes('/dashboard')) return 'dashboard';
    if (path.includes('/documents')) return 'documents';
    if (path.includes('/projects')) return 'projects';
    if (path.includes('/chat')) return 'chat';
    if (path.includes('/rag')) return 'rag';
    if (path.includes('/settings')) return 'settings';
    if (path.includes('/admin')) return 'admin';
    return 'dashboard'; // 默认
  };
  
  const currentSection = getCurrentSection();
  
  const sidebarRef = useRef<HTMLDivElement>(null);
  const languageMenuRef = useRef<HTMLDivElement>(null);

  // 计算实际主题
  const actualTheme = themeMode === 'auto' ? detectAutoTheme() : themeMode;
  const isDarkMode = actualTheme === 'dark';

  // 获取翻译文本的简化函数
  const t = (key: keyof typeof import('@/utils/language').translations['zh-CN']) => 
    getTranslation(currentLanguage, key);

  // 侧边栏导航项
  const navigationItems = [
    {
      key: 'dashboard',
      path: '/app/dashboard',
      label: '控制台',
      icon: BarChart3,
      active: currentSection === 'dashboard'
    },
    {
      key: 'documents',
      path: '/app/documents',
      label: '文档分析',
      icon: FileText,
      active: currentSection === 'documents'
    },
    {
      key: 'chat',
      path: '/app/chat',
      label: t('chat'),
      icon: MessageSquare,
      active: currentSection === 'chat'
    },
    {
      key: 'projects', 
      path: '/app/projects',
      label: t('projects'),
      icon: FolderOpen,
      active: currentSection === 'projects'
    },
    {
      key: 'rag',
      path: '/app/rag',
      label: t('rag'),
      icon: Database,
      active: currentSection === 'rag'
    },
    // 管理员专属导航项
    ...(isAdmin ? [{
      key: 'admin',
      path: '/app/admin',
      label: t('admin'),
      icon: Shield,
      active: currentSection === 'admin'
    }] : []),
    {
      key: 'settings',
      path: '/app/settings',
      label: t('settings'),
      icon: Settings,
      active: currentSection === 'settings'
    }
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
      return currentLanguage === 'zh-CN' ? '昨天' : 'Yesterday';
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
    localStorage.setItem('stp_sidebar_collapsed', JSON.stringify(newCollapsedState));
  };

  // 创建新聊天
  const createNewChat = () => {
    console.log('创建新聊天');
  };

  // 删除聊天会话
  const deleteChatSession = (chatId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    console.log('删除聊天:', chatId);
  };

  // 收藏/取消收藏聊天
  const toggleStarChat = (chatId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    console.log('切换收藏状态:', chatId);
  };

  // 切换语言
  const changeLanguage = (langCode: string) => {
    setCurrentLanguage(langCode);
    setShowLanguageMenu(false);
    saveLanguage(langCode);
  };

  // 切换主题模式
  const toggleThemeMode = () => {
    const modes: ThemeMode[] = ['light', 'dark', 'auto'];
    const currentIndex = modes.indexOf(themeMode);
    const nextIndex = (currentIndex + 1) % modes.length;
    setThemeMode(modes[nextIndex]);
    localStorage.setItem('stp_theme_mode', modes[nextIndex]);
  };

  // 初始化主题模式
  useEffect(() => {
    const savedTheme = localStorage.getItem('stp_theme_mode') as ThemeMode;
    if (savedTheme && ['light', 'dark', 'auto'].includes(savedTheme)) {
      setThemeMode(savedTheme);
    }
  }, []);

  // 确保body的类名与主题同步
  useEffect(() => {
    if (isDarkMode) {
      document.body.classList.add('dark');
    } else {
      document.body.classList.remove('dark');
    }
  }, [isDarkMode]);

  // 检查管理员权限
  useEffect(() => {
    // TODO: 实际应用中应该从用户权限中判断
    setIsAdmin(user?.username === 'admin');
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

  return (
    <div className={`flex flex-col h-screen bg-background text-foreground ${isDarkMode ? 'dark' : ''}`}>
      {/* 统一的顶部导航栏 - 充分利用界面版 */}
      <header className={`border-b transition-colors duration-300 ${
        isDarkMode ? 'border-gray-800 bg-[#171717]' : 'border-gray-200 bg-white'
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
                  title="展开侧边栏"
                >
                  <Menu className="w-5 h-5" />
                </Button>
              ) : (
                /* 展开状态：显示Logo和品牌 */
                <div className="flex items-center space-x-4">
                  <div 
                    className="flex items-center space-x-2 cursor-pointer hover:opacity-80 transition-opacity"
                    onClick={() => navigate('/app/dashboard')}
                  >
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                      isDarkMode ? 'bg-gradient-to-r from-blue-600 to-purple-600' : 'bg-gradient-to-r from-blue-500 to-purple-500'
                    }`}>
                      <MessageSquare className="w-4 h-4 text-white" />
                    </div>
                    <h1 className="text-lg font-semibold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                      Lumidoc Intelligence
                    </h1>
                  </div>
                  
                  {/* 收起按钮 */}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={toggleSidebar}
                    className={`p-1.5 rounded-md transition-colors ${
                      isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                    }`}
                    title="收起侧边栏"
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
                onClick={toggleThemeMode}
                className={`p-1.5 rounded-md transition-colors ${
                  isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                }`}
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
                <div className={`px-2 py-1 rounded-md text-xs font-medium flex items-center space-x-1 ${
                  selectedModel.type === 'thinking'
                    ? isDarkMode ? 'bg-purple-900/30 text-purple-300' : 'bg-purple-100 text-purple-700'
                    : isDarkMode ? 'bg-green-900/30 text-green-300' : 'bg-green-100 text-green-700'
                }`}>
                  {selectedModel.type === 'thinking' ? (
                    <Brain className="w-3 h-3" />
                  ) : (
                    <Zap className="w-3 h-3" />
                  )}
                  <span className="hidden md:inline text-xs">{selectedModel.displayName}</span>
                  <span className="md:hidden text-xs">{selectedModel.type === 'thinking' ? '思考' : '快速'}</span>
                </div>
              )}

              {/* 语言切换 */}
              {currentLanguage !== detectBrowserLanguage() && (
                <div className="relative" ref={languageMenuRef}>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => setShowLanguageMenu(!showLanguageMenu)}
                    className={`p-1.5 rounded-md transition-colors ${
                      isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                    }`}
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
              )}

              {/* 用户菜单 - 充分利用右侧空间 */}
              <Button
                variant="ghost"
                onClick={() => setShowAccountModal(true)}
                className={`flex items-center space-x-3 px-3 py-1.5 rounded-md transition-colors ${
                  isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                }`}
              >
                <div className="hidden sm:block text-right">
                  <p className={`text-xs font-medium ${isDarkMode ? 'text-gray-200' : 'text-gray-800'}`}>
                    {user?.username || t('user')}
                    {isAdmin && <span className="ml-1 text-xs text-yellow-500">Admin</span>}
                  </p>
                  <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                    在线
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
      <div className="flex flex-1 overflow-hidden">
        {/* 左侧边栏 - 优化空间利用 */}
        <div 
          ref={sidebarRef}
          className={`${isDarkMode ? 'bg-[#171717] border-gray-800' : 'bg-white border-gray-200'} border-r transition-all duration-300 flex flex-col ${
            sidebarCollapsed ? 'w-12' : 'w-56'
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
                  onClick={() => navigate(item.path)}
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
                {filteredChatSessions.map((session) => (
                  <div
                    key={session.id}
                    className={`group p-2 rounded-md cursor-pointer transition-all duration-200 ${
                      selectedChatId === session.id 
                        ? `${isDarkMode ? 'bg-gray-700 border-gray-600' : 'bg-blue-50 border-blue-200'} border` 
                        : `hover:${isDarkMode ? 'bg-gray-700' : 'bg-gray-100'}`
                    }`}
                    onClick={() => setSelectedChatId(session.id)}
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
                            {session.model && (
                              <span className={`text-xs px-1.5 py-0.5 rounded flex items-center gap-0.5 ${
                                session.model === 'thinking' 
                                  ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400'
                                  : 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400'
                              }`}>
                                {session.model === 'thinking' ? (
                                  <><Brain className="w-2.5 h-2.5" /> 思考</>
                                ) : (
                                  <><Zap className="w-2.5 h-2.5" /> 快速</>
                                )}
                              </span>
                            )}
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
                          onClick={(e) => deleteChatSession(session.id, e)}
                        >
                          <Trash2 className="w-2.5 h-2.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 项目列表（仅在项目模式显示） */}
        {currentSection === 'projects' && !sidebarCollapsed && (
          <div className="flex-1 overflow-y-auto p-4">
            <div className="space-y-2">
              {projects.map((project) => (
                <div
                  key={project.id}
                  className={`p-3 rounded-lg ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'} cursor-pointer group`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <FolderOpen className="w-4 h-4 text-blue-500" />
                      <span className="font-medium">{project.name}</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="opacity-0 group-hover:opacity-100 p-1 h-6 w-6"
                    >
                      <MoreHorizontal className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        </div>

        {/* 主内容区域 */}
        <div className="flex-1 bg-background">
          {children}
        </div>
      </div>

      {/* 账号模态框 */}
      <AccountModal 
        open={showAccountModal}
        onClose={() => setShowAccountModal(false)}
      />
    </div>
  );
} 