// @vitest-environment jsdom

import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { LanguageProvider, useLanguage } from '../../src/context/LanguageContext';


function LanguageProbe() {
  const { currentLanguage, setLanguage, t } = useLanguage();

  return (
    <div>
      <span>{currentLanguage}</span>
      <span>{t('settings')}</span>
      <button type="button" onClick={() => setLanguage('en-US')}>
        Switch
      </button>
    </div>
  );
}

describe('LanguageProvider', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('lumidoc_language', 'zh-CN');
  });

  it('updates visible translations and the document language immediately', () => {
    render(
      <LanguageProvider>
        <LanguageProbe />
      </LanguageProvider>,
    );

    expect(screen.getByText('设置')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Switch' }));
    expect(screen.getByText('Settings')).toBeTruthy();
    expect(document.documentElement.lang).toBe('en-US');
  });
});
