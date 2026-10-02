import type { EmbedBlockValue } from '@/types/blog';
import { shortLinkAddress } from '@/utils/externalUrl';

/** What a video card is called, however big it is drawn (todo 518). */
export interface EmbedDisplay {
  /**
   * The video's title or, for an untitled video, its SHORT address
   * (`shortLinkAddress`), never the full URL a screen reader would spell out
   * (todos 505, 518). The raw URL only when it is not an http(s) link, which
   * never joins a run, so only a full card can show it.
   */
  title: string;
  /** A compact row's second line: the provider's name, or ''. */
  detail: string;
  /** A compact row's accessible name: "title, provider", or the title alone. */
  label: string;
}

/**
 * The one place a video card's name is derived (todos 505, 518). Its compact
 * row (`CompactCardRow`) reads all three fields; its full card (the `embed`
 * case of `StreamFieldRenderer`) reads `title` for the player's iframe `title`
 * or the fallback card's first line. So an untitled video is named the same
 * way wherever it falls in a run. The full card keeps its own second line
 * ("Watch on PROVIDER" or "Open link"), so its name is not `label`. The
 * Flutter twin is `_embedTitle` / `_embedRow` in `forum_body_renderer.dart`.
 */
export function embedDisplay(
  value: Pick<EmbedBlockValue, 'url' | 'title' | 'provider_name'>
): EmbedDisplay {
  const title = value.title || shortLinkAddress(value.url) || value.url;
  const detail = value.provider_name || '';
  return { title, detail, label: detail ? `${title}, ${detail}` : title };
}
