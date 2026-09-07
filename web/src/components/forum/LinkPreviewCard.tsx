import { useState } from 'react';
import type { LinkPreview } from '@/types/forum';

interface LinkPreviewCardProps {
  preview: LinkPreview;
}

function safeExternalUrl(value: string | null, httpsOnly = false): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    if (
      !['http:', 'https:'].includes(parsed.protocol) ||
      (httpsOnly && parsed.protocol !== 'https:') ||
      !parsed.hostname ||
      parsed.username ||
      parsed.password
    ) {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

export default function LinkPreviewCard({ preview }: LinkPreviewCardProps) {
  const [failedImage, setFailedImage] = useState<string | null>(null);
  const href = safeExternalUrl(preview.url);
  if (!href) return null;

  const imageSrc = safeExternalUrl(preview.image_url, true);
  const showImage = Boolean(imageSrc) && failedImage !== imageSrc;
  const title = preview.title || preview.site_name || preview.domain || href;
  const source = preview.site_name || preview.domain;

  return (
    <div className="border-t border-line-2 bg-surface p-3 sm:p-4">
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="forum-link-preview-card block overflow-hidden rounded-sm border border-line-2 bg-surface-2 text-ink transition-colors hover:bg-surface-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
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
          <h3 className="line-clamp-2 text-sm font-semibold leading-5 sm:text-base">{title}</h3>
          {preview.description && (
            <p className="line-clamp-3 text-sm leading-5 text-ink-2">{preview.description}</p>
          )}
          <p className="truncate text-xs text-ink-3">{preview.domain || href}</p>
        </div>
      </a>
    </div>
  );
}
