import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import PageMeta from '../../components/PageMeta';
import { getLegalMarkdown, pickLanguage, type LegalDoc, type LegalLang } from '../../content/legal';

const TITLES: Record<LegalDoc, string> = {
  privacy: 'Privacy Policy',
  terms: 'Terms of Service',
};

const LANGUAGES: { lang: LegalLang; label: string }[] = [
  { lang: 'en', label: 'English' },
  { lang: 'fr', label: 'Français' },
  { lang: 'es', label: 'Español' },
];

interface LegalDocumentPageProps {
  doc: LegalDoc;
}

export default function LegalDocumentPage({ doc }: LegalDocumentPageProps) {
  const [params] = useSearchParams();
  const lang = pickLanguage(
    params.get('lang'),
    typeof navigator === 'undefined' ? undefined : navigator.language
  );
  const html = useMemo(
    () => DOMPurify.sanitize(marked.parse(getLegalMarkdown(doc, lang), { async: false })),
    [doc, lang]
  );

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 md:px-7">
      <PageMeta title={`${TITLES[doc]} | Houseplant MD`} />
      <nav aria-label="Language" className="mb-6 flex gap-4 text-body-sm">
        {LANGUAGES.map(({ lang: code, label }) => (
          <Link
            key={code}
            to={`/${doc}?lang=${code}`}
            aria-current={code === lang ? 'true' : undefined}
            className={
              code === lang ? 'font-semibold text-ink' : 'text-ink-2 underline hover:text-ink'
            }
          >
            {label}
          </Link>
        ))}
      </nav>
      <article
        lang={lang}
        className="legal-doc text-body text-ink"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
