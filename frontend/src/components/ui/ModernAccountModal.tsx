import React, { useEffect, useState, useRef } from 'react';
import { 
  User, 
  Settings, 
  Shield, 
  FolderOpen, 
  Plus, 
  Loader2, 
  AlertCircle, 
  LogOut,
  X,
  Mail,
  Bell,
  Globe,
  Monitor,
  Sun,
  Moon
} from 'lucide-react';
import { useAuth, type User as AuthUser } from '@/context/AuthContext';
import { projectApi } from '@/api/project';
import { useNavigate, useLocation } from 'react-router-dom';
import { useProjects } from '@/context/ProjectContext';
import { useTheme } from '@/context/ThemeContext';
import { useLanguage } from '@/context/LanguageContext';

interface Props {
  open: boolean;
  onClose: () => void;
}

// 现代化头像组件
function ModernAvatar({ username, size = 64 }: { username: string, size?: number }) {
  const getInitials = (name: string) => {
    const parts = name.split(' ');
    if (parts.length > 1) {
      return (parts[0]?.charAt(0) + parts[1]?.charAt(0)).toUpperCase();
    }
    return name ? name.slice(0, 2).toUpperCase() : '??';
  };

  const getGradient = (name: string) => {
    const gradients = [
      'from-purple-500 to-pink-500',
      'from-blue-500 to-indigo-500',
      'from-green-500 to-teal-500',
      'from-yellow-500 to-orange-500',
      'from-red-500 to-pink-500',
      'from-indigo-500 to-purple-500',
      'from-teal-500 to-blue-500',
      'from-orange-500 to-red-500',
    ];
    const index = name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return gradients[index % gradients.length];
  };

  return (
    <div
      className={`rounded-full flex items-center justify-center bg-gradient-to-br ${getGradient(username)} text-white font-bold shadow-lg ring-4 ring-white dark:ring-gray-800`}
      style={{
        width: size,
        height: size,
        fontSize: `${size * 0.3}px`,
      }}
    >
      {getInitials(username)}
    </div>
  );
}

// 个人信息卡片
function ProfileCard({ user, isDarkMode }: { user: AuthUser | null, isDarkMode: boolean }) {
  const { currentLanguage, t } = useLanguage();

  return (
    <div className="space-y-6">
      {/* 用户头像和基本信息 */}
      <div className="text-center space-y-4">
        <div className="relative mx-auto w-fit">
          <ModernAvatar username={user?.username || ''} size={80} />
        </div>
        <div>
          <h2 className="text-2xl font-bold">{user?.username}</h2>
          <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            ID: {user?.id?.slice(0, 8)}...
          </p>
        </div>
      </div>

      {/* 用户信息卡片 */}
      <div className="grid gap-4">
        <div className={`p-4 rounded-xl ${
          isDarkMode ? 'bg-gray-800/50' : 'bg-gray-50'
        } border ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className={`p-2 rounded-lg ${
                isDarkMode ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-600'
              }`}>
                <Mail className="w-4 h-4" />
              </div>
              <div>
                <p className="font-medium">{t('emailAddress')}</p>
                <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                  {user?.email || (currentLanguage === 'zh-CN' ? '未提供' : 'Not provided')}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// 设置卡片
function SettingsCard({ isDarkMode }: { isDarkMode: boolean }) {
  const { themeMode, toggleTheme } = useTheme();
  const { currentLanguage, t } = useLanguage();

  const getThemeIcon = () => {
    switch (themeMode) {
      case 'light': return Sun;
      case 'dark': return Moon;
      default: return Monitor;
    }
  };

  const getThemeLabel = () => {
    switch (themeMode) {
      case 'light': return t('lightMode');
      case 'dark': return t('darkMode');
      default: return t('autoMode');
    }
  };

  const ThemeIcon = getThemeIcon();

  return (
    <div className="space-y-4">
      <div className={`p-4 rounded-xl ${
        isDarkMode ? 'bg-gray-800/50' : 'bg-gray-50'
      } border ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${
              isDarkMode ? 'bg-purple-500/20 text-purple-400' : 'bg-purple-100 text-purple-600'
            }`}>
              <ThemeIcon className="w-4 h-4" />
            </div>
            <div>
              <p className="font-medium">{t('themeSettings')}</p>
              <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                {getThemeLabel()}
              </p>
            </div>
          </div>
          <button 
            onClick={toggleTheme}
            className={`px-3 py-1 text-xs rounded-lg ${
              isDarkMode ? 'bg-purple-600 hover:bg-purple-700' : 'bg-purple-500 hover:bg-purple-600'
            } text-white transition-colors`}
          >
            {currentLanguage === 'zh-CN' ? '切换' : 'Switch'}
          </button>
        </div>
      </div>

      <div className={`p-4 rounded-xl ${
        isDarkMode ? 'bg-gray-800/50' : 'bg-gray-50'
      } border ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${
              isDarkMode ? 'bg-orange-500/20 text-orange-400' : 'bg-orange-100 text-orange-600'
            }`}>
              <Bell className="w-4 h-4" />
            </div>
            <div>
              <p className="font-medium">{t('notifications')}</p>
              <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                {currentLanguage === 'zh-CN' ? '管理通知偏好' : 'Manage preferences'}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className={`p-4 rounded-xl ${
        isDarkMode ? 'bg-gray-800/50' : 'bg-gray-50'
      } border ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${
              isDarkMode ? 'bg-teal-500/20 text-teal-400' : 'bg-teal-100 text-teal-600'
            }`}>
              <Globe className="w-4 h-4" />
            </div>
            <div>
              <p className="font-medium">{t('languageSettings')}</p>
              <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                {currentLanguage === 'zh-CN' ? '中文' : 'English'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// 项目管理卡片
function ProjectsCard({ isDarkMode }: { isDarkMode: boolean }) {
  const { projects, refreshProjects } = useProjects();
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [createError, setCreateError] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  const { currentLanguage } = useLanguage();

  const currentProjectId = location.pathname.match(/project\/([\w-]+)/)?.[1];

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) {
      setCreateError(currentLanguage === 'zh-CN' ? '项目名称不能为空' : 'Project name required');
      return;
    }
    setCreateError('');
    setLoading(true);
    try {
      await projectApi.createProject({ name: newProjectName });
      setNewProjectName('');
      setCreating(false);
      await refreshProjects();
    } catch {
      setCreateError(currentLanguage === 'zh-CN' ? '创建失败' : 'Creation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* 创建新项目 */}
      <div className={`p-4 rounded-xl border-2 border-dashed ${
        isDarkMode 
          ? 'border-gray-700 hover:border-blue-500' 
          : 'border-gray-300 hover:border-blue-400'
      } transition-colors`}>
        {!creating ? (
          <button
            className="w-full flex items-center justify-center space-x-2 text-center py-3"
            onClick={() => setCreating(true)}
          >
            <Plus className="w-5 h-5 text-blue-500" />
            <span className="font-medium text-blue-500">
              {currentLanguage === 'zh-CN' ? '创建新项目' : 'Create New Project'}
            </span>
          </button>
        ) : (
          <div className="space-y-3">
            <input
              className={`w-full px-3 py-2 rounded-lg border ${
                isDarkMode 
                  ? 'bg-gray-800 border-gray-700 text-white' 
                  : 'bg-white border-gray-300 text-gray-900'
              } focus:outline-none focus:ring-2 focus:ring-blue-500`}
              placeholder={currentLanguage === 'zh-CN' ? '输入项目名称' : 'Enter project name'}
              value={newProjectName}
              onChange={e => { setNewProjectName(e.target.value); setCreateError(''); }}
              autoFocus
              onKeyDown={e => {
                if (e.key === 'Enter') handleCreateProject();
                if (e.key === 'Escape') { setCreating(false); setNewProjectName(''); setCreateError(''); }
              }}
            />
            {createError && (
              <div className="flex items-center text-red-500 text-sm">
                <AlertCircle className="w-4 h-4 mr-1" /> {createError}
              </div>
            )}
            <div className="flex space-x-2">
              <button
                className={`flex-1 px-3 py-2 rounded-lg ${
                  isDarkMode ? 'bg-blue-600 hover:bg-blue-700' : 'bg-blue-500 hover:bg-blue-600'
                } text-white font-medium transition-colors`}
                onClick={handleCreateProject}
                disabled={loading}
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 
                  (currentLanguage === 'zh-CN' ? '创建' : 'Create')}
              </button>
              <button
                className={`px-3 py-2 rounded-lg border ${
                  isDarkMode 
                    ? 'border-gray-700 hover:bg-gray-800' 
                    : 'border-gray-300 hover:bg-gray-50'
                } transition-colors`}
                onClick={() => { setCreating(false); setNewProjectName(''); setCreateError(''); }}
              >
                {currentLanguage === 'zh-CN' ? '取消' : 'Cancel'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 项目列表 */}
      <div className="space-y-2 max-h-60 overflow-y-auto">
        {projects.map(project => (
          <div key={project.id} className={`p-3 rounded-xl border ${
            project.id === currentProjectId
              ? isDarkMode
                ? 'bg-blue-900/20 border-blue-500'
                : 'bg-blue-50 border-blue-200'
              : isDarkMode
                ? 'bg-gray-800/50 border-gray-700 hover:bg-gray-800'
                : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
          } transition-colors cursor-pointer group`}>
            <div className="flex items-center justify-between">
              <div 
                className="flex items-center space-x-3 flex-1"
                onClick={() => navigate(`/project/${project.id}`)}
              >
                <div className={`p-2 rounded-lg ${
                  project.id === currentProjectId
                    ? 'bg-blue-500 text-white'
                    : isDarkMode
                      ? 'bg-gray-700 text-gray-300'
                      : 'bg-gray-200 text-gray-600'
                }`}>
                  <FolderOpen className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{project.name}</p>
                  <p className={`text-xs ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                    {new Date(project.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            </div>
          </div>
        ))}
        {projects.length === 0 && (
          <div className={`text-center py-8 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
            <FolderOpen className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">{currentLanguage === 'zh-CN' ? '暂无项目' : 'No projects'}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ModernAccountModal({ open, onClose }: Props) {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('profile');
  const modalRef = useRef<HTMLDivElement>(null);
  const { currentLanguage, t } = useLanguage();

  // 主题检测
  const { isDarkMode } = useTheme();

  // 标签页配置
  const tabs = [
    { 
      key: 'profile', 
      label: t('profile'),
      icon: User,
      description: currentLanguage === 'zh-CN' ? '个人信息和账户设置' : 'Personal info and account settings'
    },
    { 
      key: 'settings', 
      label: t('settings'),
      icon: Settings,
      description: currentLanguage === 'zh-CN' ? '偏好设置和配置' : 'Preferences and configuration'
    },
    { 
      key: 'projects', 
      label: t('projects'),
      icon: FolderOpen,
      description: currentLanguage === 'zh-CN' ? '项目管理和切换' : 'Project management and switching'
    },
    { 
      key: 'security', 
      label: t('security'),
      icon: Shield,
      description: currentLanguage === 'zh-CN' ? '安全设置和权限' : 'Security settings and permissions'
    },
  ];

  // ESC关闭弹窗
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div 
        ref={modalRef}
        className={`relative w-full max-w-4xl max-h-[90vh] rounded-2xl shadow-2xl transition-all transform ${
          isDarkMode ? 'bg-gray-900' : 'bg-white'
        } overflow-hidden animate-in fade-in-50 slide-in-from-bottom-4 duration-300`}
      >
        {/* 关闭按钮 */}
        <button
          onClick={onClose}
          aria-label={t('close')}
          className={`absolute top-4 right-4 z-10 w-8 h-8 rounded-full ${
            isDarkMode ? 'bg-gray-800 hover:bg-gray-700' : 'bg-gray-100 hover:bg-gray-200'
          } flex items-center justify-center transition-colors`}
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex max-h-[80vh] flex-col md:flex-row">
          {/* 左侧导航 */}
          <div className={`w-full border-b p-3 pr-14 md:w-72 md:border-b-0 md:border-r md:p-6 ${
            isDarkMode ? 'border-gray-800 bg-gray-900/50' : 'border-gray-200 bg-gray-50/50'
          }`}>
            <div className="grid grid-cols-4 gap-2 md:block md:space-y-2">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    aria-label={tab.label}
                    title={tab.label}
                    className={`w-full rounded-xl p-3 text-center transition-all duration-200 md:p-4 md:text-left ${
                      activeTab === tab.key
                        ? isDarkMode
                          ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25'
                          : 'bg-blue-500 text-white shadow-lg shadow-blue-500/25'
                        : isDarkMode
                          ? 'hover:bg-gray-800 text-gray-300'
                          : 'hover:bg-gray-100 text-gray-700'
                    }`}
                  >
                    <div className="flex items-center justify-center md:justify-start md:space-x-3">
                      <Icon className="w-5 h-5" />
                      <div className="hidden md:block">
                        <div className="font-medium">{tab.label}</div>
                        <div className={`text-xs ${
                          activeTab === tab.key
                            ? 'text-blue-100'
                            : isDarkMode ? 'text-gray-500' : 'text-gray-500'
                        }`}>
                          {tab.description}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 右侧内容 */}
          <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
            <div className="max-w-2xl">
              {activeTab === 'profile' && <ProfileCard user={user} isDarkMode={isDarkMode} />}
              {activeTab === 'settings' && <SettingsCard isDarkMode={isDarkMode} />}
              {activeTab === 'projects' && <ProjectsCard isDarkMode={isDarkMode} />}
              {activeTab === 'security' && (
                <div className="text-center py-12">
                  <Shield className={`w-16 h-16 mx-auto mb-4 ${
                    isDarkMode ? 'text-gray-600' : 'text-gray-400'
                  }`} />
                  <h3 className="text-lg font-semibold mb-2">
                    {currentLanguage === 'zh-CN' ? '安全设置' : 'Security Settings'}
                  </h3>
                  <p className={`${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                    {currentLanguage === 'zh-CN' ? '敬请期待' : 'Coming soon'}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 底部操作栏 */}
        <div className={`border-t ${isDarkMode ? 'border-gray-800' : 'border-gray-200'} p-4 md:p-6`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <ModernAvatar username={user?.username || ''} size={40} />
              <div>
                <p className="font-medium">{user?.username}</p>
                <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                  {currentLanguage === 'zh-CN' ? '在线' : 'Online'}
                </p>
              </div>
            </div>
            <button
              onClick={logout}
              className={`flex items-center space-x-2 whitespace-nowrap rounded-lg border px-4 py-2 ${
                isDarkMode 
                  ? 'border-red-800 text-red-400 hover:bg-red-900/20' 
                  : 'border-red-200 text-red-600 hover:bg-red-50'
              } transition-colors`}
            >
              <LogOut className="w-4 h-4" />
              <span>{currentLanguage === 'zh-CN' ? '退出登录' : 'Sign Out'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
