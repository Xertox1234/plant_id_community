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
  | { type: 'quote'; value: string }
  | { type: 'image'; value: number };

/**
 * Escape text destined for composer HTML. `quote` is a Wagtail `BlockQuoteBlock`
 * (a `TextBlock`) — its value is PLAIN TEXT, never markup, and the server
 * deliberately leaves it unsanitized ("text by contract", api/sanitize.py). So a
 * value containing `<` must be escaped on the way back into the editor, or it
 * re-parses as real document structure on the next edit.
 */
function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/**
 * A blockquote's visible text, one entry per child block. TipTap emits
 * `<blockquote><p>a</p><p>b</p></blockquote>`, so raw `textContent` would mash
 * "ab" together — join the children instead.
 */
function blockquoteText(el: Element): string {
  const parts = Array.from(el.children)
    .map((child) => child.textContent?.trim() ?? '')
    .filter(Boolean);
  // No element children (bare text inside the quote) — fall back to textContent.
  return parts.length > 0 ? parts.join('\n\n') : (el.textContent?.trim() ?? '');
}

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
    } else if (el?.tagName === 'BLOCKQUOTE') {
      // A top-level blockquote becomes its OWN `quote` block, not inline markup
      // in a paragraph: the server's nh3 allowlist has no <blockquote>, so a
      // quote left inside rich text would be silently flattened to plain text.
      flush();
      const text = blockquoteText(el);
      if (text) blocks.push({ type: 'quote', value: text });
      // An image nested in the quote is invisible to `textContent` — hoist it
      // out as its own block rather than dropping the user's content silently.
      for (const img of Array.from(el.querySelectorAll('img[data-image-id]'))) {
        blocks.push({ type: 'image', value: Number(img.getAttribute('data-image-id')) });
      }
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
      if (block.type === 'quote') {
        // Plain text in, escaped markup out — see escapeHtml. One <p> per
        // paragraph so htmlToBodyBlocks re-derives the same "\n\n"-joined value
        // (round-trip stability).
        const text = typeof block.value === 'string' ? block.value : '';
        if (!text.trim()) return '';
        const paragraphs = text
          // Split on a BLANK line only. Splitting on /\n+/ would rewrite a
          // single "\n" (possible from a non-browser client) into "\n\n" on
          // every re-edit, since blockquoteText always rejoins with "\n\n".
          .split(/\n{2,}/)
          .map((line) => line.trim())
          .filter(Boolean)
          .map((line) => `<p>${escapeHtml(line)}</p>`)
          .join('');
        return `<blockquote>${paragraphs}</blockquote>`;
      }
      return '';
    })
    .join('');
}
