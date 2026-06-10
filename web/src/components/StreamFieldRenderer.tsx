import { createSafeMarkup, SANITIZE_PRESETS } from '../utils/sanitize';
import type { StreamFieldBlock as StreamFieldBlockType } from '@/types/blog';

/**
 * SafeHTML Component
 *
 * Renders DOMPurify-sanitized HTML. Sanitization is synchronous (DOMPurify is in
 * the main bundle via utils/sanitize), so there is no loading state or effect
 * (todo 222 / M13 — dropped the needless async wrapper + scaffolding).
 */
interface SafeHTMLProps {
  html: string;
  className?: string;
}

function SafeHTML({ html, className = '' }: SafeHTMLProps) {
  const safeMarkup = createSafeMarkup(html, SANITIZE_PRESETS.STREAMFIELD);
  return <div className={className} dangerouslySetInnerHTML={safeMarkup} />;
}

/**
 * StreamFieldRenderer Component
 *
 * Renders Wagtail StreamField blocks based on their type.
 * Supports all standard blog content blocks.
 */
interface StreamFieldRendererProps {
  blocks?: StreamFieldBlockType[] | null;
}

function renderTextOrSafeHtml(content: string, className = '') {
  return content.includes('<') ? (
    <SafeHTML html={content} className={className} />
  ) : (
    <div className={className}>{content}</div>
  );
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function getSafeHref(url: string): string {
  const trimmedUrl = url.trim();

  if (trimmedUrl.startsWith('/') && !trimmedUrl.startsWith('//')) {
    return trimmedUrl;
  }

  try {
    const parsedUrl = new URL(trimmedUrl);
    return ['http:', 'https:', 'mailto:'].includes(parsedUrl.protocol) ? trimmedUrl : '#';
  } catch {
    return '#';
  }
}

export default function StreamFieldRenderer({ blocks }: StreamFieldRendererProps) {
  if (!blocks || blocks.length === 0) {
    return null;
  }

  return (
    <div className="prose prose-lg max-w-none">
      {blocks.map((block, index) => (
        <StreamFieldBlock key={block.id || index} block={block} />
      ))}
    </div>
  );
}

/**
 * StreamFieldBlock Component
 *
 * Renders individual StreamField blocks based on their type.
 */
interface StreamFieldBlockProps {
  block: StreamFieldBlockType;
}

function StreamFieldBlock({ block }: StreamFieldBlockProps) {
  const { type } = block;

  switch (type) {
    case 'heading': {
      // Backend: CharBlock (simple string)
      return <h2 className="text-3xl font-bold mt-8 mb-4 text-ink">{block.value}</h2>;
    }

    case 'paragraph':
      // Backend: RichTextBlock (HTML string)
      return <SafeHTML html={block.value} className="mb-4 text-ink-2 leading-relaxed" />;

    // Removed: image block (no backend definition, use paragraph with embedded images)

    case 'quote': {
      // Backend: StructBlock with quote_text (RichTextBlock) and attribution (CharBlock)
      const { value } = block;
      const quoteText = typeof value === 'string' ? value : (value.quote_text ?? value.quote ?? '');
      const attribution = typeof value === 'string' ? undefined : value.attribution;

      return (
        <blockquote className="border-l-4 border-primary pl-6 py-4 my-8 italic text-ink-2 bg-surface rounded-r-lg">
          {quoteText && renderTextOrSafeHtml(quoteText, 'text-xl mb-2')}
          {attribution && (
            <footer className="text-sm text-ink-3 not-italic">— {attribution}</footer>
          )}
        </blockquote>
      );
    }

    case 'code': {
      // Backend: StructBlock with code (TextBlock) and language (ChoiceBlock)
      const { code, language } = block.value;
      return (
        <pre className="bg-ink text-surface p-4 rounded-lg overflow-x-auto my-6 shadow-inner">
          <code className={`language-${language || 'text'}`}>{code}</code>
        </pre>
      );
    }

    case 'plant_spotlight': {
      // Backend: StructBlock with plant_name, scientific_name, description, care_difficulty, image
      const { value } = block;
      const plantName = value.plant_name ?? value.heading ?? '';
      const description = value.description ?? '';
      const careValue = value.care_difficulty ?? value.care_level;
      const careLabel = value.care_level ? 'Care Level' : 'Care Difficulty';

      return (
        <div className="my-8 p-6 bg-primary/10 border-2 border-primary/20 rounded-lg shadow-sm">
          <h3 className="text-2xl font-bold text-ink mb-3">🌿 {plantName}</h3>
          {value.scientific_name && (
            <p className="text-sm italic text-ink-3 mb-3">{value.scientific_name}</p>
          )}
          {value.image && (
            <img
              src={value.image.url}
              alt={value.image.title || value.image.alt || plantName}
              className="w-full h-64 object-cover rounded-lg mb-4 shadow-md"
            />
          )}
          {description && renderTextOrSafeHtml(description, 'text-ink-2 mb-4')}
          {careValue && (
            <p className="mt-4 text-sm font-semibold text-leaf flex items-center">
              <svg
                className="w-5 h-5 mr-2"
                aria-hidden="true"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              {careLabel}: {capitalize(careValue)}
            </p>
          )}
        </div>
      );
    }

    case 'call_to_action': {
      // Backend: StructBlock with cta_title, cta_description, button_text, button_url, button_style
      const { value } = block;
      const title = value.cta_title ?? value.heading ?? '';
      const description = value.cta_description ?? value.description ?? '';
      const buttonText = value.button_text ?? '';
      const buttonUrl = getSafeHref(value.button_url ?? '#');
      const buttonStyle = value.button_style;

      // Map button style to Tailwind classes
      const buttonClasses =
        buttonStyle === 'secondary'
          ? 'inline-block px-8 py-3 bg-surface-2 text-ink-2 font-semibold rounded-lg hover:bg-surface-3 transition-colors shadow-md'
          : buttonStyle === 'outline'
            ? 'inline-block px-8 py-3 bg-transparent border-2 border-on-primary text-on-primary font-semibold rounded-lg hover:bg-on-primary hover:text-primary transition-colors shadow-md'
            : 'inline-block px-8 py-3 bg-surface-2 text-primary font-semibold rounded-lg hover:bg-surface-3 transition-colors shadow-md';

      return (
        <div className="my-8 p-8 bg-primary text-on-primary rounded-lg text-center shadow-lg">
          <h3 className="text-2xl font-bold mb-2">{title}</h3>
          {description && renderTextOrSafeHtml(description, 'mb-6 text-on-primary')}
          {buttonText && (
            <a href={buttonUrl} className={buttonClasses}>
              {buttonText}
            </a>
          )}
        </div>
      );
    }

    // Removed: list and embed blocks (no backend definitions)

    default:
      return (
        <div className="my-4 p-4 bg-warn/10 border border-warn/30 rounded text-sm text-ink-3">
          <p className="font-semibold text-warn mb-1">Unsupported block type</p>
          <code className="text-xs">{type}</code>
        </div>
      );
  }
}
