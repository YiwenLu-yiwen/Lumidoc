import React, { useState, useEffect } from 'react';
import {
  User,
  Settings,
  Moon,
  Sun,
  Monitor,
  Globe,
  Bell,
  Shield,
  Database,
  Palette,
  Key,
  Download,
  Upload,
  RefreshCw,
  Save,
  Check,
  AlertCircle,
  Info,
  Eye,
  EyeOff,
  Copy,
  Trash2,
  Plus
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  detectAutoTheme, 
  detectBrowserLanguage, 
  saveLanguage, 
  supportedLanguages,
  getTranslation
} from '@/utils/language';
import { useAuth } from '@/context/AuthContext';

type ThemeMode = 'light' | 'dark' | 'auto';

interface SettingsSection {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface APIKey {
  id: string;
  name: string;
  key: string;
  provider: string;
  createdAt: Date;
  lastUsed?: Date;
}

export function SettingsPage() {
  const { user } = useAuth();
  const [activeSection, setActiveSection] = useState('profile');
  const [themeMode, setThemeMode] = useState<ThemeMode>('auto');
  const [currentLanguage, setCurrentLanguage] = useState<string>(detectBrowserLanguage());
  const [notifications, setNotifications] = useState({
    email: true,
    push: false,
    desktop: true,
    marketing: false
  });
  const [apiKeys, setApiKeys] = useState<APIKey[]>([
    {
      id: '1',
      name: 'OpenAI API Key',
      key: 'sk-...Xj3k',
      provider: 'OpenAI',
      createdAt: new Date('2024-01-15'),
      lastUsed: new Date('2024-01-18')
    },
    {
      id: '2',
      name: 'DeepSeek API Key',
      key: 'dk-...P9m2',
      provider: 'DeepSeek',
      createdAt: new Date('2024-01-16'),
      lastUsed: new Date('2024-01-18')
    }
  ]);
  const [showApiKey, setShowApiKey] = useState<string | null>(null);
  const [newApiKey, setNewApiKey] = useState({ name: '', key: '', provider: 'OpenAI' });
  const [showNewApiForm, setShowNewApiForm] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');

  // 主题模式检测
  const isDarkMode = themeMode === 'auto' ? detectAutoTheme() === 'dark' : themeMode === 'dark';

  // 获取翻译文本
  const t = (key: keyof typeof import('@/utils/language').translations['zh-CN']) => 
    getTranslation(currentLanguage, key);

  // 设置区域配置
  const settingsSections: SettingsSection[] = [
    {
      id: 'profile',
      title: '个人资料',
      description: '管理您的账户信息和偏好设置',
      icon: User
    },
    {
      id: 'appearance',
      title: '外观设置',
      description: '自定义界面主题和显示选项',
      icon: Palette
    },
    {
      id: 'notifications',
      title: '通知设置',
      description: '配置消息通知和提醒方式',
      icon: Bell
    },
    {
      id: 'security',
      title: '安全设置',
      description: '管理密码、API密钥和安全选项',
      icon: Shield
    },
    {
      id: 'data',
      title: '数据管理',
      description: '导入导出数据，管理存储空间',
      icon: Database
    }
  ];

  // 初始化主题模式
  useEffect(() => {
    const savedTheme = localStorage.getItem('stp_theme_mode') as ThemeMode;
    if (savedTheme && ['light', 'dark', 'auto'].includes(savedTheme)) {
      setThemeMode(savedTheme);
    }
  }, []);

  // 主题切换
  const handleThemeChange = (newTheme: ThemeMode) => {
    setThemeMode(newTheme);
    localStorage.setItem('stp_theme_mode', newTheme);
    
    // 更新body类名
    if (newTheme === 'auto') {
      const autoTheme = detectAutoTheme();
      document.body.classList.toggle('dark', autoTheme === 'dark');
    } else {
      document.body.classList.toggle('dark', newTheme === 'dark');
    }
  };

  // 语言切换
  const handleLanguageChange = (langCode: string) => {
    setCurrentLanguage(langCode);
    saveLanguage(langCode);
  };

  // 通知设置切换
  const handleNotificationChange = (key: keyof typeof notifications) => {
    setNotifications(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  // 保存设置
  const handleSaveSettings = async () => {
    setSaveStatus('saving');
    try {
      // 模拟API调用
      await new Promise(resolve => setTimeout(resolve, 1000));
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      setSaveStatus('error');
      setTimeout(() => setSaveStatus('idle'), 2000);
    }
  };

  // API密钥管理
  const handleAddApiKey = () => {
    if (newApiKey.name && newApiKey.key) {
      const newKey: APIKey = {
        id: Date.now().toString(),
        name: newApiKey.name,
        key: newApiKey.key,
        provider: newApiKey.provider,
        createdAt: new Date()
      };
      setApiKeys(prev => [...prev, newKey]);
      setNewApiKey({ name: '', key: '', provider: 'OpenAI' });
      setShowNewApiForm(false);
    }
  };

  const handleDeleteApiKey = (id: string) => {
    setApiKeys(prev => prev.filter(key => key.id !== id));
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const formatDate = (date: Date) => {
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const renderProfileSection = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-4">个人信息</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className={`block text-sm font-medium mb-2 ${
              isDarkMode ? 'text-gray-300' : 'text-gray-700'
            }`}>
              用户名
            </label>
            <Input
              value={user?.username || ''}
              readOnly
              className={`${
                isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-gray-50 border-gray-300'
              }`}
            />
          </div>
          <div>
            <label className={`block text-sm font-medium mb-2 ${
              isDarkMode ? 'text-gray-300' : 'text-gray-700'
            }`}>
              邮箱地址
            </label>
            <Input
              value={user?.email || ''}
              readOnly
              className={`${
                isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-gray-50 border-gray-300'
              }`}
            />
          </div>
        </div>
      </div>
      
      <div>
        <h3 className="text-lg font-semibold mb-4">账户统计</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className={`p-4 rounded-lg ${
            isDarkMode ? 'bg-gray-800' : 'bg-gray-50'
          }`}>
            <div className="text-2xl font-bold text-blue-600">156</div>
            <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              总对话数
            </div>
          </div>
          <div className={`p-4 rounded-lg ${
            isDarkMode ? 'bg-gray-800' : 'bg-gray-50'
          }`}>
            <div className="text-2xl font-bold text-green-600">23</div>
            <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              处理文档
            </div>
          </div>
          <div className={`p-4 rounded-lg ${
            isDarkMode ? 'bg-gray-800' : 'bg-gray-50'
          }`}>
            <div className="text-2xl font-bold text-purple-600">8</div>
            <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              活跃项目
            </div>
          </div>
          <div className={`p-4 rounded-lg ${
            isDarkMode ? 'bg-gray-800' : 'bg-gray-50'
          }`}>
            <div className="text-2xl font-bold text-orange-600">2.3GB</div>
            <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              存储使用
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderAppearanceSection = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-4">主题设置</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { value: 'light', label: '浅色模式', icon: Sun },
            { value: 'dark', label: '深色模式', icon: Moon },
            { value: 'auto', label: '自动模式', icon: Monitor }
          ].map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              onClick={() => handleThemeChange(value as ThemeMode)}
              className={`p-4 rounded-xl border-2 transition-all duration-200 ${
                themeMode === value
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                  : isDarkMode
                    ? 'border-gray-700 hover:border-gray-600'
                    : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <Icon className={`w-6 h-6 mx-auto mb-2 ${
                themeMode === value ? 'text-blue-600' : isDarkMode ? 'text-gray-400' : 'text-gray-600'
              }`} />
              <div className={`text-sm font-medium ${
                themeMode === value ? 'text-blue-600' : ''
              }`}>
                {label}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-4">语言设置</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {supportedLanguages.map((lang) => (
            <button
              key={lang.code}
              onClick={() => handleLanguageChange(lang.code)}
              className={`p-3 rounded-lg border transition-all duration-200 ${
                currentLanguage === lang.code
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                  : isDarkMode
                    ? 'border-gray-700 hover:border-gray-600'
                    : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="flex items-center space-x-2">
                <span className="text-lg">{lang.flag}</span>
                <span className={`text-sm font-medium ${
                  currentLanguage === lang.code ? 'text-blue-600' : ''
                }`}>
                  {lang.name}
                </span>
                {currentLanguage === lang.code && (
                  <Check className="w-4 h-4 text-blue-600" />
                )}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );

  const renderNotificationsSection = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-4">通知偏好</h3>
        <div className="space-y-4">
          {[
            { key: 'email', label: '邮件通知', desc: '接收重要更新和系统通知' },
            { key: 'push', label: '推送通知', desc: '在设备上接收实时通知' },
            { key: 'desktop', label: '桌面通知', desc: '在浏览器中显示通知' },
            { key: 'marketing', label: '营销邮件', desc: '接收产品更新和促销信息' }
          ].map(({ key, label, desc }) => (
            <div key={key} className={`flex items-center justify-between p-4 rounded-lg ${
              isDarkMode ? 'bg-gray-800' : 'bg-gray-50'
            }`}>
              <div>
                <div className="font-medium">{label}</div>
                <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                  {desc}
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={notifications[key as keyof typeof notifications]}
                  onChange={() => handleNotificationChange(key as keyof typeof notifications)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
              </label>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderSecuritySection = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-4">API密钥管理</h3>
        <div className="space-y-4">
          {apiKeys.map((apiKey) => (
            <div key={apiKey.id} className={`p-4 rounded-lg border ${
              isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <Key className="w-4 h-4 text-blue-600" />
                    <span className="font-medium">{apiKey.name}</span>
                    <span className={`px-2 py-1 text-xs rounded ${
                      isDarkMode ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {apiKey.provider}
                    </span>
                  </div>
                  <div className="flex items-center space-x-4 text-sm">
                    <div className={`font-mono ${
                      isDarkMode ? 'text-gray-400' : 'text-gray-600'
                    }`}>
                      {showApiKey === apiKey.id ? apiKey.key : '••••••••••••••••••••••••••••'}
                    </div>
                    <button
                      onClick={() => setShowApiKey(showApiKey === apiKey.id ? null : apiKey.id)}
                      className={`p-1 rounded ${
                        isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                      }`}
                    >
                      {showApiKey === apiKey.id ? (
                        <EyeOff className="w-4 h-4" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </button>
                    <button
                      onClick={() => copyToClipboard(apiKey.key)}
                      className={`p-1 rounded ${
                        isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                      }`}
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                  </div>
                  <div className={`text-xs mt-2 ${
                    isDarkMode ? 'text-gray-500' : 'text-gray-400'
                  }`}>
                    创建于 {formatDate(apiKey.createdAt)}
                    {apiKey.lastUsed && ` • 最后使用 ${formatDate(apiKey.lastUsed)}`}
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteApiKey(apiKey.id)}
                  className={`p-2 rounded text-red-500 ${
                    isDarkMode ? 'hover:bg-red-900/20' : 'hover:bg-red-50'
                  }`}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
          
          {showNewApiForm ? (
            <div className={`p-4 rounded-lg border-2 border-dashed ${
              isDarkMode ? 'border-gray-600 bg-gray-800/50' : 'border-gray-300 bg-gray-50'
            }`}>
              <div className="space-y-4">
                <Input
                  placeholder="API密钥名称"
                  value={newApiKey.name}
                  onChange={(e) => setNewApiKey(prev => ({ ...prev, name: e.target.value }))}
                />
                <Input
                  placeholder="API密钥"
                  value={newApiKey.key}
                  onChange={(e) => setNewApiKey(prev => ({ ...prev, key: e.target.value }))}
                />
                <select
                  value={newApiKey.provider}
                  onChange={(e) => setNewApiKey(prev => ({ ...prev, provider: e.target.value }))}
                  className={`w-full px-3 py-2 rounded-lg border ${
                    isDarkMode 
                      ? 'bg-gray-800 border-gray-700 text-white' 
                      : 'bg-white border-gray-300 text-gray-900'
                  }`}
                >
                  <option value="OpenAI">OpenAI</option>
                  <option value="DeepSeek">DeepSeek</option>
                  <option value="Claude">Claude</option>
                  <option value="Azure">Azure OpenAI</option>
                </select>
                <div className="flex space-x-3">
                  <Button onClick={handleAddApiKey} size="sm">
                    添加密钥
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={() => setShowNewApiForm(false)} 
                    size="sm"
                  >
                    取消
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowNewApiForm(true)}
              className={`w-full p-4 rounded-lg border-2 border-dashed transition-colors ${
                isDarkMode 
                  ? 'border-gray-600 hover:border-gray-500 hover:bg-gray-800/50' 
                  : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
              }`}
            >
              <Plus className="w-5 h-5 mx-auto mb-2 text-gray-400" />
              <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                添加新的API密钥
              </div>
            </button>
          )}
        </div>
      </div>
    </div>
  );

  const renderDataSection = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-4">数据导入导出</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className={`p-6 rounded-lg border ${
            isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
          }`}>
            <Upload className="w-8 h-8 text-blue-600 mb-3" />
            <h4 className="font-semibold mb-2">导入数据</h4>
            <p className={`text-sm mb-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              从文件中导入聊天记录和设置
            </p>
            <Button variant="outline" size="sm">
              选择文件
            </Button>
          </div>
          <div className={`p-6 rounded-lg border ${
            isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
          }`}>
            <Download className="w-8 h-8 text-green-600 mb-3" />
            <h4 className="font-semibold mb-2">导出数据</h4>
            <p className={`text-sm mb-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              下载您的所有数据和设置
            </p>
            <Button variant="outline" size="sm">
              开始导出
            </Button>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-4">存储管理</h3>
        <div className={`p-4 rounded-lg ${isDarkMode ? 'bg-gray-800' : 'bg-gray-50'}`}>
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium">存储使用情况</span>
            <span className="text-sm text-gray-500">2.3GB / 10GB</span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div className="bg-blue-600 h-2 rounded-full" style={{ width: '23%' }}></div>
          </div>
          <div className="flex justify-between text-xs text-gray-500 mt-2">
            <span>聊天记录: 1.2GB</span>
            <span>文档: 800MB</span>
            <span>模型缓存: 300MB</span>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className={`h-full overflow-y-auto transition-colors duration-300 ${
      isDarkMode ? 'bg-[#212121] text-gray-100' : 'bg-white text-gray-900'
    }`}>
      <div className="max-w-7xl mx-auto p-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold mb-2">系统设置</h1>
            <p className={`text-lg ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              管理您的账户、偏好设置和系统配置
            </p>
          </div>
          <Button
            onClick={handleSaveSettings}
            disabled={saveStatus === 'saving'}
            className={`${
              saveStatus === 'saved' 
                ? 'bg-green-600 hover:bg-green-700' 
                : 'bg-blue-600 hover:bg-blue-700'
            } text-white`}
          >
            {saveStatus === 'saving' ? (
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            ) : saveStatus === 'saved' ? (
              <Check className="w-4 h-4 mr-2" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            {saveStatus === 'saving' ? '保存中...' : saveStatus === 'saved' ? '已保存' : '保存设置'}
          </Button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* 左侧导航 */}
          <div className="lg:col-span-1">
            <nav className="space-y-2">
              {settingsSections.map((section) => {
                const Icon = section.icon;
                return (
                  <button
                    key={section.id}
                    onClick={() => setActiveSection(section.id)}
                    className={`w-full text-left p-4 rounded-xl transition-all duration-200 ${
                      activeSection === section.id
                        ? isDarkMode
                          ? 'bg-blue-900/30 text-blue-400 border border-blue-500/30'
                          : 'bg-blue-50 text-blue-700 border border-blue-200'
                        : isDarkMode
                          ? 'hover:bg-gray-800 text-gray-300'
                          : 'hover:bg-gray-50 text-gray-700'
                    }`}
                  >
                    <div className="flex items-center space-x-3">
                      <Icon className="w-5 h-5" />
                      <div>
                        <div className="font-medium">{section.title}</div>
                        <div className={`text-xs ${
                          activeSection === section.id
                            ? isDarkMode ? 'text-blue-300' : 'text-blue-600'
                            : isDarkMode ? 'text-gray-500' : 'text-gray-500'
                        }`}>
                          {section.description}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </nav>
          </div>

          {/* 右侧内容 */}
          <div className="lg:col-span-3">
            <div className={`rounded-2xl border p-8 ${
              isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
            }`}>
              {activeSection === 'profile' && renderProfileSection()}
              {activeSection === 'appearance' && renderAppearanceSection()}
              {activeSection === 'notifications' && renderNotificationsSection()}
              {activeSection === 'security' && renderSecuritySection()}
              {activeSection === 'data' && renderDataSection()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}