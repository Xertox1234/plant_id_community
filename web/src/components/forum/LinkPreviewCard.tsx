import { useId, useState } from 'react';
import type { LinkPreviewBlockValue } from '@/types/blog';
import { mediaUrl } from '@/services/blogService';
import { safeExternalUrl, shortLinkAddress } from '@/utils/externalUrl';

interface LinkPreviewCardProps {
  /** The composer's `LinkPreview` fits too: it only adds `available`. */
  preview: LinkPreviewBlockValue;
  /**
   * `composer` (default): the live preview under the editor, from the
   * preview endpoint, whose image is the linked site's own (https only).
   * `post`: a card stored in a post body (todo 428), whose image is OUR
   * media copy — resolved like every other media URL, never a third party.
   */
  variant?: 'composer' | 'post';
}

/**
 * A link shown as a card. The address line is the SHORTENED URL (origin plus
 * "…", `shortLinkAddress`) and the spoken label is the title plus that short
 * address; the full URL is only the `href` and the `title` attribute, so
 * hovering shows it (owner decision, todo 428). `aria-describedby` points at
 * the new-tab hint so the accessible description is that hint: with no
 * description of its own, a link's `title` becomes its description, and a
 * screen reader would read the full URL out after all.
 */
export default function LinkPreviewCard({ preview, variant = 'composer' }: LinkPreviewCardProps) {
  const [failedImage, setFailedImage] = useState<string | null>(null);
  const hintId = useId();
  const href = safeExternalUrl(preview.url);
  const address = shortLinkAddress(preview.url);
  if (!href || !address) return null;

  const imageSrc =
    variant === 'post'
      ? preview.image_url
        ? safeExternalUrl(mediaUrl(preview.image_url))
        : null
      : safeExternalUrl(preview.image_url, true);
  const showImage = Boolean(imageSrc) && failedImage !== imageSrc;
  const title = preview.title || preview.site_name || preview.domain || address;
  const source = preview.site_name || preview.domain;
  const label = title === address ? address : `${title}, ${address}`;

  return (
    <div className={variant === 'post' ? 'my-5' : 'border-t border-line-2 bg-surface p-3 sm:p-4'}>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        title={href}
        aria-label={label}
        aria-describedby={hintId}
        className="block overflow-hidden rounded-sm border border-line-2 bg-surface-2 text-ink transition-colors hover:bg-surface-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
        data-testid="forum-link-preview"
      >
        {showImage && (
          <img
            src={imageSrc ?? undefined}
            alt=""
            className="aspect-[1.91/1] w-full object-cover"
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => setFailedImage(imageSrc)}
          />
        )}
        <div className="space-y-1 p-3 sm:p-4">
          {source && (
            <p className="truncate text-xs font-medium uppercase tracking-wide text-ink-3">
              {source}
            </p>
          )}
          <p className="line-clamp-2 text-sm font-semibold leading-5 sm:text-base">{title}</p>
          {preview.description && (
            <p className="line-clamp-3 text-sm leading-5 text-ink-2">{preview.description}</p>
          )}
          {title !== address && <p className="truncate text-xs text-ink-3">{address}</p>}
        </div>
        <span id={hintId} className="sr-only">
          Opens in a new tab
        </span>
      </a>
    </div>
  );
}
