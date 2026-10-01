import type { LinkPreviewBlockValue } from '@/types/blog';
import { mediaUrl } from '@/services/blogService';
import { safeExternalUrl, shortLinkAddress } from '@/utils/externalUrl';

/** What a link card shows and says, however big it is drawn. */
export interface LinkPreviewDisplay {
  /** The full URL: the link's `href` (and its hover `title`), never spoken. */
  href: string;
  /** The SHORT address (`shortLinkAddress`): what the card shows and says. */
  address: string;
  /** The page title, falling back to its site name, its domain, then the address. */
  title: string;
  /** The second line: the address, or '' when the title already IS the address. */
  detail: string;
  /** The accessible name: "title, address", or the address alone (todo 453). */
  label: string;
  /** The image to show, or null. */
  imageSrc: string | null;
}

/**
 * The one place a link card's display is derived (todo 453): the full card
 * (`LinkPreviewCard`), its compact row (`CompactCardRow`) and the run rule
 * (`isCardBlock`) all read it, so "renders nothing" and "joins a run" cannot
 * drift apart. Null means the card renders nothing: no envelope, or a URL
 * that `safeExternalUrl` refuses. The Flutter twin is `linkPreviewDisplay`
 * in `forum_body_block.dart`.
 *
 * `variant` picks the image source. `composer` (the live preview under the
 * editor): the linked site's own image, https only. `post` (a card stored in a
 * post body, todo 428): OUR media copy, resolved like every other media URL.
 *
 * The parameter is the block value's shape, so the composer's `LinkPreview`
 * (which only adds `available`) fits too.
 */
export function linkPreviewDisplay(
  preview: LinkPreviewBlockValue | null | undefined,
  variant: 'composer' | 'post' = 'post'
): LinkPreviewDisplay | null {
  if (!preview) return null;
  const href = safeExternalUrl(preview.url);
  const address = shortLinkAddress(preview.url);
  if (!href || !address) return null;
  const title = preview.title || preview.site_name || preview.domain || address;
  const detail = title === address ? '' : address;
  const imageSrc =
    variant === 'post'
      ? preview.image_url
        ? safeExternalUrl(mediaUrl(preview.image_url))
        : null
      : safeExternalUrl(preview.image_url, true);
  return {
    href,
    address,
    title,
    detail,
    label: detail ? `${title}, ${detail}` : title,
    imageSrc,
  };
}
