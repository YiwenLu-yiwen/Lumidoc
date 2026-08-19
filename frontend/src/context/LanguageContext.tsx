import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  detectBrowserLanguage,
  getTranslation,
  resolveSupportedLanguage,
  saveLanguage,
  translations,
} from '@/utils/language';

export type TranslationKey = keyof typeof translations['zh-CN'];

interface LanguageContextValue {
  currentLanguage: string;
  setLanguage: (languageCode: string) => void;
  t: (key: TranslationKey) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [currentLanguage, setCurrentLanguage] = useState(() =>
    resolveSupportedLanguage(detectBrowserLanguage()),
  );

  const setLanguage = useCallback((languageCode: string) => {
    const supportedLanguage = resolveSupportedLanguage(languageCode);
    saveLanguage(supportedLanguage);
    setCurrentLanguage(supportedLanguage);
  }, []);

  useEffect(() => {
    document.documentElement.lang = currentLanguage;
  }, [currentLanguage]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      currentLanguage,
      setLanguage,
      t: (key) => getTranslation(currentLanguage, key),
    }),
    [currentLanguage, setLanguage],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useLanguage(): LanguageContextValue {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
