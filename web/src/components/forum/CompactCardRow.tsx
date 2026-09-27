import { useState, type ReactNode } from 'react';
import { mediaUrl } from '@/services/blogService';
import { safeExternalUrl, shortLinkAddress } from '@/utils/externalUrl';
import type { StreamFieldBlock } from '@/types/blog';

interface CompactCardRowProps {
  block: StreamFieldBlock;
  /** The block's full card, shown in place of a video row once it is clicked. */
  renderFull: () => ReactNode;
}

const ROW_CLASS =
  'flex min-h-11 w-full items-center gap-3 rounded-md border border-line bg-surface-2 p-2 text-left text-ink hover:bg-surface-3';

/**
 * A card after the first in a run (todo 429): a small thumbnail beside the
 * title and the site, on the card's surface and border. Its accessible name
 * is "title, site". A video row with a player swaps itself for that player
 * when clicked, so no iframe loads until asked for; any other row is a link,
 * like its full card.
 */
export default function CompactCardRow({ block, renderFull }: CompactCardRowProps) {
  const [expanded, setExpanded] = useState(false);
  if (expanded) return <>{renderFull()}</>;

  let href: string | null = null;
  let title = '';
  let site = '';
  let thumbnail: string | null = null;
  let playable = false;
  if (block.type === 'embed') {
    const { url, title: t, provider_name, thumbnail_url, embed_url } = block.value;
    href = safeExternalUrl(url);
    title = t || url;
    site = provider_name;
    thumbnail = safeExternalUrl(thumbnail_url);
    playable = Boolean(embed_url);
  } else if (block.type === 'link_preview' && block.value) {
    const preview = block.value;
    href = safeExternalUrl(preview.url);
    const address = shortLinkAddress(preview.url) || preview.url;
    title = preview.title || preview.site_name || preview.domain || address;
    site = preview.site_name || preview.domain;
    thumbnail = preview.image_url ? safeExternalUrl(mediaUrl(preview.image_url)) : null;
  }
  if (!href) return null;

  const label = site ? `${title}, ${site}` : title;
  const body = (
    <>
      <span className="h-12 w-[72px] shrink-0 overflow-hidden rounded-sm bg-surface-3">
        {thumbnail && <img src={thumbnail} alt="" className="h-full w-full object-cover" />}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{title}</span>
        {site && <span className="block truncate text-xs text-ink-3">{site}</span>}
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
