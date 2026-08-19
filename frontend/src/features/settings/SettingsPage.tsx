import React, { useState } from 'react';
import {
  User,
  Moon,
  Sun,
  Monitor,
  Bell,
  Shield,
  Database,
  Palette,
  Check,
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { 
  supportedLanguages,
} from '@/utils/language';
import { useTheme } from '@/context/ThemeContext';
import { useAuth } from '@/context/AuthContext';
import { useLanguage } from '@/context/LanguageContext';

type ThemeMode = 'light' | 'dark' | 'auto';

interface SettingsSection {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

export function SettingsPage() {
  const { user } = useAuth();
  const [activeSection, setActiveSection] = useState('profile');
  const { themeMode, isDarkMode, setThemeMode } = useTheme();
  const { currentLanguage, setLanguage, t } = useLanguage();
  // 设置区域配置
  const settingsSections: SettingsSection[] = [
    {
      id: 'profile',
      title: t('profile'),
      description: t('manageAccountInfo'),
      icon: User
    },
    {
      id: 'appearance',
      title: t('appearance'),
      description: t('customizeInterface'),
      icon: Palette
    },
    {
      id: 'notifications',
      title: t('notifications'),
      description: t('configureNotifications'),
      icon: Bell
    },
    {
      id: 'security',
      title: t('security'),
      description: t('managePasswords'),
      icon: Shield
    },
    {
      id: 'data',
      title: t('dataManagement'),
      description: t('importExportData'),
      icon: Database
    }
  ];

  const handleThemeChange = (newTheme: ThemeMode) => {
    setThemeMode(newTheme);
  };

  // 语言切换
  const handleLanguageChange = (langCode: string) => {
    setLanguage(langCode);
  };

  const renderProfileSection = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-4">{t('personalInfo')}</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className={`block text-sm font-medium mb-2 ${
              isDarkMode ? 'text-gray-300' : 'text-gray-700'
            }`}>
              {t('username')}
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
              {t('emailAddress')}
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
        <h3 className="text-lg font-semibold mb-4">{t('accountStats')}</h3>
        <div
          className="rounded-lg border border-border bg-muted/40 p-4 text-sm text-muted-foreground"
          role="status"
        >
          {t('accountStatsUnavailable')}
        </div>
      </div>
    </div>
  );

  const renderAppearanceSection = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-4">{t('themeSettings')}</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { value: 'light', label: t('lightMode'), icon: Sun },
            { value: 'dark', label: t('darkMode'), icon: Moon },
            { value: 'auto', label: t('autoMode'), icon: Monitor }
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
        <h3 className="text-lg font-semibold mb-4">{t('languageSettings')}</h3>
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

  const renderUnavailableSection = (title: string) => (
    <div className="space-y-3" role="status">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="rounded-lg border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
        {t('settingsSectionUnavailable')}
      </p>
    </div>
  );

  return (
    <div className="h-full overflow-y-auto bg-background text-foreground transition-colors duration-300">
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="mb-2 text-3xl font-bold">{t('settings')}</h1>
            <p className="text-lg text-muted-foreground">{t('settingsDescription')}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* 左侧导航 */}
          <div className="lg:col-span-1">
            <nav className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:block lg:space-y-2">
              {settingsSections.map((section) => {
                const Icon = section.icon;
                return (
                  <button
                    key={section.id}
                    onClick={() => setActiveSection(section.id)}
                    className={`w-full rounded-xl p-3 text-left transition-all duration-200 lg:p-4 ${
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
                        <div className={`hidden text-xs lg:block ${
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
            <div className={`rounded-2xl border p-5 sm:p-8 ${
              isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
            }`}>
              {activeSection === 'profile' && renderProfileSection()}
              {activeSection === 'appearance' && renderAppearanceSection()}
              {activeSection === 'notifications' && renderUnavailableSection(t('notifications'))}
              {activeSection === 'security' && renderUnavailableSection(t('security'))}
              {activeSection === 'data' && renderUnavailableSection(t('dataManagement'))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
