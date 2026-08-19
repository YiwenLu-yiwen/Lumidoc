import { describe, expect, it } from 'vitest';

import {
  resolveSupportedLanguage,
  supportedLanguages,
  translations,
} from '../../src/utils/language';


describe('language policy', () => {
  it('only exposes locales with complete product coverage', () => {
    expect(supportedLanguages.map((language) => language.code)).toEqual([
      'zh-CN',
      'en-US',
    ]);
  });

  it('keeps English translation keys aligned with Chinese', () => {
    expect(Object.keys(translations['en-US']).sort()).toEqual(
      Object.keys(translations['zh-CN']).sort(),
    );
  });

  it('falls back unsupported browser locales to English', () => {
    expect(resolveSupportedLanguage('ja-JP')).toBe('en-US');
    expect(resolveSupportedLanguage('fr-FR')).toBe('en-US');
    expect(resolveSupportedLanguage('zh-HK')).toBe('zh-CN');
  });
});
