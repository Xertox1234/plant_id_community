import { describe, it, expect } from 'vitest';
import {
  pickLanguage,
  getLegalMarkdown,
  getLegalVersion,
  type LegalDoc,
  type LegalLang,
} from './index';

describe('pickLanguage', () => {
  it.each([
    ['fr', 'en-US', 'fr'],
    [null, 'fr-CA', 'fr'],
    [null, 'es-MX', 'es'],
    [null, 'pt-BR', 'en'],
    [null, undefined, 'en'],
    ['de', 'es-ES', 'es'],
  ])('(%s, %s) -> %s', (param, nav, expected) => {
    expect(pickLanguage(param, nav)).toBe(expected);
  });
});

describe('getLegalMarkdown', () => {
  const docs: LegalDoc[] = ['privacy', 'terms'];
  const langs: LegalLang[] = ['en', 'fr', 'es'];
  for (const doc of docs) {
    for (const lang of langs) {
      it(`${doc}.${lang} is non-empty and carries the version comment`, () => {
        const md = getLegalMarkdown(doc, lang);
        expect(md.length).toBeGreaterThan(0);
        expect(md).toContain('<!-- version: 2026-11-11 -->');
      });
    }
  }
});

describe('getLegalVersion', () => {
  it('reads the version comment of a document', () => {
    expect(getLegalVersion(getLegalMarkdown('privacy', 'en'))).toBe('2026-11-11');
  });

  it('returns null when there is no version comment', () => {
    expect(getLegalVersion('# Title')).toBeNull();
  });
});
