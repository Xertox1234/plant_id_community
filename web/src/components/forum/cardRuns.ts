import type { StreamFieldBlock } from '@/types/blog';
import { safeExternalUrl, shortLinkAddress } from '@/utils/externalUrl';

/**
 * The block types that render as a card (todo 429). A run of 2+ consecutive
 * cards shows the first as a full card and each later one as a compact row.
 * One set, so a new card type joins by one entry (the Flutter mirror is
 * `forumCardBlockTypes` in forum_body_renderer.dart).
 */
export const CARD_BLOCK_TYPES: ReadonlySet<StreamFieldBlock['type']> = new Set([
  'embed',
  'link_preview',
]);

/**
 * A card that can join a run: a card type that renders something. A
 * `link_preview` with a null envelope or an unusable URL renders nothing
 * (LinkPreviewCard returns null), so it must not count.
 */
export function isCardBlock(block: StreamFieldBlock): boolean {
  if (!CARD_BLOCK_TYPES.has(block.type)) return false;
  // The same URL check the row makes, so a card joins a run only if it renders.
  if (block.type === 'embed') return Boolean(safeExternalUrl(block.value?.url));
  if (block.type === 'link_preview') {
    return Boolean(
      block.value && safeExternalUrl(block.value.url) && shortLinkAddress(block.value.url)
    );
  }
  return false;
}

export interface IndexedBlock {
  block: StreamFieldBlock;
  index: number;
}

export type BodyItem =
  | { kind: 'block'; item: IndexedBlock }
  | { kind: 'run'; first: IndexedBlock; rest: IndexedBlock[] };

/** Group runs of 2+ consecutive card blocks; everything else stays a block. */
export function groupCardRuns(blocks: StreamFieldBlock[]): BodyItem[] {
  const items: BodyItem[] = [];
  const card = blocks.map(isCardBlock);
  for (let i = 0; i < blocks.length; i++) {
    let end = i;
    while (card[i] && end + 1 < blocks.length && card[end + 1]) end++;
    if (end === i) {
      items.push({ kind: 'block', item: { block: blocks[i], index: i } });
    } else {
      const rest: IndexedBlock[] = [];
      for (let j = i + 1; j <= end; j++) rest.push({ block: blocks[j], index: j });
      items.push({ kind: 'run', first: { block: blocks[i], index: i }, rest });
    }
    i = end;
  }
  return items;
}
