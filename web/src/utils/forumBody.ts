/**
 * Forum body <-> composer-HTML serialization (Spec 2 PR-3, true interleaving).
 *
 * The TipTap composer emits one HTML string with inline `<img data-image-id>`
 * nodes. The wagtail_forum API instead models a body as a StreamField list where
 * images are their OWN `image` blocks (referencing a wagtail image id). These two
 * functions are inverses: they let text and images interleave in the composer
 * while persisting the block structure the backend validates and renders.
 */
import type { StreamFieldBlock } from '@/types/blog';

/** A forum body block as SENT to the API (an image references the wagtail id). */
export type ForumBodyWriteBlock =
  | { type: 'paragraph'; value: string }
  | { type: 'image'; value: number };

/**
 * Composer HTML -> forum body blocks. Runs of rich text become `paragraph`
 * blocks; each inline `<img data-image-id>` becomes its own `image` block (value
 * = the wagtail image id — the url/alt in the editor are display-only and are
 * re-derived by the backend, so they are intentionally dropped here).
 */
export function htmlToBodyBlocks(html: string): ForumBodyWriteBlock[] {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const blocks: ForumBodyWriteBlock[] = [];
  let buffer: string[] = [];
  const flush = () => {
    const value = buffer.join('').trim();
    if (value) blocks.push({ type: 'paragraph', value });
    buffer = [];
  };
  for (const node of Array.from(doc.body.childNodes)) {
    const el = node.nodeType === Node.ELEMENT_NODE ? (node as Element) : null;
    const imageId = el?.tagName === 'IMG' ? el.getAttribute('data-image-id') : null;
    if (imageId) {
      flush();
      blocks.push({ type: 'image', value: Number(imageId) });
    } else if (el) {
      buffer.push(el.outerHTML);
    } else if (node.textContent?.trim()) {
      buffer.push(node.textContent);
    }
  }
  flush();
  return blocks;
}

/**
 * Forum body blocks -> composer HTML, the inverse of htmlToBodyBlocks. Image
 * blocks become `<img data-image-id>` so re-editing round-trips the wagtail id
 * through TipTap. Block types the forum composer does not produce render empty.
 */
export function bodyBlocksToHtml(body: StreamFieldBlock[] | null | undefined): string {
  if (!body) return '';
  return body
    .map((block) => {
      if (block.type === 'image') {
        const { id, url, alt } = block.value;
        const safeAlt = (alt || '').replace(/"/g, '&quot;');
        return `<img src="${url}" alt="${safeAlt}" data-image-id="${id}">`;
      }
      if (block.type === 'paragraph') {
        return typeof block.value === 'string' ? block.value : '';
      }
      return '';
    })
    .join('');
}
