// @vitest-environment jsdom

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SettingsPage } from '../../src/features/settings/SettingsPage';


vi.mock('../../src/context/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'reviewer', email: 'reviewer@example.com' } }),
}));

vi.mock('../../src/context/ThemeContext', () => ({
  useTheme: () => ({
    themeMode: 'light',
    isDarkMode: false,
    setThemeMode: vi.fn(),
  }),
}));

vi.mock('../../src/context/LanguageContext', () => ({
  useLanguage: () => ({
    currentLanguage: 'en-US',
    setLanguage: vi.fn(),
    t: (key: string) => ({
      settings: 'Settings',
      settingsDescription: 'Manage your account and preferences',
      personalInfo: 'Personal Information',
      accountStatsUnavailable: 'Usage metrics are not available yet.',
      profile: 'Profile',
      appearance: 'Appearance',
      notifications: 'Notifications',
      security: 'Security',
      dataManagement: 'Data Management',
      manageAccountInfo: 'Manage account information',
      customizeInterface: 'Customize interface',
      configureNotifications: 'Configure notifications',
      managePasswords: 'Manage passwords',
      importExportData: 'Import and export data',
      username: 'Username',
      emailAddress: 'Email Address',
      accountStats: 'Account Statistics',
    } as Record<string, string>)[key] || key,
  }),
}));

describe('SettingsPage', () => {
  it('does not present fabricated account or credential data', () => {
    render(<SettingsPage />);

    expect(screen.queryByText('156')).toBeNull();
    expect(screen.queryByText('23')).toBeNull();
    expect(screen.queryByText('2.3GB')).toBeNull();
    expect(screen.queryByText('OpenAI API Key')).toBeNull();
    expect(screen.getByText('Usage metrics are not available yet.')).toBeTruthy();
  });
});
