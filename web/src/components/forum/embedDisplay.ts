import type { EmbedBlockValue, StreamFieldBlock } from '@/types/blog';
import { shortLinkAddress } from '@/utils/externalUrl';

/** What a video card is called, however big it is drawn (todo 518). */
export interface EmbedDisplay {
  /**
   * The video's title or, for an untitled video, its SHORT address
   * (`shortLinkAddress`), never the full URL a screen reader would spell out
   * (todos 505, 518). The raw URL only when it is not an http(s) link, which
   * never joins a run, so only a full card can show it. When two untitled
   * videos in one post body would share that name, each carries an ordinal,
   * "https://youtu.be/… (2)" (`untitledEmbedOrdinals`, todo 563).
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
  value: Pick<EmbedBlockValue, 'url' | 'title' | 'provider_name'>,
  ordinal?: number
): EmbedDisplay {
  const base = untitledName(value);
  const title = value.title || (ordinal ? `${base} (${ordinal})` : base);
  const detail = value.provider_name;
  return { title, detail, label: detail ? `${title}, ${detail}` : title };
}

/** An untitled video's base name: its short address, else its raw URL. */
function untitledName(value: Pick<EmbedBlockValue, 'url'>): string {
  return shortLinkAddress(value.url) || value.url;
}

/**
 * The ordinal each untitled video carries in one post body, keyed by its index
 * in `blocks` (todo 563, owner decision 2026-10-11). Two untitled videos on one
 * host share a short address, so a screen reader's frame list could not tell
 * their players apart. Only names that collide get one, numbered 1, 2, … in
 * body order; a lone untitled video keeps its bare short address. The scope is
 * one body (one renderer), never the page: two posts on one thread can still
 * share a name. The Flutter twin is `untitledEmbedOrdinals` in
 * `forum_body_renderer.dart`.
 */
export function untitledEmbedOrdinals(blocks: readonly StreamFieldBlock[]): Map<number, number> {
  const byName = new Map<string, number[]>();
  blocks.forEach((block, index) => {
    if (block.type !== 'embed' || block.value.title) return;
    const name = untitledName(block.value);
    if (!name) return;
    byName.set(name, [...(byName.get(name) ?? []), index]);
  });
  const ordinals = new Map<number, number>();
  for (const indexes of byName.values()) {
    if (indexes.length < 2) continue;
    indexes.forEach((index, i) => ordinals.set(index, i + 1));
  }
  return ordinals;
}
