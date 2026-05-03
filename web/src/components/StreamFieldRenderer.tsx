import { useState, useEffect } from 'react';
import { createSafeMarkup, SANITIZE_PRESETS } from '../utils/domSanitizer';
import type { StreamFieldBlock as StreamFieldBlockType } from '@/types/blog';

/**
 * SafeHTML Component
 *
 * Wrapper component that handles async HTML sanitization with DOMPurify.
 * DOMPurify is dynamically imported to reduce initial bundle size.
 */
interface SafeHTMLProps {
  html: string;
  className?: string;
}

function SafeHTML({ html, className = '' }: SafeHTMLProps) {
  const [safeMarkup, setSafeMarkup] = useState<{ __html: string } | null>(null);

  useEffect(() => {
    let isMounted = true;

    createSafeMarkup(html, SANITIZE_PRESETS.STREAMFIELD).then((markup) => {
      if (isMounted) {
        setSafeMarkup(markup);
      }
    });

    return () => {
      isMounted = false;
    };
  }, [html]);

  if (!safeMarkup) {
    return <div className={className}>Loading...</div>;
  }

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
      return <h2 className="text-3xl font-bold mt-8 mb-4 text-gray-900">{block.value}</h2>;
    }

    case 'paragraph':
      // Backend: RichTextBlock (HTML string)
      return <SafeHTML html={block.value} className="mb-4 text-gray-700 leading-relaxed" />;

    // Removed: image block (no backend definition, use paragraph with embedded images)

    case 'quote': {
      // Backend: StructBlock with quote_text (RichTextBlock) and attribution (CharBlock)
      const { value } = block;
      const quoteText = typeof value === 'string' ? value : value.quote_text ?? value.quote ?? '';
      const attribution = typeof value === 'string' ? undefined : value.attribution;

      return (
        <blockquote className="border-l-4 border-green-600 pl-6 py-4 my-8 italic text-gray-700 bg-gray-50 rounded-r-lg">
          {quoteText && renderTextOrSafeHtml(quoteText, 'text-xl mb-2')}
          {attribution && (
            <footer className="text-sm text-gray-600 not-italic">
              — {attribution}
            </footer>
          )}
        </blockquote>
      );
    }

    case 'code': {
      // Backend: StructBlock with code (TextBlock) and language (ChoiceBlock)
      const { code, language } = block.value;
      return (
        <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto my-6 shadow-inner">
          <code className={`language-${language || 'text'}`}>
            {code}
          </code>
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
        <div className="my-8 p-6 bg-green-50 border-2 border-green-200 rounded-lg shadow-sm">
          <h3 className="text-2xl font-bold text-gray-900 mb-3">
            🌿 {plantName}
          </h3>
          {value.scientific_name && (
            <p className="text-sm italic text-gray-600 mb-3">{value.scientific_name}</p>
          )}
          {value.image && (
            <img
              src={value.image.url}
              alt={value.image.title || value.image.alt || plantName}
              className="w-full h-64 object-cover rounded-lg mb-4 shadow-md"
            />
          )}
          {description && renderTextOrSafeHtml(description, 'text-gray-700 mb-4')}
          {careValue && (
            <p className="mt-4 text-sm font-semibold text-green-700 flex items-center">
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
      const buttonClasses = buttonStyle === 'secondary'
        ? 'inline-block px-8 py-3 bg-gray-200 text-gray-800 font-semibold rounded-lg hover:bg-gray-300 transition-colors shadow-md'
        : buttonStyle === 'outline'
        ? 'inline-block px-8 py-3 bg-transparent border-2 border-white text-white font-semibold rounded-lg hover:bg-white hover:text-green-600 transition-colors shadow-md'
        : 'inline-block px-8 py-3 bg-white text-green-600 font-semibold rounded-lg hover:bg-gray-100 transition-colors shadow-md';

      return (
        <div className="my-8 p-8 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg text-center shadow-lg">
          <h3 className="text-2xl font-bold mb-2">{title}</h3>
          {description && renderTextOrSafeHtml(description, 'mb-6 text-green-50')}
          {buttonText && (
            <a
              href={buttonUrl}
              className={buttonClasses}
            >
              {buttonText}
            </a>
          )}
        </div>
      );
    }

    // Removed: list and embed blocks (no backend definitions)

    default:
      return (
        <div className="my-4 p-4 bg-yellow-50 border border-yellow-200 rounded text-sm text-gray-600">
          <p className="font-semibold text-yellow-800 mb-1">
            Unsupported block type
          </p>
          <code className="text-xs">{type}</code>
        </div>
      );
  }
}
