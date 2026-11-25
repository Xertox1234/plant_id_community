/**
 * The parts of the forum body model that need no TipTap (audit F110).
 *
 * Reading a thread needs these; only writing needs the editor and its schema
 * (utils/forumBody, components/forum/TipTapEditor), which are loaded when
 * somebody composes. Nothing here may import TipTap or forumBody at run time
 * (ThreadDetailPage.imports.test.ts).
 */
import type { JSONContent } from '@tiptap/react';
import type { StreamFieldBlock } from '@/types/blog';

/**
 * Client-side cap on the text the Quote action lifts out of a post (todo
 * 342) — half the server's QUOTE_MAX_CHARS (1000), so a long post never 400s
 * the reply that quotes it. Cut with an ellipsis, not silently.
 */
export const QUOTE_TEXT_MAX_CHARS = 500;

/** A fresh empty composer document (the schema needs at least one block). */
export function emptyDoc(): JSONContent {
  return { type: 'doc', content: [{ type: 'paragraph' }] };
}

/**
 * A forum's plain-text topic template -> a composer document (todo 678;
 * owner decision 2026-10-30): each line becomes a paragraph, nothing is
 * formatted, and a blank line stays an empty paragraph.
 */
export function templateToDoc(text: string): JSONContent {
  if (!text.trim()) return emptyDoc();
  return {
    type: 'doc',
    content: text
      .replace(/\r\n?/g, '\n')
      .split('\n')
      .map((line) =>
        line
          ? { type: 'paragraph', content: [{ type: 'text', text: line }] }
          : { type: 'paragraph' }
      ),
  };
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
export function nodeText(node: JSONContent, hardBreak: '' | '\n'): string {
  if (node.type === 'text') return node.text ?? '';
  if (node.type === 'hardBreak') return hardBreak;
  if (node.type === 'mention') return mentionText(node);
  return (node.content ?? []).map((child) => nodeText(child, hardBreak)).join('');
}

/** Every descendant of `node` of type `type`, in document order. */
export function descendantsOfType(node: JSONContent, type: string): JSONContent[] {
  return (node.content ?? []).flatMap((child) => [
    ...(child.type === type ? [child] : []),
    ...descendantsOfType(child, type),
  ]);
}

/**
 * Whether a composer document is effectively empty — the submit gate. An
 * image-only body counts as blank. The same answer as `isBlankHtml` of the
 * document's HTML (pinned in forumDoc.test.ts): a no-break space is content,
 * because the serializer prints it as `&nbsp;`.
 */
export function isBlankDoc(doc: JSONContent | null | undefined): boolean {
  return (
    nodeText(doc ?? {}, '')
      .replace(/\u00a0/g, 'x')
      .trim() === ''
  );
}

/**
 * Whether a composer document holds nothing at all — no text AND no image.
 * Not the submit gate: `isBlankDoc` deliberately counts an image-only body as
 * blank. This is for code that would otherwise DISCARD the document, e.g. the
 * Quote action deciding whether to keep the reply already drafted (todo 538:
 * an image-only reply was dropped when the user quoted a post).
 */
export function isEmptyDoc(doc: JSONContent | null | undefined): boolean {
  return isBlankDoc(doc) && descendantsOfType(doc ?? {}, 'image').length === 0;
}

/** Trim each line and the whole, keeping the line structure ("a \n b" -> "a\nb"). */
export function trimLines(text: string): string {
  return text
    .split('\n')
    .map((line) => line.trim())
    .join('\n')
    .trim();
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
export function quoteNode(text: string, postId?: number): JSONContent | null {
  const content = quoteParagraphs(text);
  if (content.length === 0) return null;
  return postId != null && Number.isSafeInteger(postId) && postId > 0
    ? { type: 'blockquote', attrs: { postId: String(postId) }, content }
    : { type: 'blockquote', content };
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

/** Tags that end a line: they count as whitespace in a post's plain text. */
const LINE_TAGS = new Set(
  'ADDRESS ARTICLE ASIDE BLOCKQUOTE DD DIV DL DT FIGCAPTION FIGURE FOOTER H1 H2 H3 H4 H5 H6 HEADER HR LI MAIN NAV OL P PRE SECTION TABLE TD TH TR UL'.split(
    ' '
  )
);

/**
 * An element's visible text, with a "\n" at each `<br>` and at each end of a
 * block inside it. `textContent` merges the words on both sides of those.
 */
function textWithBreaks(el: Element): string {
  let out = '';
  const breakLine = () => {
    if (out && !out.endsWith('\n')) out += '\n';
  };
  for (const node of Array.from(el.childNodes)) {
    if (node.nodeType === Node.TEXT_NODE) {
      out += node.textContent ?? '';
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const child = node as Element;
      if (child.tagName === 'BR') {
        out += '\n';
      } else if (LINE_TAGS.has(child.tagName)) {
        breakLine();
        out += textWithBreaks(child);
        breakLine();
      } else {
        out += textWithBreaks(child);
      }
    }
  }
  return out;
}

/** Visible text of one rich-text paragraph block, one entry per top-level block element. */
function richTextParagraphs(html: string): string[] {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  // Collapse runs of spaces but KEEP line structure: a hard break in the
  // source (`<p>a<br>b</p>`, Shift+Enter) is lifted as "a\nb", which
  // quoteParagraphs renders back as a hard break — never as the merged "ab".
  const collapse = (s: string) => trimLines(s.replace(/[^\S\n]+/g, ' '));
  const paragraphs: string[] = [];
  // Loose inline content between blocks is a paragraph of its own.
  let inline = doc.createElement('div');
  const flush = () => {
    paragraphs.push(collapse(textWithBreaks(inline)));
    inline = doc.createElement('div');
  };
  for (const node of Array.from(doc.body.childNodes)) {
    if (node.nodeType === Node.ELEMENT_NODE && LINE_TAGS.has((node as Element).tagName)) {
      flush();
      paragraphs.push(collapse(textWithBreaks(node as Element)));
    } else {
      inline.appendChild(node.cloneNode(true));
    }
  }
  flush();
  return paragraphs.filter(Boolean);
}

/** Cut at `max` UTF-16 units without splitting a surrogate pair (an emoji). */
function cutAt(text: string, max: number): string {
  const last = text.charCodeAt(max - 1);
  return text.slice(0, last >= 0xd800 && last <= 0xdbff ? max - 1 : max);
}

/**
 * The plain text the Quote action lifts out of a post body (todo 342):
 * paragraphs (and headings) as text, blank-line separated; a legacy `quote`
 * as its text.
 *
 * The server checks it (owner decision, audit F3): with whitespace collapsed
 * and one trailing "…" ignored it must be ONE contiguous piece of the post's
 * plain text. So it is the first unbroken run of quotable blocks. An image
 * has no text and does not break the run; a `post_quote` (a third person's
 * words), code, an embed or a link card does, since the post's text holds
 * something there that this leaves out. "…" marks a run cut short, there or
 * at `maxChars`. '' when the post has no quotable text (an image-only post):
 * the caller must not quote nothing, since the server rejects an empty quote.
 */
export function postQuoteText(
  body: StreamFieldBlock[] | null | undefined,
  maxChars = QUOTE_TEXT_MAX_CHARS
): string {
  const parts: string[] = [];
  let broken = false;
  let cut = false;
  for (const block of body ?? []) {
    let texts: string[];
    if (block.type === 'paragraph') {
      texts = typeof block.value === 'string' && block.value ? richTextParagraphs(block.value) : [];
    } else if (block.type === 'heading') {
      texts = [block.value.trim()];
    } else if (block.type === 'quote') {
      const v = block.value;
      texts = [(typeof v === 'string' ? v : (v.quote_text ?? v.quote ?? '')).trim()];
    } else {
      if (block.type !== 'image' && parts.length > 0) broken = true;
      continue;
    }
    texts = texts.filter(Boolean);
    if (texts.length === 0) continue;
    if (broken) {
      cut = true;
      break;
    }
    parts.push(...texts);
  }
  const text = parts.join('\n\n');
  if (text.length > maxChars) return `${cutAt(text, maxChars).trimEnd()}…`;
  return cut ? `${text}…` : text;
}
