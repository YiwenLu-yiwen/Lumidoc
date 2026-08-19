// @vitest-environment jsdom

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { DocumentAnalysis } from '../../src/components/document/DocumentAnalysis';

vi.mock('../../src/context/ThemeContext', () => ({
  useTheme: () => ({ isDarkMode: false }),
}));

vi.mock('../../src/context/LanguageContext', () => ({
  useLanguage: () => ({
    currentLanguage: 'en-US',
    t: (key: string) => ({
      noDocuments: 'No documents yet',
      uploadFirstDocument: 'Upload a document to start analysis.',
    } as Record<string, string>)[key] || key,
  }),
}));

describe('DocumentAnalysis', () => {
  it('starts with an honest empty state instead of sample documents', () => {
    render(<DocumentAnalysis />);

    expect(screen.getByText('No documents yet')).toBeTruthy();
    expect(screen.queryByText('2024年度财务报告.pdf')).toBeNull();
  });
});
