/**
 * Forum body <-> composer document serialization (Spec 2 PR-3, true
 * interleaving; TipTap JSON since todo 526).
 *
 * The TipTap composer holds ONE document with block-level image nodes. The
 * wagtail_forum API instead models a body as a StreamField list where images
 * are their OWN `image` blocks (referencing a wagtail image id). The two
 * converters here — `bodyBlocksToDoc` and `docToBodyBlocks` — are inverses:
 * they let text and images interleave in the composer while persisting the
 * block structure the backend validates and renders.
 *
 * Both work on TipTap JSON, never on composer HTML built from strings (todo
 * 526). An image's id, alt and decorative flag, a quoted post id, a quote's
 * text and an embed's URL travel as node attributes and text nodes, so no
 * persisted value is interpolated into markup and none passes through the HTML
 * parser — whose attribute normalisation (CR/CRLF to LF, NUL to U+FFFD) no
 * amount of escaping could prevent. The one HTML boundary left is a
 * `paragraph` block's value, which IS HTML by contract (server-sanitized): it
 * is parsed, and the composer's rich text printed, with the live editor's own
 * schema (forumEditorSchema).
 */
import type { JSONContent } from '@tiptap/react';
import { elementFromString, getHTMLFromFragment, getSchema } from '@tiptap/react';
import { DOMParser as SchemaDOMParser, Fragment, type Schema } from '@tiptap/pm/model';
import type { StreamFieldBlock } from '@/types/blog';
import { FORUM_SCHEMA_EXTENSIONS } from '../components/forum/forumEditorSchema';
import { stripHtml } from './sanitize';
import { safeExternalUrl } from './externalUrl';

/**
 * Whether `html` is an effectively-empty rich-text body.
 *
 * Was duplicated verbatim in ThreadDetailPage and NewThreadPage as
 * `html.replace(/<[^>]*>/g, '').trim() === ''`. That regex is not a sanitizer
 * and never was one (the value is only ever compared, never rendered), but it
 * mishandles a truncated tag and CodeQL flagged it as
 * `js/incomplete-multi-character-sanitization` in both copies. `stripHtml` is
 * DOMPurify with `ALLOWED_TAGS: []` and already trims.
 *
 * This is a BEHAVIOUR change, not a pure refactor. Measured against the old
 * regex, five input classes now count as blank that did not before:
 * numeric entities for ASCII whitespace (`<p>&#32;</p>`, `<p>&#9;</p>`), a
 * malformed attribute (`<p title="x>hello</p>`), and the text inside
 * `<script>`/`<style>`/`<title>`, which DOMPurify drops wholesale. Unchanged:
 * `&nbsp;`/`&#160;`/`&amp;`/`&lt;` (DOMPurify re-serializes them), `<textarea>`
 * content, comments, and a truncated tail like `<p>hello<`.
 *
 * All of that is unreachable from the current call sites — the only producer
 * feeding `isBlankHtml` is `isBlankDoc`, i.e. ProseMirror's own serializer,
 * which emits a literal space, never `&#32;` — so this is documentation of
 * the seam, not a live behaviour change. It matters if a call site is ever
 * pointed at author-supplied or server-stored HTML, because every divergence
 * points the same way: toward "blank", i.e. a silently disabled submit button.
 */
export function isBlankHtml(html: string): boolean {
  return stripHtml(html) === '';
}

/** A forum body block as SENT to the API (an image references the wagtail id). */
export type ForumBodyWriteBlock =
  | { type: 'paragraph'; value: string }
  | { type: 'quote'; value: string }
  /** A quote of a specific post (todo 342): the quoted post id + plain text.
   * The server validates the id (visible, not block-paired), caps distinct
   * quoted posts per body and the text length (QUOTE_MAX_CHARS, 1000) — none
   * of that is re-checked here; a 400 surfaces as the reply error. */
  | { type: 'post_quote'; value: { post: number; text: string } }
  /** An inline image (todo 357). Wagtail's `ImageBlock`: the wagtail image id
   * plus the PER-USAGE accessibility pair. A blank `alt_text` must ship with
   * `decorative: true` — the server normalises it anyway, but sending the pair
   * `ImageBlock.clean()` refuses would make the post un-editable in the CMS. */
  | {
      type: 'image';
      value: { image: number; alt_text: string; decorative: boolean };
    }
  | { type: 'embed'; value: string };

/**
 * Client-side cap on the text the Quote action lifts out of a post (todo
 * 342) — half the server's QUOTE_MAX_CHARS (1000), so a long post never 400s
 * the reply that quotes it. Cut with an ellipsis, not silently.
 */
export const QUOTE_TEXT_MAX_CHARS = 500;

// ---------------------------------------------------------------------------
// The composer schema (todo 526)
// ---------------------------------------------------------------------------

let schemaCache: Schema | null = null;

/** The live editor's schema, built once (getSchema resolves every extension). */
function forumSchema(): Schema {
  schemaCache ??= getSchema(FORUM_SCHEMA_EXTENSIONS);
  return schemaCache;
}

/**
 * Rich-text HTML -> the composer's block nodes, through the editor's schema —
 * what `editor.setContent(html)` would hold. Only ever fed a `paragraph`
 * block's server-sanitized value or a pre-526 draft the author wrote.
 */
function htmlToNodes(html: string): JSONContent[] {
  const doc = SchemaDOMParser.fromSchema(forumSchema()).parse(elementFromString(html));
  return (doc.toJSON() as JSONContent).content ?? [];
}

/**
 * Composer block nodes -> HTML, printed by the editor's schema: the same
 * serializer as `editor.getHTML()`, so a paragraph block's value is exactly
 * what the pre-526 composer sent.
 */
function nodesToHtml(nodes: JSONContent[]): string {
  const schema = forumSchema();
  return getHTMLFromFragment(
    Fragment.fromArray(nodes.map((node) => schema.nodeFromJSON(node))),
    schema
  );
}

/** A fresh empty composer document (the schema needs at least one block). */
export function emptyDoc(): JSONContent {
  return { type: 'doc', content: [{ type: 'paragraph' }] };
}

/**
 * Whether a composer document is effectively empty — the submit gate. Same
 * rule as before todo 526, applied to the editor's own serialisation, so
 * "blank" did not move: an image-only body still counts as blank.
 */
export function isBlankDoc(doc: JSONContent | null | undefined): boolean {
  return isBlankHtml(nodesToHtml(doc?.content ?? []));
}

/**
 * A stored or legacy value -> a composer document. A JSON `doc` is kept when
 * the schema accepts it (a tampered or stale draft becomes an empty document
 * rather than crashing the editor on mount); a string is a pre-526 draft,
 * which was always the composer's own `getHTML()`, and is parsed by the schema.
 */
export function toComposerDoc(value: unknown): JSONContent {
  if (typeof value === 'string') {
    return value.trim() ? { type: 'doc', content: htmlToNodes(value) } : emptyDoc();
  }
  if (value && typeof value === 'object' && (value as JSONContent).type === 'doc') {
    try {
      forumSchema().nodeFromJSON(value).check();
      return value as JSONContent;
    } catch {
      return emptyDoc();
    }
  }
  return emptyDoc();
}

/** A stored reply draft (JSON since todo 526, HTML before it) -> a composer document. */
export function draftToDoc(raw: string | null | undefined): JSONContent {
  if (!raw) return emptyDoc();
  try {
    return toComposerDoc(JSON.parse(raw));
  } catch {
    return toComposerDoc(raw); // a pre-526 HTML draft
  }
}

/** The plain text a mention node renders (the extension's default `renderText`). */
function mentionText(node: JSONContent): string {
  const attrs = node.attrs ?? {};
  return `@${attrs.label ?? attrs.id ?? ''}`;
}

/**
 * A node's visible text. `hardBreak` is `br`: '' reads as `textContent` does
 * (the embed rule), '\n' keeps a quote's line structure.
 */
function nodeText(node: JSONContent, hardBreak: '' | '\n'): string {
  if (node.type === 'text') return node.text ?? '';
  if (node.type === 'hardBreak') return hardBreak;
  if (node.type === 'mention') return mentionText(node);
  return (node.content ?? []).map((child) => nodeText(child, hardBreak)).join('');
}

/** Every descendant of `node` of type `type`, in document order. */
function descendantsOfType(node: JSONContent, type: string): JSONContent[] {
  return (node.content ?? []).flatMap((child) => [
    ...(child.type === type ? [child] : []),
    ...descendantsOfType(child, type),
  ]);
}

/**
 * An image node -> an `image` body block, or null when it carries no usable id.
 *
 * Shared by the top-level branch and the blockquote hoist so the two can never
 * drift into emitting different shapes — the reason this exists is that they
 * already had duplicated construction when the value went from a bare id to
 * ImageBlock's `{image, alt_text, decorative}` (todo 357).
 */
function imageBlockFrom(node: JSONContent): ForumBodyWriteBlock | null {
  const attrs = node.attrs ?? {};
  const rawId: unknown = attrs.imageId;
  const id = typeof rawId === 'number' || typeof rawId === 'string' ? String(rawId) : '';
  // Digits only. A non-numeric id yielded `{image: NaN}`, which
  // JSON.stringify emits as null and the server rejects — 400ing the WHOLE
  // post rather than dropping one image. ForumImage.parseHTML returns the
  // attribute verbatim, so any value that reaches the node survives to here.
  // Matches quotedPostId.
  if (!/^\d+$/.test(id)) return null;
  const altText = (typeof attrs.alt === 'string' ? attrs.alt : '').trim();
  // A blank alt IS a decorative declaration — that is what the composer's
  // "Skip" means, and `alt_text: "" + decorative: false` is the one pair
  // ImageBlock.clean() refuses (it would make the post un-editable in the CMS).
  const decorative = attrs.decorative === true || altText === '';
  return {
    type: 'image',
    value: { image: Number(id), alt_text: decorative ? '' : altText, decorative },
  };
}

/** The quoted post id a composer blockquote carries, or null when absent/invalid. */
function quotedPostId(node: JSONContent): number | null {
  const raw: unknown = node.attrs?.postId;
  const text = typeof raw === 'number' || typeof raw === 'string' ? String(raw) : '';
  if (!/^\d+$/.test(text)) return null;
  const id = Number(text);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

/**
 * A pasted video link becomes an `embed` block (todo 344) when it is the
 * ONLY content of its paragraph. Mirrors the server's known-player set —
 * the server's finder allowlist is still the authority (400 otherwise).
 */
// `[^\s<>"'\`]+` rather than `\S+`: a pasted "link" carrying HTML
// meta-characters is never a provider URL, so it stays an ordinary paragraph
// (where TipTap has already escaped it) instead of becoming an embed value
// (todo 353 — the CodeQL js/xss-through-dom trace starts at this textContent).
const PROVIDER_VIDEO_URL =
  /^https?:\/\/(?:(?:[-\w]+\.)?youtube\.com\/(?:watch\?[^\s<>"'`]+|shorts\/[^\s<>"'`]+|live\/[^\s<>"'`]+|v\/[^\s<>"'`]+)|youtu\.be\/[^\s<>"'`]+|(?:www\.)?vimeo\.com\/[^\s<>"'`]+)$/;

/**
 * The bare provider URL if `node` is a paragraph holding exactly one, else
 * null. A URL written as code stays code: the server's rule (`_sole_url` with
 * `skip_code`, todo 448 item 10) refuses any `<code>` holding non-blank text.
 */
function embedUrlOf(node: JSONContent): string | null {
  if (node.type !== 'paragraph') return null;
  const inCode = descendantsOfType(node, 'text').some(
    (text) => text.marks?.some((mark) => mark.type === 'code') && (text.text ?? '').trim()
  );
  if (inCode) return null;
  const text = nodeText(node, '').trim();
  return PROVIDER_VIDEO_URL.test(text) ? text : null;
}

const PREVIEW_BLOCK_TAGS = new Set([
  'ADDRESS',
  'ARTICLE',
  'ASIDE',
  'BLOCKQUOTE',
  'BR',
  'DIV',
  'FOOTER',
  'H1',
  'H2',
  'H3',
  'H4',
  'H5',
  'H6',
  'HEADER',
  'HR',
  'LI',
  'MAIN',
  'NAV',
  'OL',
  'P',
  'PRE',
  'SECTION',
  'TABLE',
  'TR',
  'UL',
]);

function previewTextWithBlockBreaks(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? '';
  if (node.nodeType !== Node.ELEMENT_NODE) return '';
  const element = node as Element;
  const content = Array.from(element.childNodes).map(previewTextWithBlockBreaks).join('');
  return PREVIEW_BLOCK_TAGS.has(element.tagName) ? `${content}\n` : content;
}

/**
 * The URL check is `safeExternalUrl` (todo 438: one shared http(s)/host/
 * no-credentials rule). Two differences stay deliberate here: characters that
 * `new URL` would percent-encode rather than reject (`<>"'`, whitespace) are
 * refused outright (todo 353), and the author's own trimmed string is
 * returned, not the parser's normalised form (`https://example.com` must not
 * become `https://example.com/`).
 */
function validPreviewUrl(value: string | null): string | null {
  const trimmed = value?.trim() ?? '';
  if (!trimmed || /[<>"']/.test(trimmed) || /\s/.test(trimmed)) return null;
  return safeExternalUrl(trimmed) ? trimmed : null;
}

export function previewUrlFromHtml(html: string): string | null {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  for (const element of Array.from(doc.querySelectorAll('script, style, noscript, template'))) {
    element.remove();
  }
  const links = Array.from(doc.querySelectorAll('a[href]')).reverse();
  for (const link of links) {
    const url = validPreviewUrl(link.getAttribute('href'));
    if (url) return url;
  }
  const urls = previewTextWithBlockBreaks(doc.body).match(/https?:\/\/[^\s<>"']+/gi) ?? [];
  for (const candidate of urls.reverse()) {
    const url = validPreviewUrl(candidate.replace(/[),.!?]+$/, ''));
    if (url) return url;
  }
  return null;
}

/**
 * An element's visible text with each `<br>` as "\n". `textContent` drops a
 * hard break entirely ("one<br>two" -> "onetwo"). Only text nodes and breaks
 * contribute, so no tag ever leaks into the plain text of a quote.
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
 * A blockquote node's visible text, one entry per child block. Raw text would
 * mash `<p>a</p><p>b</p>` into "ab" — join the children with a blank line
 * instead. A `hardBreak` inside a child (the form quoteParagraphs writes a
 * single "\n" as) reads back as "\n".
 */
function blockquoteText(node: JSONContent): string {
  return (node.content ?? [])
    .map((child) => trimLines(nodeText(child, '\n')))
    .filter(Boolean)
    .join('\n\n');
}

/**
 * Composer document -> forum body blocks. Runs of rich text become `paragraph`
 * blocks (HTML, printed by the editor's schema); each image node becomes its
 * own `image` block.
 *
 * Since the ImageBlock migration (todo 357) the block carries the id AND the
 * per-usage `alt_text`/`decorative`, so the editor's alt is PERSISTED rather
 * than dropped — which is what makes alt editable after insert without
 * re-uploading. Only `src` is display-only (the backend re-derives the
 * rendition URL).
 */
export function docToBodyBlocks(doc: JSONContent | null | undefined): ForumBodyWriteBlock[] {
  const blocks: ForumBodyWriteBlock[] = [];
  let run: JSONContent[] = [];
  const flush = () => {
    const value = run.length ? nodesToHtml(run).trim() : '';
    if (value) blocks.push({ type: 'paragraph', value });
    run = [];
  };
  for (const node of doc?.content ?? []) {
    const embedUrl = embedUrlOf(node);
    if (node.type === 'image') {
      // An image without a usable id (never uploaded) is dropped: the server
      // strips `<img>` from paragraph HTML, so it could never persist anyway.
      flush();
      const imageBlock = imageBlockFrom(node);
      if (imageBlock) blocks.push(imageBlock);
    } else if (embedUrl) {
      // A paragraph that is just a video link → its own embed block; the
      // server unfurls it (todo 344). Re-editing round-trips through
      // bodyBlocksToDoc's link paragraph back to this branch.
      flush();
      blocks.push({ type: 'embed', value: embedUrl });
    } else if (node.type === 'blockquote') {
      // A top-level blockquote becomes its OWN `quote` block, not inline markup
      // in a paragraph: the server's nh3 allowlist has no <blockquote>, so a
      // quote left inside rich text would be silently flattened to plain text.
      // Only TOP-LEVEL blockquotes are detected: one nested inside a list
      // item stays in its paragraph's markup and is flattened exactly like
      // that (pre-existing limitation, not handled).
      // One carrying a `postId` (the Quote action, todo 342) is a `post_quote`
      // of that post instead; a missing or malformed id falls back to the
      // legacy free-form quote rather than a guaranteed 400.
      flush();
      const text = blockquoteText(node);
      const postId = quotedPostId(node);
      if (text && postId != null) {
        blocks.push({ type: 'post_quote', value: { post: postId, text } });
      } else if (text) {
        blocks.push({ type: 'quote', value: text });
      }
      // An image nested in the quote has no text — hoist it out as its own
      // block rather than dropping the user's content silently. Same builder
      // as the top-level branch, so the shape and the id guard cannot drift.
      for (const image of descendantsOfType(node, 'image')) {
        const nestedBlock = imageBlockFrom(image);
        if (nestedBlock) blocks.push(nestedBlock);
      }
    } else {
      run.push(node);
    }
  }
  flush();
  return blocks;
}

/**
 * A stored link (an embed or a link card) as a composer node: a paragraph
 * holding only that link, which docToBodyBlocks and the server both read as
 * "a link posted on its own". SECURITY: the editor renders this href into the
 * live composer DOM, where React's href guard does not apply — so a persisted
 * URL with a non-http(s) scheme (a direct API POST that skipped the composer)
 * is dropped, not linked (review). The URL is a node attribute and a text
 * node, never markup.
 */
function linkParagraph(url: string | null | undefined): JSONContent | null {
  if (!url || !/^https?:\/\//i.test(url)) return null;
  return {
    type: 'paragraph',
    content: [{ type: 'text', text: url, marks: [{ type: 'link', attrs: { href: url } }] }],
  };
}

/**
 * Plain quote text -> one paragraph node per paragraph. The text is a TEXT
 * node, never markup: `quote` is a Wagtail `BlockQuoteBlock` (a `TextBlock`)
 * whose value the server deliberately leaves unsanitized ("text by contract",
 * api/sanitize.py), so it must not become document structure. A single "\n"
 * inside a paragraph (a list-sourced quote — postQuoteText joins list items
 * with one "\n" — or a non-browser client) becomes a `hardBreak`, which
 * blockquoteText reads back as "\n", so the round trip is stable.
 */
function quoteParagraphs(text: string): JSONContent[] {
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
      )
      .filter((lines) => lines.length > 0)
      .map((lines) => ({
        type: 'paragraph',
        content: lines.flatMap((line, i): JSONContent[] =>
          i === 0
            ? [{ type: 'text', text: line }]
            : [{ type: 'hardBreak' }, { type: 'text', text: line }]
        ),
      }))
  );
}

/** A blockquote node of `text`, carrying `postId` when it is a valid post id. */
function quoteNode(text: string, postId?: number): JSONContent | null {
  const content = quoteParagraphs(text);
  if (content.length === 0) return null;
  return postId != null && Number.isSafeInteger(postId) && postId > 0
    ? { type: 'blockquote', attrs: { postId: String(postId) }, content }
    : { type: 'blockquote', content };
}

/**
 * Forum body blocks -> composer document, the inverse of docToBodyBlocks.
 * Image blocks become image nodes carrying the wagtail id, so re-editing
 * round-trips the id through TipTap. Block types the forum composer does not
 * produce are left out. No branch builds an HTML string (todo 526).
 */
export function bodyBlocksToDoc(body: StreamFieldBlock[] | null | undefined): JSONContent {
  const content: JSONContent[] = [];
  for (const block of body ?? []) {
    if (block.type === 'image') {
      // Deleted image -> `value: null` from the server. Dropped rather than
      // rendered: there is no id or url left to round-trip, and an image node
      // with no id would re-persist a broken block on the next save. Losing a
      // reference that already points at nothing is the correct outcome;
      // throwing here blocked re-editing the post at all.
      if (!block.value) continue;
      const { id, url, alt, decorative } = block.value;
      content.push({
        type: 'image',
        attrs: {
          // `|| ''`: a nullish url must degrade, not throw and block
          // re-editing the post (PR #826 review). Display-only — the backend
          // re-derives the rendition.
          src: url || '',
          alt: alt || '',
          // docToBodyBlocks drops any non-digit id on the way back.
          imageId: id == null ? null : String(id),
          // Round-trips the flag so re-saving an untouched decorative image
          // does not downgrade it to the pair the CMS refuses.
          decorative: decorative === true,
        },
      });
    } else if (block.type === 'paragraph') {
      // Server-sanitized rich text — HTML by contract, parsed by the editor's
      // schema exactly as `setContent` would.
      if (typeof block.value === 'string' && block.value.trim()) {
        content.push(...htmlToNodes(block.value));
      }
    } else if (block.type === 'embed') {
      // The read shape is an envelope; only the original URL goes back into
      // the composer, as a link paragraph docToBodyBlocks recognises (see
      // linkParagraph for the scheme guard).
      const url = typeof block.value === 'string' ? block.value : block.value?.url;
      const node = linkParagraph(url);
      if (node) content.push(node);
    } else if (block.type === 'link_preview') {
      // A link card (todo 428) goes back into the composer as the link the
      // author posted — the same link paragraph as an embed. Saving it
      // unchanged re-derives the same stored card server-side, with no
      // fetch. A null value (an unusable stored link) has nothing to keep.
      const node = block.value ? linkParagraph(block.value.url) : null;
      if (node) content.push(node);
    } else if (block.type === 'quote') {
      const node = quoteNode(typeof block.value === 'string' ? block.value : '');
      if (node) content.push(node);
    } else if (block.type === 'post_quote') {
      // Same plain-text contract as `quote`, plus the quoted post id so
      // docToBodyBlocks re-derives a `post_quote` block — REGARDLESS of
      // `available`. The server exempts the ids the stored body already
      // carries from the availability re-check on edit
      // (`existing_quote_ids`), so a quote whose post has since gone keeps its
      // id; downgrading it to a plain `quote` here would silently rewrite the
      // author's post on every re-edit and lose the attribution for good.
      // Only a malformed id falls back.
      const node = quoteNode(block.value.text, block.value.post_id);
      if (node) content.push(node);
    }
  }
  return content.length > 0 ? { type: 'doc', content } : emptyDoc();
}

/**
 * Whether saving `doc` would send the same body blocks that opening `body` for
 * editing would (todo 526). Both sides go through the same converters, so an
 * untouched post compares equal however its stored paragraph HTML is
 * formatted — which is what lets an untouched re-save skip the PATCH, and the
 * unsaved-edit prompt (M27) stay quiet.
 */
export function isUnchangedBody(
  doc: JSONContent | null | undefined,
  body: StreamFieldBlock[] | null | undefined
): boolean {
  return (
    JSON.stringify(docToBodyBlocks(doc)) === JSON.stringify(docToBodyBlocks(bodyBlocksToDoc(body)))
  );
}

/**
 * The composer node for the Quote action (todo 342): a `post_quote`
 * blockquote of `postId` holding `text`, in exactly the form docToBodyBlocks
 * turns back into `{type: 'post_quote', value: {post, text}}`. `text` comes
 * from postQuoteText, i.e. from another member's post — it is a text node,
 * never markup. Null when `text` has no content.
 */
export function postQuoteNode(postId: number, text: string): JSONContent | null {
  return quoteNode(text, postId);
}

/** Visible text of one rich-text paragraph block, one entry per top-level element. */
function richTextParagraphs(html: string): string[] {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  // Collapse runs of spaces but KEEP line structure: a hard break in the
  // source (`<p>a<br>b</p>`, Shift+Enter) is lifted as "a\nb", which
  // quoteParagraphs renders back as a hard break — never as the merged "ab".
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
