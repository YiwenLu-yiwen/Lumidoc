import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { detectAutoTheme } from '@/utils/language';

export type ThemeMode = 'light' | 'dark' | 'auto';

interface ThemeContextType {
  themeMode: ThemeMode;
  isDarkMode: boolean;
  setThemeMode: (mode: ThemeMode) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

interface ThemeProviderProps {
  children: ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [themeMode, setThemeModeState] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem('stp_theme_mode') as ThemeMode;
    return saved && ['light', 'dark', 'auto'].includes(saved) ? saved : 'auto';
  });

  // 计算实际的暗色模式状态
  const isDarkMode = themeMode === 'auto' ? detectAutoTheme() === 'dark' : themeMode === 'dark';

  // 设置主题模式
  const setThemeMode = (mode: ThemeMode) => {
    setThemeModeState(mode);
    localStorage.setItem('stp_theme_mode', mode);
    
    // 立即更新 body 类名
    updateBodyClass(mode);
  };

  // 切换主题（循环：light -> dark -> auto）
  const toggleTheme = () => {
    const modes: ThemeMode[] = ['light', 'dark', 'auto'];
    const currentIndex = modes.indexOf(themeMode);
    const nextMode = modes[(currentIndex + 1) % modes.length];
    setThemeMode(nextMode);
  };

  // 更新 body 类名
  const updateBodyClass = (mode: ThemeMode) => {
    if (mode === 'auto') {
      const autoTheme = detectAutoTheme();
      document.body.classList.toggle('dark', autoTheme === 'dark');
    } else {
      document.body.classList.toggle('dark', mode === 'dark');
    }
  };

  // 监听系统主题变化（仅在 auto 模式下）
  useEffect(() => {
    if (themeMode === 'auto') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      
      const handleChange = () => {
        updateBodyClass('auto');
        // 强制重新渲染
        setThemeModeState(prev => prev);
      };

      mediaQuery.addEventListener('change', handleChange);
      
      return () => {
        mediaQuery.removeEventListener('change', handleChange);
      };
    }
  }, [themeMode]);

  // 初始化时设置 body 类名
  useEffect(() => {
    updateBodyClass(themeMode);
  }, [themeMode]);

  const contextValue: ThemeContextType = {
    themeMode,
    isDarkMode,
    setThemeMode,
    toggleTheme
  };

  return (
    <ThemeContext.Provider value={contextValue}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextType {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}