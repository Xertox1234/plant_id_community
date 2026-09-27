import { useEffect, useRef, useState, type ReactNode } from 'react';
import { mediaUrl } from '@/services/blogService';
import { safeExternalUrl, shortLinkAddress } from '@/utils/externalUrl';
import type { StreamFieldBlock } from '@/types/blog';

interface CompactCardRowProps {
  block: StreamFieldBlock;
  /** The block's full card, shown in place of a video row once it is clicked. */
  renderFull: () => ReactNode;
}

const ROW_CLASS =
  'flex min-h-11 w-full items-center gap-3 rounded-md border border-line bg-surface-2 p-2 text-left text-ink hover:bg-surface-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary';

/**
 * A card after the first in a run (todo 429): a small thumbnail beside the
 * title and a second line, on the card's surface and border. Its accessible
 * name is "title, <second line>". A video row's second line is its provider;
 * a link row's is the SHORT ADDRESS derived from the URL, never the page's own
 * og:site_name, so a row cannot claim to be a site it does not link to (the
 * todo 428 rule for the full card). A video row with a player swaps itself for
 * that player when clicked, so no iframe loads until asked for, and focus
 * moves to the player so a keyboard user is not dropped to <body>. Any other
 * row is a link, like its full card.
 */
export default function CompactCardRow({ block, renderFull }: CompactCardRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);
  const playerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (expanded) playerRef.current?.focus();
  }, [expanded]);

  let href: string | null = null;
  let title = '';
  let detail = '';
  let thumbnail: string | null = null;
  let playable = false;
  if (block.type === 'embed') {
    const { url, title: t, provider_name, thumbnail_url, embed_url } = block.value;
    href = safeExternalUrl(url);
    title = t || url;
    detail = provider_name;
    thumbnail = safeExternalUrl(thumbnail_url);
    playable = Boolean(embed_url);
  } else if (block.type === 'link_preview' && block.value) {
    const preview = block.value;
    href = safeExternalUrl(preview.url);
    const address = shortLinkAddress(preview.url) || '';
    title = preview.title || preview.site_name || preview.domain || address;
    detail = title === address ? '' : address;
    thumbnail = preview.image_url ? safeExternalUrl(mediaUrl(preview.image_url)) : null;
  }
  if (!href) return null;
  const label = detail ? `${title}, ${detail}` : title;

  if (expanded) {
    // The player replaces the button the user pressed; focus follows it.
    return (
      <div
        ref={playerRef}
        tabIndex={-1}
        role="group"
        aria-label={label}
        className="outline-none [&>*]:my-0"
      >
        {renderFull()}
      </div>
    );
  }

  const body = (
    <>
      <span className="h-12 w-[72px] shrink-0 overflow-hidden rounded-sm bg-surface-3">
        {thumbnail && !imageFailed && (
          <img
            src={thumbnail}
            alt=""
            className="h-full w-full object-cover"
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => setImageFailed(true)}
          />
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{title}</span>
        {detail && <span className="block truncate text-xs text-ink-3">{detail}</span>}
      </span>
    </>
  );

  if (playable) {
    return (
      <button
        type="button"
        className={ROW_CLASS}
        aria-label={label}
        onClick={() => setExpanded(true)}
      >
        {body}
      </button>
    );
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={ROW_CLASS}
      aria-label={label}
    >
      {body}
    </a>
  );
}
