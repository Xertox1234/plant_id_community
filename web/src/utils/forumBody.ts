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
  | { type: 'image'; value: number }
  | { type: 'embed'; value: string };

/**
 * A pasted video link becomes an `embed` block (todo 344) when it is the
 * ONLY content of its paragraph. Mirrors the server's known-player set —
 * the server's finder allowlist is still the authority (400 otherwise).
 */
const PROVIDER_VIDEO_URL =
  /^https?:\/\/(?:(?:[-\w]+\.)?youtube\.com\/(?:watch\?\S+|shorts\/\S+|live\/\S+|v\/\S+)|youtu\.be\/\S+|(?:www\.)?vimeo\.com\/\S+)$/;

/** The bare provider URL if `el` is a paragraph holding exactly one, else null. */
function embedUrlOf(el: Element): string | null {
  if (el.tagName !== 'P' || el.querySelector('img')) return null;
  const text = (el.textContent ?? '').trim();
  return PROVIDER_VIDEO_URL.test(text) ? text : null;
}

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
 *
 * What the backend re-derives `alt` FROM changed in M7: it is now the author's
 * own text, captured at upload time and stored on the image row, not the upload
 * filename. Dropping the editor's copy here is still correct — but it is also
 * why alt cannot be edited after insert without re-uploading the image.
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
    const embedUrl = el ? embedUrlOf(el) : null;
    if (imageId) {
      flush();
      blocks.push({ type: 'image', value: Number(imageId) });
    } else if (embedUrl) {
      // A paragraph that is just a video link → its own embed block; the
      // server unfurls it (todo 344). Re-editing round-trips through
      // bodyBlocksToHtml's <p><a> form back to this branch.
      flush();
      blocks.push({ type: 'embed', value: embedUrl });
    } else if (el?.tagName === 'BLOCKQUOTE') {
      // A top-level blockquote becomes its OWN `quote` block, not inline markup
      // in a paragraph: the server's nh3 allowlist has no <blockquote>, so a
      // quote left inside rich text would be silently flattened to plain text.
      flush();
      const text = blockquoteText(el);
      if (text) blocks.push({ type: 'quote', value: text });
      // An image nested in the quote is invisible to `textContent` — hoist it
      // out as its own block rather than dropping the user's content silently.
      // Gate on the attribute exactly like the top-level branch above: a pasted
      // `<img data-image-id="">` would otherwise yield value 0, and a
      // non-numeric one NaN (serialized as null). Both fail the server's
      // validate_forum_body, so ONE unusable image would 400 the whole save
      // instead of just being dropped.
      for (const img of Array.from(el.querySelectorAll('img[data-image-id]'))) {
        const nestedId = img.getAttribute('data-image-id');
        if (nestedId) blocks.push({ type: 'image', value: Number(nestedId) });
      }
    } else if (el) {
      buffer.push(el.outerHTML);
    } else if (node.textContent?.trim()) {
      // A bare text node at body level. `buffer` is joined into a `paragraph`
      // block, whose value is HTML — so this text must be ESCAPED, or "a < b"
      // is re-parsed as markup downstream (CodeQL js/xss-through-dom: DOM text
      // reinterpreted as HTML). Escaping is also the correct rendering: the
      // user typed those characters, they did not author tags.
      buffer.push(escapeHtml(node.textContent));
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
      if (block.type === 'embed') {
        // The read shape is an envelope; only the original URL goes back
        // into the composer, as a link paragraph htmlToBodyBlocks recognises.
        // SECURITY: this is a hand-built HTML string later parsed into the
        // live composer DOM — React's own href guard does not apply here —
        // so a persisted URL with a non-http(s) scheme (a direct API POST
        // that skipped the composer) is dropped, not linked (review).
        const url = typeof block.value === 'string' ? block.value : block.value.url;
        if (!url || !/^https?:\/\//i.test(url)) return '';
        const safe = escapeHtml(url);
        return `<p><a href="${safe.replace(/"/g, '&quot;')}">${safe}</a></p>`;
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
