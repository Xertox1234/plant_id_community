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
  /** A quote of a specific post (todo 342): the quoted post id + plain text.
   * The server validates the id (visible, not block-paired), caps distinct
   * quoted posts per body and the text length (QUOTE_MAX_CHARS, 1000) — none
   * of that is re-checked here; a 400 surfaces as the reply error. */
  | { type: 'post_quote'; value: { post: number; text: string } }
  | { type: 'image'; value: number }
  | { type: 'embed'; value: string };

/**
 * Client-side cap on the text the Quote action lifts out of a post (todo
 * 342) — half the server's QUOTE_MAX_CHARS (1000), so a long post never 400s
 * the reply that quotes it. Cut with an ellipsis, not silently.
 */
export const QUOTE_TEXT_MAX_CHARS = 500;

/** The quoted post id a composer blockquote carries, or null when absent/invalid. */
function quotedPostId(el: Element): number | null {
  const raw = el.getAttribute('data-post-id');
  if (!raw || !/^\d+$/.test(raw)) return null;
  const id = Number(raw);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

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
 * An element's visible text with each `<br>` as "\n". `textContent` drops a
 * hard break entirely ("one<br>two" -> "onetwo"). Only text nodes and breaks
 * contribute, so no tag ever leaks into the plain `text` of a quote block.
 */
function textWithBreaks(el: Element): string {
  let out = '';
  for (const node of Array.from(el.childNodes)) {
    if (node.nodeType === Node.TEXT_NODE) {
      out += node.textContent ?? '';
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      out += (node as Element).tagName === 'BR' ? '\n' : textWithBreaks(node as Element);
    }
  }
  return out;
}

/** Trim each line and the whole, keeping the line structure ("a \n b" -> "a\nb"). */
function trimLines(text: string): string {
  return text
    .split('\n')
    .map((line) => line.trim())
    .join('\n')
    .trim();
}

/**
 * A blockquote's visible text, one entry per child block. TipTap emits
 * `<blockquote><p>a</p><p>b</p></blockquote>`, so raw `textContent` would mash
 * "ab" together — join the children instead. A `<br>` inside a child (the
 * form quoteParagraphsHtml writes a single "\n" as) reads back as "\n".
 */
function blockquoteText(el: Element): string {
  const parts = Array.from(el.children)
    .map((child) => trimLines(textWithBreaks(child)))
    .filter(Boolean);
  // No element children (bare text inside the quote) — fall back to the
  // blockquote's own text.
  return parts.length > 0 ? parts.join('\n\n') : trimLines(textWithBreaks(el));
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
      // Only BODY-LEVEL blockquotes are detected: one nested inside a list
      // item (or any other element) stays in its paragraph's markup and is
      // flattened exactly like that (pre-existing limitation, not handled).
      // One carrying `data-post-id` (the Quote action, todo 342) is a
      // `post_quote` of that post instead; a missing or malformed id falls
      // back to the legacy free-form quote rather than a guaranteed 400.
      flush();
      const text = blockquoteText(el);
      const postId = quotedPostId(el);
      if (text && postId != null) {
        blocks.push({ type: 'post_quote', value: { post: postId, text } });
      } else if (text) {
        blocks.push({ type: 'quote', value: text });
      }
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
        return `<blockquote>${quoteParagraphsHtml(text)}</blockquote>`;
      }
      if (block.type === 'post_quote') {
        // Same plain-text contract as `quote` (escaped on the way in), plus
        // the quoted post id as `data-post-id` so htmlToBodyBlocks re-derives
        // a `post_quote` block — REGARDLESS of `available`. The server exempts
        // the ids the stored body already carries from the availability
        // re-check on edit (`existing_quote_ids`), so a quote whose post has
        // since gone keeps its id; downgrading it to a plain `quote` here
        // would silently rewrite the author's post on every re-edit and lose
        // the attribution for good. Only a malformed id falls back.
        const { text, post_id } = block.value;
        if (!text.trim()) return '';
        const paragraphs = quoteParagraphsHtml(text);
        return Number.isSafeInteger(post_id) && post_id > 0
          ? `<blockquote data-post-id="${post_id}">${paragraphs}</blockquote>`
          : `<blockquote>${paragraphs}</blockquote>`;
      }
      return '';
    })
    .join('');
}

/**
 * Plain quote text -> `<p>` per paragraph, escaped (see escapeHtml). A single
 * "\n" inside a paragraph (a list-sourced quote — postQuoteText joins list
 * items with one "\n" — or a non-browser client) becomes `<br>`: written as
 * a bare newline ProseMirror would collapse it to a space in the editor, and
 * blockquoteText reads the `<br>` back as "\n", so the round trip is stable.
 */
function quoteParagraphsHtml(text: string): string {
  return (
    text
      // Split on a BLANK line only. Splitting on /\n+/ would rewrite a
      // single "\n" into "\n\n" on every re-edit, since blockquoteText
      // always rejoins paragraphs with "\n\n".
      .split(/\n{2,}/)
      .map((paragraph) =>
        paragraph
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean)
          .map((line) => escapeHtml(line))
          .join('<br>')
      )
      .filter(Boolean)
      .map((paragraph) => `<p>${paragraph}</p>`)
      .join('')
  );
}

/**
 * Composer HTML for the Quote action (todo 342): a `post_quote` blockquote of
 * `postId` holding `text`, in exactly the form htmlToBodyBlocks turns back
 * into `{type: 'post_quote', value: {post, text}}`. `text` is escaped here —
 * it comes from postQuoteText, i.e. from another member's post.
 */
export function postQuoteHtml(postId: number, text: string): string {
  return `<blockquote data-post-id="${postId}">${quoteParagraphsHtml(text)}</blockquote>`;
}

/** Visible text of one rich-text paragraph block, one entry per top-level element. */
function richTextParagraphs(html: string): string[] {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  // Collapse runs of spaces but KEEP line structure: a hard break in the
  // source (`<p>a<br>b</p>`, Shift+Enter) is lifted as "a\nb", which
  // quoteParagraphsHtml renders back as <br> — never as the merged "ab".
  const collapse = (s: string | null | undefined) => trimLines((s ?? '').replace(/[^\S\n]+/g, ' '));
  const children = Array.from(doc.body.children);
  if (children.length === 0) return [collapse(doc.body.textContent)].filter(Boolean);
  return children
    .map((el) =>
      // A list's textContent would mash its items together — one line each.
      el.tagName === 'UL' || el.tagName === 'OL'
        ? Array.from(el.querySelectorAll('li'))
            .map((li) => collapse(textWithBreaks(li)))
            .filter(Boolean)
            .join('\n')
        : collapse(textWithBreaks(el))
    )
    .filter(Boolean);
}

/**
 * The plain text the Quote action lifts out of a post body (todo 342):
 * paragraphs (and headings) as text, blank-line separated; a legacy `quote`
 * as its text. Skipped on purpose: `post_quote` blocks (quoting a quote
 * would put a third person's words under this author's name), images,
 * embeds and code. Cut at `maxChars` with an ellipsis. '' when the post has
 * no quotable text (an image-only post) — the caller must not quote nothing,
 * since the server rejects an empty quote.
 */
export function postQuoteText(
  body: StreamFieldBlock[] | null | undefined,
  maxChars = QUOTE_TEXT_MAX_CHARS
): string {
  if (!body) return '';
  const parts: string[] = [];
  for (const block of body) {
    if (block.type === 'paragraph') {
      if (typeof block.value === 'string' && block.value)
        parts.push(...richTextParagraphs(block.value));
    } else if (block.type === 'heading') {
      parts.push(block.value.trim());
    } else if (block.type === 'quote') {
      const v = block.value;
      parts.push((typeof v === 'string' ? v : (v.quote_text ?? v.quote ?? '')).trim());
    }
  }
  const text = parts.filter(Boolean).join('\n\n');
  if (text.length <= maxChars) return text;
  return `${text.slice(0, maxChars).trimEnd()}…`;
}
