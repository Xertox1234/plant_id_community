import { createSafeMarkup, SANITIZE_PRESETS } from '../utils/sanitize';
import { highlightMentions } from '../utils/mentions';
import { mediaUrl } from '../services/blogService';
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
  /** Applied AFTER sanitization — must never introduce user-controlled markup. */
  postProcess?: (html: string) => string;
  /**
   * DOMPurify preset. Defaults to the broad STREAMFIELD allowlist (blog); forum
   * content passes the tighter FORUM allowlist so headings/img/div/pre in a
   * direct-API payload are stripped, matching the server contract (M32).
   */
  preset?: Parameters<typeof createSafeMarkup>[1];
}

function SafeHTML({
  html,
  className = '',
  postProcess,
  preset = SANITIZE_PRESETS.STREAMFIELD,
}: SafeHTMLProps) {
  const safeMarkup = createSafeMarkup(html, preset);
  const markup = postProcess ? { __html: postProcess(safeMarkup.__html) } : safeMarkup;
  return <div className={className} dangerouslySetInnerHTML={markup} />;
}

/**
 * StreamFieldRenderer Component
 *
 * Renders Wagtail StreamField blocks based on their type.
 * Supports all standard blog content blocks.
 */
interface StreamFieldRendererProps {
  blocks?: StreamFieldBlockType[] | null;
  /** Forum posts only: style @username mentions in paragraph blocks. */
  mentionHighlight?: boolean;
  /**
   * 'inline' (default): current compact rendering — forum posts, previews.
   * 'article': blog detail — reading measure + roomier block rhythm.
   */
  variant?: 'inline' | 'article';
  /**
   * When set, each block is wrapped in an element with `id="<prefix>-<index>"`
   * (index into the StreamField's raw block list) so a citation can deep-link
   * to the passage (`/blog/<slug>#block-7`, todo 289). Opt-in per renderer: a
   * thread page mounts one renderer per post, so unconditional ids would
   * collide.
   */
  anchorPrefix?: string;
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

export default function StreamFieldRenderer({
  blocks,
  mentionHighlight,
  variant = 'inline',
  anchorPrefix,
}: StreamFieldRendererProps) {
  if (!blocks || blocks.length === 0) {
    return null;
  }

  const wrapper =
    variant === 'article' ? 'mx-auto w-full max-w-[70ch] text-[15px]' : 'prose prose-lg max-w-none';

  return (
    <div className={wrapper}>
      {blocks.map((block, index) => {
        const rendered = (
          <StreamFieldBlock
            key={block.id || index}
            block={block}
            mentionHighlight={mentionHighlight}
          />
        );
        if (!anchorPrefix) return rendered;
        // scroll-mt keeps the anchored block clear of the sticky header.
        return (
          <div key={block.id || index} id={`${anchorPrefix}-${index}`} className="scroll-mt-24">
            {rendered}
          </div>
        );
      })}
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
  mentionHighlight?: boolean;
}

function StreamFieldBlock({ block, mentionHighlight }: StreamFieldBlockProps) {
  const { type } = block;

  switch (type) {
    case 'heading': {
      // Backend: CharBlock (simple string)
      return (
        <h2 className="mt-9 mb-3.5 text-[24px] font-semibold leading-snug text-balance text-ink">
          {block.value}
        </h2>
      );
    }

    case 'paragraph':
      // Backend: RichTextBlock (HTML string). Forum posts (mentionHighlight)
      // sanitize under the tighter FORUM allowlist to match nh3 (M32).
      return (
        <SafeHTML
          html={block.value}
          className="mb-4 leading-relaxed text-ink-2"
          preset={mentionHighlight ? SANITIZE_PRESETS.FORUM : SANITIZE_PRESETS.STREAMFIELD}
          postProcess={mentionHighlight ? highlightMentions : undefined}
        />
      );

    case 'image': {
      // Backend (forum PR-3): ImageChooserBlock → {id, url, alt, width, height}.
      // url is relative (`/media/...`) — resolve against the API origin like
      // every other blog image consumer (BlogCard, BlogDetailPage cover).
      const { url, alt } = block.value;
      return (
        <img
          src={mediaUrl(url)}
          alt={alt || ''}
          className="my-5 mx-auto h-auto max-w-full rounded-md"
        />
      );
    }

    case 'quote': {
      // Backend: StructBlock with quote_text (RichTextBlock) and attribution (CharBlock)
      const { value } = block;
      const quoteText = typeof value === 'string' ? value : (value.quote_text ?? value.quote ?? '');
      const attribution = typeof value === 'string' ? undefined : value.attribution;

      return (
        <blockquote className="my-8 rounded-r-md border-l-2 border-secondary bg-surface-2/50 py-4 pl-6 pr-4 italic text-ink-2">
          {/* SECURITY: a forum quote is a Wagtail BlockQuoteBlock (TextBlock) —
              PLAIN TEXT that api/sanitize.py deliberately leaves untouched
              ("text by contract"), so a direct API POST can put `<script>` in it.
              Render it as text (React escapes) rather than through
              renderTextOrSafeHtml, which would treat any value containing `<` as
              HTML under the broad blog STREAMFIELD preset. Blog quotes come from
              trusted Wagtail editors and keep the rich-text path (todo 276 / M1).
              whitespace-pre-line preserves the "\n\n" paragraph joins that
              forumBody.ts writes. */}
          {quoteText &&
            (mentionHighlight ? (
              <div className="mb-2 text-[17px] whitespace-pre-line">{quoteText}</div>
            ) : (
              renderTextOrSafeHtml(quoteText, 'mb-2 text-[17px]')
            ))}
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
        <pre className="my-6 overflow-x-auto rounded-md border border-line bg-surface-2/60 p-4 font-mono text-[13px] text-ink">
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
        <div className="my-8 rounded-md border border-line bg-surface-2/50 p-6">
          <h3 className="mb-3 text-[19px] font-semibold text-ink">{plantName}</h3>
          {value.scientific_name && (
            <p className="text-sm italic text-ink-3 mb-3">{value.scientific_name}</p>
          )}
          {value.image && (
            <img
              src={value.image.url}
              alt={value.image.alt || plantName}
              className="w-full h-64 object-cover rounded-lg mb-4 shadow-md"
            />
          )}
          {description && renderTextOrSafeHtml(description, 'text-ink-2 mb-4')}
          {careValue && (
            <p className="mt-4 flex items-center text-sm font-semibold text-ok">
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
          ? 'inline-block rounded-pill border border-line bg-surface-2/60 px-6 py-2.5 text-[13.5px] font-semibold text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink'
          : buttonStyle === 'outline'
            ? 'inline-block rounded-pill border border-line bg-transparent px-6 py-2.5 text-[13.5px] font-semibold text-ink-2 transition-colors hover:bg-surface-2/60 hover:text-ink'
            : 'canopy-cta inline-block rounded-pill px-6 py-2.5 text-[13.5px] font-semibold';

      return (
        <div className="canopy-card my-8 rounded-md p-8 text-center">
          <h3 className="mb-2 text-[19px] font-semibold text-ink">{title}</h3>
          {description && renderTextOrSafeHtml(description, 'mb-6 text-ink-2')}
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
