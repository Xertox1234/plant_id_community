import privacyEn from './privacy.en.md?raw';
import privacyFr from './privacy.fr.md?raw';
import privacyEs from './privacy.es.md?raw';
import termsEn from './terms.en.md?raw';
import termsFr from './terms.fr.md?raw';
import termsEs from './terms.es.md?raw';

export type LegalDoc = 'privacy' | 'terms';
export type LegalLang = 'en' | 'fr' | 'es';

export const LEGAL_LANGS: readonly LegalLang[] = ['en', 'fr', 'es'];

const DOCS: Record<LegalDoc, Record<LegalLang, string>> = {
  privacy: { en: privacyEn, fr: privacyFr, es: privacyEs },
  terms: { en: termsEn, fr: termsFr, es: termsEs },
};

function fromBrowser(navigatorLanguage: string | undefined): LegalLang {
  const code = (navigatorLanguage ?? '').toLowerCase();
  if (code.startsWith('fr')) return 'fr';
  if (code.startsWith('es')) return 'es';
  return 'en';
}

/** A valid `?lang` wins; anything else falls back to the browser language. */
export function pickLanguage(
  param: string | null,
  navigatorLanguage: string | undefined
): LegalLang {
  if (param && (LEGAL_LANGS as readonly string[]).includes(param)) return param as LegalLang;
  return fromBrowser(navigatorLanguage);
}

export function getLegalMarkdown(doc: LegalDoc, lang: LegalLang): string {
  return DOCS[doc][lang];
}
