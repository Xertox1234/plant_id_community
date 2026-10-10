import { describe, it, expect, vi } from 'vitest';
import { Editor, generateHTML, type JSONContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import {
  bodyBlocksToDoc,
  docToBodyBlocks,
  draftToDoc,
  emptyDoc,
  isBlankDoc,
  isUnchangedBody,
  previewUrlFromHtml,
  postQuoteNode,
  postQuoteText,
  isBlankHtml,
  toComposerDoc,
  QUOTE_TEXT_MAX_CHARS,
} from './forumBody';
import { ForumImage } from '../components/forum/forumImageNode';
import { FORUM_SCHEMA_EXTENSIONS } from '../components/forum/forumEditorSchema';
import type { StreamFieldBlock } from '@/types/blog';

// Lets one test make the shared URL rule reject everything, to prove the
// preview detection defers to it (todo 438). A plain wrapper, not vi.fn:
// the config's mockReset would wipe a vi.fn implementation between tests.
const urlGate = vi.hoisted(() => ({ rejectAll: false }));
vi.mock('./externalUrl', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./externalUrl')>();
  return {
    ...actual,
    safeExternalUrl: (...args: Parameters<typeof actual.safeExternalUrl>) =>
      urlGate.rejectAll ? null : actual.safeExternalUrl(...args),
  };
});

// Since todo 526 the composer's content model is TipTap JSON: bodyBlocksToDoc
// builds the editor's document, docToBodyBlocks reads it back. Most cases
// below were ported from the HTML pair they replaced (bodyBlocksToHtml /
// htmlToBodyBlocks). Where a case's INPUT is composer HTML, `fromHtml` parses
// it with the live editor's schema first — exactly what the editor holds after
// that HTML is pasted or set — so the cases still pin the same rules.
const fromHtml = (html: string) => docToBodyBlocks(toComposerDoc(html));
const docOf = (...content: JSONContent[]): JSONContent => ({ type: 'doc', content });
const text = (value: string, marks?: JSONContent['marks']): JSONContent =>
  marks ? { type: 'text', text: value, marks } : { type: 'text', text: value };
const para = (...content: JSONContent[]): JSONContent =>
  content.length ? { type: 'paragraph', content } : { type: 'paragraph' };
const image = (attrs: Record<string, unknown>): JSONContent => ({ type: 'image', attrs });

/** `doc` as the live editor holds it: mounted, then read back with getJSON(). */
function throughEditor(doc: JSONContent): JSONContent {
  const editor = new Editor({ extensions: FORUM_SCHEMA_EXTENSIONS, content: doc });
  try {
    return editor.getJSON();
  } finally {
    editor.destroy();
  }
}

describe('previewUrlFromHtml', () => {
  it('extracts a linked public URL from real TipTap output', () => {
    const editor = new Editor({
      extensions: [StarterKit.configure({ link: false }), Link],
      content: '<p><a href="https://www.facebook.com/example/posts/1">Open Facebook</a></p>',
    });
    try {
      expect(previewUrlFromHtml(editor.getHTML())).toBe('https://www.facebook.com/example/posts/1');
    } finally {
      editor.destroy();
    }
  });

  it('extracts URLs from prose and list items but ignores non-http targets', () => {
    expect(previewUrlFromHtml('<p>See https://example.com for details</p>')).toBe(
      'https://example.com'
    );
    expect(previewUrlFromHtml('<ul><li>https://example.com/plant</li></ul>')).toBe(
      'https://example.com/plant'
    );
    expect(
      previewUrlFromHtml(
        '<ul><li>https://example.com/one</li><li>https://example.org/two</li></ul>'
      )
    ).toBe('https://example.org/two');
    expect(previewUrlFromHtml('<p>mailto:test@example.com</p>')).toBeNull();
    expect(previewUrlFromHtml('<script>https://example.com/hidden</script>')).toBeNull();
  });

  it('uses the shared safeExternalUrl rule, not a copy of it (todo 438)', () => {
    urlGate.rejectAll = true;
    try {
      expect(previewUrlFromHtml('<p>See https://example.com for details</p>')).toBeNull();
      expect(previewUrlFromHtml('<p><a href="https://example.com/a">a</a></p>')).toBeNull();
    } finally {
      urlGate.rejectAll = false;
    }
  });

  it('keeps its own stricter shape and returns the author string unnormalised', () => {
    // safeExternalUrl would accept these after percent-encoding; the preview
    // detector refuses them outright (todo 353).
    expect(previewUrlFromHtml('<p><a href="https://example.com/a&quot;b">x</a></p>')).toBeNull();
    expect(previewUrlFromHtml('<p><a href="https://example.com/a b">x</a></p>')).toBeNull();
    expect(previewUrlFromHtml('<p><a href="https://u:p@example.com/">x</a></p>')).toBeNull();
    expect(previewUrlFromHtml('<p><a href="ftp://example.com/x">x</a></p>')).toBeNull();
    // The parser's form would be "https://example.com/"; the author's string wins.
    expect(previewUrlFromHtml('<p><a href="https://EXAMPLE.com">x</a></p>')).toBe(
      'https://EXAMPLE.com'
    );
  });
});

describe('forumBody serialization', () => {
  it('never turns a link carrying HTML meta-characters into an embed (todo 353)', () => {
    const bad = fromHtml('<p>https://youtu.be/abc&lt;script&gt;x</p>');
    expect(bad).toEqual([
      { type: 'paragraph', value: '<p>https://youtu.be/abc&lt;script&gt;x</p>' },
    ]);
    const quoted = fromHtml('<p>https://www.youtube.com/watch?v=1"onerror="x</p>');
    expect(quoted[0]?.type).toBe('paragraph');
    const good = fromHtml('<p>https://youtu.be/abc123</p>');
    expect(good).toEqual([{ type: 'embed', value: 'https://youtu.be/abc123' }]);
  });

  it('docToBodyBlocks splits interleaved text and images into separate blocks', () => {
    const html = '<p>before</p><img src="https://cdn/x.jpg" alt="a" data-image-id="5"><p>after</p>';
    expect(fromHtml(html)).toEqual([
      { type: 'paragraph', value: '<p>before</p>' },
      { type: 'image', value: { image: 5, alt_text: 'a', decorative: false } },
      { type: 'paragraph', value: '<p>after</p>' },
    ]);
  });

  it('docToBodyBlocks does not make an image block for an image without an id', () => {
    // Only uploaded (id-bearing) images become image blocks.
    const blocks = fromHtml('<p>x</p><img src="https://cdn/y.jpg">');
    expect(blocks.some((b) => b.type === 'image')).toBe(false);
  });

  it('bodyBlocksToDoc builds an image NODE carrying the wagtail id, not an <img> string (todo 526)', () => {
    const body: StreamFieldBlock[] = [
      { type: 'paragraph', value: '<p>hi</p>' },
      { type: 'image', value: { id: 9, url: 'https://cdn/z.jpg', alt: 'cap' } },
    ];
    expect(bodyBlocksToDoc(body)).toEqual(
      docOf(
        para(text('hi')),
        image({ src: 'https://cdn/z.jpg', alt: 'cap', imageId: '9', decorative: false })
      )
    );
  });

  it('keeps typed markup characters as text in the paragraph HTML', () => {
    // The paragraph value is HTML, so a character the user typed must be
    // escaped there, never re-read as a tag (CodeQL js/xss-through-dom). Bare
    // top-level text is wrapped in a paragraph by the schema (todo 526: it
    // used to be passed through unwrapped, which only raw HTML input could
    // produce — the editor never emits bare text).
    expect(fromHtml('a < b')).toEqual([{ type: 'paragraph', value: '<p>a &lt; b</p>' }]);
    expect(fromHtml('<p>ok</p>plain & text')).toEqual([
      { type: 'paragraph', value: '<p>ok</p><p>plain &amp; text</p>' },
    ]);
  });

  it('round-trips a body through the document and back, preserving image ids and order', () => {
    const body: StreamFieldBlock[] = [
      { type: 'paragraph', value: '<p>look</p>' },
      { type: 'image', value: { id: 42, url: 'https://cdn/p.jpg', alt: '' } },
      { type: 'paragraph', value: '<p>done</p>' },
    ];
    expect(docToBodyBlocks(bodyBlocksToDoc(body))).toEqual([
      { type: 'paragraph', value: '<p>look</p>' },
      { type: 'image', value: { image: 42, alt_text: '', decorative: true } },
      { type: 'paragraph', value: '<p>done</p>' },
    ]);
  });

  it('round-trips through a REAL TipTap editor: ForumImage stays a top-level block with its id', () => {
    // Guards the seam the unit tests cannot: that the actual editor keeps the
    // image a top-level block (not inline in a paragraph) and preserves its
    // id through the ProseMirror schema — otherwise the image is swept into a
    // paragraph, nh3 strips it on save, and it vanishes in prod.
    const doc = throughEditor(
      toComposerDoc('<p>a</p><img src="https://cdn/x.jpg" data-image-id="5"><p>b</p>')
    );
    expect(docToBodyBlocks(doc)).toEqual([
      { type: 'paragraph', value: '<p>a</p>' },
      { type: 'image', value: { image: 5, alt_text: '', decorative: true } },
      { type: 'paragraph', value: '<p>b</p>' },
    ]);
  });
});

describe('forumBody quote blocks (audit M1)', () => {
  it('lifts a top-level blockquote into its own quote block as PLAIN text', () => {
    // BlockQuoteBlock is a Wagtail TextBlock — the value is text, never markup.
    expect(fromHtml('<p>before</p><blockquote><p>quoted</p></blockquote>')).toEqual([
      { type: 'paragraph', value: '<p>before</p>' },
      { type: 'quote', value: 'quoted' },
    ]);
  });

  it('joins a multi-paragraph blockquote instead of mashing the text together', () => {
    // Raw text would yield "onetwo".
    expect(fromHtml('<blockquote><p>one</p><p>two</p></blockquote>')).toEqual([
      { type: 'quote', value: 'one\n\ntwo' },
    ]);
  });

  it('drops an empty blockquote rather than emitting a blank quote block', () => {
    expect(fromHtml('<blockquote><p>   </p></blockquote>')).toEqual([]);
  });

  it('hoists an image nested in a blockquote out instead of silently losing it', () => {
    // An image has no text; without the hoist the user's upload vanishes.
    expect(
      fromHtml('<blockquote><p>see</p><img src="https://cdn/x.jpg" data-image-id="7"></blockquote>')
    ).toEqual([
      { type: 'quote', value: 'see' },
      { type: 'image', value: { image: 7, alt_text: '', decorative: true } },
    ]);
  });

  it('skips a nested image with a blank id instead of emitting value 0', () => {
    // An image node whose id is "" has no usable id. Emitting 0 (or NaN ->
    // null) fails validate_forum_body server-side, so ONE unusable image would
    // 400 the whole save. Match the top-level branch and drop it. The real
    // image alongside it must still survive.
    const doc = docOf({
      type: 'blockquote',
      content: [para(text('q')), image({ imageId: '' }), image({ imageId: '8' })],
    });
    expect(docToBodyBlocks(doc)).toEqual([
      { type: 'quote', value: 'q' },
      { type: 'image', value: { image: 8, alt_text: '', decorative: true } },
    ]);
  });

  it('puts quote text back into the composer as a TEXT node, never as markup', () => {
    // The server leaves quote values unsanitized ("text by contract"); the
    // write-back must not turn stored text into real editor structure.
    const doc = bodyBlocksToDoc([{ type: 'quote', value: '<script>alert(1)</script>' }]);
    expect(doc).toEqual(
      docOf({ type: 'blockquote', content: [para(text('<script>alert(1)</script>'))] })
    );
    // As the editor renders it, the text is escaped, never a tag.
    const html = generateHTML(doc, FORUM_SCHEMA_EXTENSIONS);
    expect(html).toContain('&lt;script&gt;');
    expect(html).not.toContain('<script>');
  });

  it('round-trips a quote containing markup-looking text unchanged (idempotent)', () => {
    const body: StreamFieldBlock[] = [
      { type: 'paragraph', value: '<p>intro</p>' },
      { type: 'quote', value: 'a < b\n\nsecond line' },
    ];
    const once = docToBodyBlocks(bodyBlocksToDoc(body));
    expect(once).toEqual([
      { type: 'paragraph', value: '<p>intro</p>' },
      { type: 'quote', value: 'a < b\n\nsecond line' },
    ]);
    // Stable under a second pass — re-editing a saved post must not drift.
    expect(docToBodyBlocks(bodyBlocksToDoc(structuredClone(once) as StreamFieldBlock[]))).toEqual(
      once
    );
  });

  it('does not promote a single newline to a paragraph break on re-edit', () => {
    // A value with single "\n" separators can arrive from a non-browser client.
    // Splitting on /\n+/ would rewrite it to "\n\n" every time the post is
    // opened and saved, since blockquoteText always rejoins with "\n\n".
    const blocks = docToBodyBlocks(
      bodyBlocksToDoc([{ type: 'quote', value: 'line one\nline two' }])
    );
    expect(blocks).toEqual([{ type: 'quote', value: 'line one\nline two' }]);
  });

  it('keeps markup-looking quote text inert through the full re-edit round trip', () => {
    // A <script> is not content: the schema parser drops it, so a blockquote
    // holding only one is empty (before todo 526 its text leaked through as
    // "alert(1)").
    expect(fromHtml('<blockquote><script>alert(1)</script></blockquote>')).toEqual([]);

    const evil = fromHtml('<blockquote>a &lt;img src=x onerror=alert(1)&gt; b</blockquote>');
    expect(evil).toEqual([{ type: 'quote', value: 'a <img src=x onerror=alert(1)> b' }]);
    const doc = bodyBlocksToDoc(structuredClone(evil) as StreamFieldBlock[]);
    const html = generateHTML(doc, FORUM_SCHEMA_EXTENSIONS);
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;img');
    // ...and reading the document back yields the same plain text, not an image block.
    expect(docToBodyBlocks(doc)).toEqual(evil);
  });

  it('round-trips through a REAL TipTap editor: blockquote stays top-level', () => {
    // The seam the unit tests cannot cover — that StarterKit's Blockquote is a
    // top-level node so docToBodyBlocks sees it (rather than nested in a
    // paragraph, where nh3 would strip it on save and the quote would vanish).
    const doc = throughEditor(
      toComposerDoc('<p>a</p><blockquote><p>quoted</p></blockquote><p>b</p>')
    );
    expect(docToBodyBlocks(doc)).toEqual([
      { type: 'paragraph', value: '<p>a</p>' },
      { type: 'quote', value: 'quoted' },
      { type: 'paragraph', value: '<p>b</p>' },
    ]);
  });
});

describe('forumBody embed blocks (todo 344)', () => {
  it('turns a paragraph that is only a YouTube or Vimeo link into an embed block', () => {
    const blocks = fromHtml(
      '<p>Watch this:</p><p>https://youtu.be/dQw4w9WgXcQ</p><p><a href="https://vimeo.com/148751763">https://vimeo.com/148751763</a></p>'
    );
    expect(blocks).toEqual([
      { type: 'paragraph', value: '<p>Watch this:</p>' },
      { type: 'embed', value: 'https://youtu.be/dQw4w9WgXcQ' },
      { type: 'embed', value: 'https://vimeo.com/148751763' },
    ]);
  });

  it('leaves a video link written as code as code, as the server does (todo 448 item 10)', () => {
    const html = '<p><code>https://youtu.be/dQw4w9WgXcQ</code></p>';
    expect(fromHtml(html)).toEqual([{ type: 'paragraph', value: html }]);
  });

  it('leaves a link inside prose, or an unknown provider, as ordinary paragraph text', () => {
    const blocks = fromHtml(
      '<p>See https://youtu.be/dQw4w9WgXcQ for details</p><p>https://example.com/video/1</p>'
    );
    expect(blocks.every((b) => b.type === 'paragraph')).toBe(true);
    expect(blocks).toHaveLength(1);
  });

  it('accepts a youtube.com/live share link as an embed, and drops a persisted non-http(s) embed url on re-edit', () => {
    expect(fromHtml('<p>https://www.youtube.com/live/abcDEF12345?feature=share</p>')).toEqual([
      { type: 'embed', value: 'https://www.youtube.com/live/abcDEF12345?feature=share' },
    ]);
    expect(
      bodyBlocksToDoc([
        {
          type: 'embed',
          value: {
            url: 'javascript:alert(1)',
            provider_name: '',
            title: '',
            thumbnail_url: '',
            embed_url: null,
          },
        },
      ])
    ).toEqual(emptyDoc());
  });

  it('builds an embed as a link paragraph NODE and reads it back as an embed block (todo 526)', () => {
    const doc = bodyBlocksToDoc([
      {
        type: 'embed',
        value: {
          url: 'https://youtu.be/dQw4w9WgXcQ',
          provider_name: 'YouTube',
          title: 'T',
          thumbnail_url: '',
          embed_url: 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ',
        },
      },
    ]);
    // The URL is a link mark's attribute and a text node — never markup.
    expect(doc).toEqual(
      docOf(
        para(
          text('https://youtu.be/dQw4w9WgXcQ', [
            { type: 'link', attrs: { href: 'https://youtu.be/dQw4w9WgXcQ' } },
          ])
        )
      )
    );
    expect(docToBodyBlocks(doc)).toEqual([
      { type: 'embed', value: 'https://youtu.be/dQw4w9WgXcQ' },
    ]);
  });
});

describe('forumBody post_quote blocks (todo 342)', () => {
  const ada = { username: 'ada', display_name: 'Ada', avatar: null, trust_level: 1 };

  it('turns a top-level blockquote carrying data-post-id into a post_quote block', () => {
    expect(
      fromHtml('<p>re:</p><blockquote data-post-id="5"><p>one</p><p>two</p></blockquote>')
    ).toEqual([
      { type: 'paragraph', value: '<p>re:</p>' },
      { type: 'post_quote', value: { post: 5, text: 'one\n\ntwo' } },
    ]);
  });

  it('keeps a blockquote without a usable post id as a legacy quote', () => {
    // No attribute, a non-numeric one, zero and a negative all fall back to
    // `quote`: a post_quote the server is certain to 400 would block the
    // whole reply for a malformed attribute nobody typed on purpose.
    for (const attr of ['', ' data-post-id="abc"', ' data-post-id="0"', ' data-post-id="-3"']) {
      expect(fromHtml(`<blockquote${attr}><p>q</p></blockquote>`)).toEqual([
        { type: 'quote', value: 'q' },
      ]);
    }
  });

  it('writes an available post_quote back with its post id and its text as TEXT nodes', () => {
    const doc = bodyBlocksToDoc([
      {
        type: 'post_quote',
        value: {
          text: '<script>alert(1)</script>\n\nsecond',
          post_id: 5,
          available: true,
          topic_id: 12,
          author: ada,
          is_blocked: false,
          is_muted: false,
        },
      },
    ]);
    expect(doc).toEqual(
      docOf({
        type: 'blockquote',
        attrs: { postId: '5' },
        content: [para(text('<script>alert(1)</script>')), para(text('second'))],
      })
    );
    // ...and reading it back yields the WRITE shape with the original plain text.
    expect(docToBodyBlocks(doc)).toEqual([
      { type: 'post_quote', value: { post: 5, text: '<script>alert(1)</script>\n\nsecond' } },
    ]);
  });

  it('keeps the post id of a quote whose post is no longer available on re-edit', () => {
    // The server exempts ids the stored body already carries from the
    // availability re-check on edit (existing_quote_ids), so the quote keeps
    // its id and attribution instead of silently degrading to a plain quote.
    const doc = bodyBlocksToDoc([
      {
        type: 'post_quote',
        value: {
          text: 'gone',
          post_id: 5,
          available: false,
          topic_id: null,
          author: null,
          is_blocked: false,
          is_muted: false,
        },
      },
    ]);
    expect(doc).toEqual(
      docOf({ type: 'blockquote', attrs: { postId: '5' }, content: [para(text('gone'))] })
    );
    expect(docToBodyBlocks(doc)).toEqual([
      { type: 'post_quote', value: { post: 5, text: 'gone' } },
    ]);
  });

  it('writes a single newline (a list-sourced quote) as a hard break and reads it back as "\\n"', () => {
    // postQuoteText joins list items with one "\n". A bare newline inside a
    // paragraph is collapsed to a space by ProseMirror, so it must travel as
    // a hardBreak, and the break must come back as "\n" — never as a tag.
    const node = postQuoteNode(7, 'one\ntwo\n\nthree');
    expect(node).toEqual({
      type: 'blockquote',
      attrs: { postId: '7' },
      content: [para(text('one'), { type: 'hardBreak' }, text('two')), para(text('three'))],
    });
    expect(docToBodyBlocks(docOf(node!))).toEqual([
      { type: 'post_quote', value: { post: 7, text: 'one\ntwo\n\nthree' } },
    ]);
    // A <br> with whitespace around it (a hand-edited body) trims per line.
    expect(fromHtml('<blockquote><p>a <br> b</p></blockquote>')).toEqual([
      { type: 'quote', value: 'a\nb' },
    ]);
  });

  it('postQuoteNode builds exactly the composer node docToBodyBlocks reads back', () => {
    const node = postQuoteNode(7, 'a < b\n\nc & d');
    expect(node).toEqual({
      type: 'blockquote',
      attrs: { postId: '7' },
      content: [para(text('a < b')), para(text('c & d'))],
    });
    expect(docToBodyBlocks(docOf(node!))).toEqual([
      { type: 'post_quote', value: { post: 7, text: 'a < b\n\nc & d' } },
    ]);
    // Nothing to quote -> no node (the caller must not insert an empty quote).
    expect(postQuoteNode(7, ' \n\n ')).toBeNull();
  });

  it('round-trips through a REAL TipTap editor only WITH the blockquote attribute extension', () => {
    const content = docOf(para(text('a')), postQuoteNode(5, 'q')!, para(text('b')));
    // The composer's own schema (StarterKit's blockquote plus
    // ForumBlockquoteAttrs): the id survives ProseMirror's parse/serialize.
    expect(docToBodyBlocks(throughEditor(content))).toEqual([
      { type: 'paragraph', value: '<p>a</p>' },
      { type: 'post_quote', value: { post: 5, text: 'q' } },
      { type: 'paragraph', value: '<p>b</p>' },
    ]);
    // Control: without it the schema drops the unknown attribute and the
    // quote silently degrades — the exact failure the extension exists for.
    const bare = new Editor({
      extensions: [StarterKit, ForumImage],
      content: '<p>a</p><blockquote data-post-id="5"><p>q</p></blockquote><p>b</p>',
    });
    try {
      expect(docToBodyBlocks(bare.getJSON())).toContainEqual({ type: 'quote', value: 'q' });
    } finally {
      bare.destroy();
    }
  });

  it('keeps the line breaks of a list-sourced quote through a REAL TipTap editor', () => {
    // The seam the unit test cannot cover: the hardBreak survives the schema,
    // so each item keeps its own line and the text reads back with "\n".
    const editor = new Editor({
      extensions: FORUM_SCHEMA_EXTENSIONS,
      content: docOf(postQuoteNode(5, 'one\ntwo\n\nthree')!),
    });
    try {
      expect(editor.getHTML()).toContain('<br>');
      expect(docToBodyBlocks(editor.getJSON())).toEqual([
        { type: 'post_quote', value: { post: 5, text: 'one\ntwo\n\nthree' } },
      ]);
    } finally {
      editor.destroy();
    }
  });
});

describe('postQuoteText (todo 342)', () => {
  it('keeps a hard line break inside a source paragraph as "\\n" (never merges the words)', () => {
    const body = [
      { type: 'paragraph', value: '<p>water  it<br>weekly</p>', id: 'p1' },
    ] as unknown as StreamFieldBlock[];
    expect(postQuoteText(body)).toBe('water it\nweekly');
  });

  it('lifts paragraphs, list items and legacy quotes out as blank-line separated plain text', () => {
    const body: StreamFieldBlock[] = [
      {
        type: 'paragraph',
        value:
          '<p>Hello <strong>there</strong>, <span class="mention" data-mention="ada">@ada</span></p><ul><li>one</li><li>two</li></ul>',
      },
      { type: 'image', value: { id: 1, url: 'https://cdn/x.jpg' } },
      { type: 'quote', value: 'an earlier quote' },
      // A quote of someone else's post is NOT re-quoted: it would put a third
      // person's words under this author's name.
      {
        type: 'post_quote',
        value: {
          text: 'nested',
          post_id: 3,
          available: true,
          topic_id: 1,
          author: null,
          is_blocked: false,
          is_muted: false,
        },
      },
      { type: 'paragraph', value: '<p>bye</p>' },
    ];
    expect(postQuoteText(body)).toBe('Hello there, @ada\n\none\ntwo\n\nan earlier quote\n\nbye');
  });

  it('returns "" for a body with no text, and cuts long text at the cap with an ellipsis', () => {
    expect(postQuoteText([{ type: 'image', value: { id: 1, url: 'https://cdn/x.jpg' } }])).toBe('');
    expect(postQuoteText(undefined)).toBe('');
    const long = 'x'.repeat(QUOTE_TEXT_MAX_CHARS + 100);
    const cut = postQuoteText([{ type: 'paragraph', value: `<p>${long}</p>` }]);
    expect(cut).toHaveLength(QUOTE_TEXT_MAX_CHARS + 1);
    expect(cut.endsWith('…')).toBe(true);
    // The literal, not the binding: the cap itself is the guarantee — it must
    // stay under the server's 1000-char QUOTE_MAX_CHARS.
    expect(QUOTE_TEXT_MAX_CHARS).toBe(500);
  });
});

describe('isBlankHtml', () => {
  // The single definition replacing verbatim copies in ThreadDetailPage and
  // NewThreadPage. It gates canSubmit and the reply/edit disabled states, so
  // "blank" is a user-visible contract, not an internal detail.

  it('treats structurally-empty rich text as blank', () => {
    expect(isBlankHtml('')).toBe(true);
    expect(isBlankHtml('<p></p>')).toBe(true);
    expect(isBlankHtml('<p>   </p>')).toBe(true);
    expect(isBlankHtml('<p><br></p>')).toBe(true);
    expect(isBlankHtml('<div><p></p><p>  </p></div>')).toBe(true);
  });

  it('treats any real text as not blank', () => {
    expect(isBlankHtml('<p>hi</p>')).toBe(false);
    expect(isBlankHtml('<p><strong>a</strong></p>')).toBe(false);
    expect(isBlankHtml('x')).toBe(false);
  });

  it('counts a numeric entity for ASCII whitespace as blank (behaviour change)', () => {
    // The replaced implementation was `html.replace(/<[^>]*>/g, '').trim()`,
    // which left "&#32;" as six literal characters and called it NOT blank.
    expect(isBlankHtml('<p>&#32;</p>')).toBe(true); // encoded space
    expect(isBlankHtml('<p>&#9;</p>')).toBe(true); // encoded tab
  });

  it('also counts malformed and script/style-only bodies as blank', () => {
    // The other three measured divergences from the old regex. Every one of
    // them points the same way — toward "blank" — so the failure mode of
    // getting this wrong is a silently disabled submit button, not a leak.
    expect(isBlankHtml('<p title="x>hello</p>')).toBe(true); // regex: false
    expect(isBlankHtml('<script>alert(1)</script>')).toBe(true); // regex: false
    expect(isBlankHtml('<style>p{color:red}</style>')).toBe(true); // regex: false
  });

  it('leaves every other entity exactly as the old regex had it', () => {
    // DOMPurify re-serializes on output, so &nbsp; stays "&nbsp;" rather than
    // decoding to U+00A0 — the non-breaking-space cases do NOT change.
    expect(isBlankHtml('<p>&nbsp;</p>')).toBe(false);
    expect(isBlankHtml('<p>&#160;</p>')).toBe(false);
    expect(isBlankHtml('<p>&amp;</p>')).toBe(false);
    expect(isBlankHtml('<p>&lt;</p>')).toBe(false);
  });

  it('keeps a truncated tail non-blank, exactly as the regex did', () => {
    // Pinned as a NON-difference. An earlier version of this test claimed the
    // regex "mishandled" this; it does not — both call `<p>hello<` non-blank.
    expect(isBlankHtml('<p>hello<')).toBe(false);
    expect(isBlankHtml('<p>&nbsp;</p>')).toBe(false);
  });

  it('returns a boolean, never the stripped text', () => {
    // The reason this was never a sanitizer bug: the stripped string does not
    // escape the function, so it can never reach a render sink. Asserted by
    // value, not by `typeof` — a `typeof x === 'boolean'` check passes for any
    // boolean-returning implementation, including a broken one.
    expect(isBlankHtml('<p>real text</p>')).toBe(false);
    expect(isBlankHtml('<p></p>')).toBe(true);
  });
});

describe('isBlankDoc (todo 526)', () => {
  // The submit gate on the composer's JSON document: the same rule as
  // isBlankHtml, applied to the editor's own serialisation, so "blank" did
  // not move when the content model changed.
  it('treats an empty or whitespace-only document as blank', () => {
    expect(isBlankDoc(emptyDoc())).toBe(true);
    expect(isBlankDoc(undefined)).toBe(true);
    expect(isBlankDoc(docOf(para(text('   ')), para({ type: 'hardBreak' })))).toBe(true);
  });

  it('treats text, a quote or a mention as not blank', () => {
    expect(isBlankDoc(docOf(para(text('hi'))))).toBe(false);
    expect(isBlankDoc(docOf(postQuoteNode(5, 'q')!, para()))).toBe(false);
    expect(isBlankDoc(docOf(para({ type: 'mention', attrs: { id: 'ada', label: 'ada' } })))).toBe(
      false
    );
  });

  it('keeps an image-only body blank, exactly as the HTML gate had it', () => {
    expect(isBlankDoc(docOf(image({ src: '/x.jpg', imageId: '5' })))).toBe(true);
  });
});

describe('composer drafts (todo 526)', () => {
  it('reads a JSON document draft, and a pre-526 HTML draft through the schema', () => {
    const doc = docOf(para(text('kept')));
    expect(draftToDoc(JSON.stringify(doc))).toEqual(doc);
    expect(draftToDoc('<p>legacy <strong>draft</strong></p>')).toEqual(
      docOf(para(text('legacy '), text('draft', [{ type: 'bold' }])))
    );
  });

  it('turns a missing, blank or schema-invalid draft into an empty document instead of crashing the editor', () => {
    expect(draftToDoc(null)).toEqual(emptyDoc());
    expect(draftToDoc('')).toEqual(emptyDoc());
    expect(draftToDoc(JSON.stringify(docOf({ type: 'nope' })))).toEqual(emptyDoc());
    expect(draftToDoc(JSON.stringify({ type: 'doc', content: [text('bare text')] }))).toEqual(
      emptyDoc()
    );
    expect(toComposerDoc(42)).toEqual(emptyDoc());
  });
});

describe('forumBody image blocks (todo 357 — ImageBlock)', () => {
  it('carries authored alt text through docToBodyBlocks instead of dropping it', () => {
    // Under ImageChooserBlock the editor's alt was discarded and re-derived
    // server-side, which is why alt used to be uneditable after insert.
    const html = '<img src="https://cdn/x.jpg" alt="  A monstera leaf  " data-image-id="5">';
    expect(fromHtml(html)).toEqual([
      { type: 'image', value: { image: 5, alt_text: 'A monstera leaf', decorative: false } },
    ]);
  });

  it('treats a blank alt as decorative, never as alt_text="" + decorative:false', () => {
    // That pair is the one ImageBlock.clean() refuses; storing it would make
    // the post un-editable in the Wagtail admin.
    const html = '<img src="https://cdn/x.jpg" alt="   " data-image-id="5">';
    expect(fromHtml(html)).toEqual([
      { type: 'image', value: { image: 5, alt_text: '', decorative: true } },
    ]);
  });

  it('honours an explicit decorative flag even when alt text is present', () => {
    const html =
      '<img src="https://cdn/x.jpg" alt="ignored" data-image-id="5" data-decorative="true">';
    expect(fromHtml(html)).toEqual([
      { type: 'image', value: { image: 5, alt_text: '', decorative: true } },
    ]);
  });

  it('round-trips alt and decorative through bodyBlocksToDoc and back', () => {
    // The edit path: bodyBlocksToDoc seeds the composer, the author saves, and
    // docToBodyBlocks must reproduce what the server sent — otherwise editing
    // an untouched post silently rewrites its accessibility metadata.
    const body: StreamFieldBlock[] = [
      {
        type: 'image',
        value: { id: 42, url: 'https://cdn/p.jpg', alt: 'A fern frond', decorative: false },
      },
      { type: 'image', value: { id: 43, url: 'https://cdn/q.jpg', alt: '', decorative: true } },
    ];
    expect(docToBodyBlocks(bodyBlocksToDoc(body))).toEqual([
      { type: 'image', value: { image: 42, alt_text: 'A fern frond', decorative: false } },
      { type: 'image', value: { image: 43, alt_text: '', decorative: true } },
    ]);
  });

  it('keeps an alt containing a quote as an attribute VALUE, never markup', () => {
    const body: StreamFieldBlock[] = [
      {
        type: 'image',
        value: { id: 1, url: 'https://cdn/x.jpg', alt: 'a " onerror="alert(1)', decorative: false },
      },
    ];
    const doc = bodyBlocksToDoc(body);
    expect(doc.content?.[0]?.attrs?.alt).toBe('a " onerror="alert(1)');
    // The editor's serialisation escapes it, so no attribute breaks out...
    expect(generateHTML(doc, FORUM_SCHEMA_EXTENSIONS)).not.toContain('onerror="alert(1)"');
    // ...and it survives the round trip as literal text.
    expect(docToBodyBlocks(doc)).toEqual([
      { type: 'image', value: { image: 1, alt_text: 'a " onerror="alert(1)', decorative: false } },
    ]);
  });
});

describe('forumBody image id guard (todo 357 review)', () => {
  it('drops a non-numeric image id instead of emitting NaN', () => {
    // `!rawId` alone rejected the empty string but not "abc", which yielded
    // {image: NaN} -> JSON null -> the server 400s the WHOLE post rather than
    // one image being dropped.
    expect(
      fromHtml('<img src="/a.jpg" data-image-id="abc"><img src="/b.jpg" data-image-id="9">')
    ).toEqual([{ type: 'image', value: { image: 9, alt_text: '', decorative: true } }]);
    expect(docToBodyBlocks(docOf(image({ imageId: 'abc' }), image({ imageId: 9 })))).toEqual([
      { type: 'image', value: { image: 9, alt_text: '', decorative: true } },
    ]);
  });

  it('drops a non-numeric nested id in a blockquote too', () => {
    const doc = docOf({
      type: 'blockquote',
      content: [para(text('q')), image({ imageId: '12abc' })],
    });
    expect(docToBodyBlocks(doc)).toEqual([{ type: 'quote', value: 'q' }]);
  });
});

describe('an image deleted after posting (todo 374)', () => {
  // The composer's RE-EDIT path. The server sends `value: null` for an image
  // whose row is gone; destructuring it threw, so opening an old post for
  // editing crashed outright once the photo had been deleted.
  it('positive control: a live image still becomes an image node', () => {
    const live: StreamFieldBlock[] = [
      {
        type: 'image',
        value: { id: 9, url: '/media/x.jpg', alt: 'a fern', decorative: false },
        id: 'b1',
      },
    ];
    expect(bodyBlocksToDoc(live).content?.[0]?.attrs?.imageId).toBe('9');
  });

  it('drops the dead block instead of throwing', () => {
    const dead: StreamFieldBlock[] = [{ type: 'image', value: null, id: 'b1' }];
    expect(bodyBlocksToDoc(dead)).toEqual(emptyDoc());
  });

  it('keeps the surrounding blocks intact', () => {
    const mixed: StreamFieldBlock[] = [
      { type: 'paragraph', value: '<p>before</p>', id: 'a' },
      { type: 'image', value: null, id: 'b' },
      { type: 'paragraph', value: '<p>after</p>', id: 'c' },
    ];
    expect(bodyBlocksToDoc(mixed)).toEqual(docOf(para(text('before')), para(text('after'))));
  });
});

describe('image attributes survive rehydrate exactly (todo 441, todo 526)', () => {
  // Before todo 526 the composer's <img> was a hand-built HTML string: escaping
  // only `"` let an `&` through (todo 441), and NO escaping could stop the HTML
  // parser normalising CR/CRLF to LF and NUL to U+FFFD in attribute values
  // (todo 443). As node attributes the values are never parsed, so every one
  // below — the CR/LF/NUL ones included — comes back byte-identical.
  const ALTS = [
    'Tom &amp; Jerry',
    'leaf &copy 2026',
    'a < b > c',
    'say "hi"',
    "it's",
    'A plain monstera leaf',
    'line one\r\nline two',
    'carriage\rreturn',
    'nul\u0000byte',
  ];
  const imageBody = (alt: string, url = 'https://cdn/p.jpg'): StreamFieldBlock[] => [
    { type: 'image', value: { id: 42, url, alt, decorative: alt === '' } },
  ];
  const expected = (alt: string) => [
    { type: 'image', value: { image: 42, alt_text: alt, decorative: alt === '' } },
  ];

  it.each([...ALTS, ''])('alt %j survives bodyBlocksToDoc -> docToBodyBlocks', (alt) => {
    expect(docToBodyBlocks(bodyBlocksToDoc(imageBody(alt)))).toEqual(expected(alt));
  });

  it.each([...ALTS, ''])('alt %j survives a real TipTap rehydrate -> getJSON', (alt) => {
    // The production edit path: bodyBlocksToDoc seeds the editor, the author
    // saves, getJSON() is what docToBodyBlocks reads.
    expect(docToBodyBlocks(throughEditor(bodyBlocksToDoc(imageBody(alt))))).toEqual(expected(alt));
  });

  it('keeps the image url an attribute value: src survives and cannot break out', () => {
    const url = 'https://cdn/x.jpg?a=1&amp;b=2&copy=3" onerror="alert(1)';
    const editor = new Editor({
      extensions: FORUM_SCHEMA_EXTENSIONS,
      content: bodyBlocksToDoc(imageBody('leaf', url)),
    });
    try {
      const img = editor.view.dom.querySelector('img');
      expect(img?.getAttribute('src')).toBe(url);
      expect(img?.hasAttribute('onerror')).toBe(false);
    } finally {
      editor.destroy();
    }
  });

  it('leaves ordinary values byte-identical', () => {
    expect(bodyBlocksToDoc(imageBody("it's a fern"))).toEqual(
      docOf(
        image({ src: 'https://cdn/p.jpg', alt: "it's a fern", imageId: '42', decorative: false })
      )
    );
  });

  // PR #826 review round 1.
  it('an image block with a missing url degrades instead of throwing', () => {
    const doc = bodyBlocksToDoc([
      {
        type: 'image',
        value: { id: 5, url: undefined as unknown as string, alt: 'x', decorative: false },
      },
    ] as never);
    expect(doc.content?.[0]?.attrs).toMatchObject({ src: '', imageId: '5' });
  });

  it('keeps a non-numeric image id inert, and never sends it', () => {
    const doc = bodyBlocksToDoc([
      {
        type: 'image',
        value: {
          id: '1" onerror="x' as unknown as number,
          url: '/m.jpg',
          alt: '',
          decorative: true,
        },
      },
    ] as never);
    expect(doc.content?.[0]?.attrs?.imageId).toBe('1" onerror="x');
    expect(generateHTML(doc, FORUM_SCHEMA_EXTENSIONS)).not.toContain('onerror="x"');
    expect(docToBodyBlocks(doc)).toEqual([]);
  });
});

describe('forumBody link_preview blocks (todo 428)', () => {
  const card = {
    url: 'https://example.com/a?b=1&c=2',
    title: 'T',
    description: '',
    site_name: '',
    domain: 'example.com',
    image_url: null,
  };

  it('puts a link card back into the composer as a link paragraph NODE (todo 526)', () => {
    const doc = bodyBlocksToDoc([{ type: 'link_preview', value: card }]);

    expect(doc).toEqual(docOf(para(text(card.url, [{ type: 'link', attrs: { href: card.url } }]))));
    // Saved unchanged, it goes back as a link-only paragraph (printed by the
    // editor's schema, as getHTML() did), which the server turns into the
    // same stored card without fetching.
    const blocks = docToBodyBlocks(doc);
    expect(blocks).toHaveLength(1);
    expect(blocks[0].type).toBe('paragraph');
    expect(blocks[0].value).toContain('href="https://example.com/a?b=1&amp;c=2"');
    expect(blocks[0].value).toContain('>https://example.com/a?b=1&amp;c=2</a></p>');
  });

  it('keeps the rest of the post around a card', () => {
    const doc = bodyBlocksToDoc([
      { type: 'paragraph', value: '<p>before</p>' },
      { type: 'link_preview', value: card },
      { type: 'paragraph', value: '<p>after</p>' },
    ]);

    expect(doc).toEqual(
      docOf(
        para(text('before')),
        para(text(card.url, [{ type: 'link', attrs: { href: card.url } }])),
        para(text('after'))
      )
    );
  });

  it('drops a null card and a card whose stored link is not http(s)', () => {
    expect(
      bodyBlocksToDoc([
        { type: 'link_preview', value: null },
        { type: 'link_preview', value: { ...card, url: 'javascript:alert(1)' } },
      ])
    ).toEqual(emptyDoc());
  });
});

describe('every stored block shape round-trips through the editor (todo 526)', () => {
  // The edit path end to end: the stored READ body seeds a REAL editor via
  // bodyBlocksToDoc, the author touches nothing, and docToBodyBlocks(getJSON())
  // must be exactly the WRITE form of what is stored — so re-saving an
  // untouched post changes nothing (and ThreadDetailPage sends no PATCH).
  const ada = { username: 'ada', display_name: 'Ada', avatar: null, trust_level: 1 };
  const stored: StreamFieldBlock[] = [
    { type: 'paragraph', value: '<p>Hello <strong>there</strong> <em>you</em></p>' },
    { type: 'paragraph', value: '<h2>Care</h2><ul><li><p>water</p></li></ul>' },
    {
      type: 'image',
      value: { id: 9, url: '/m/x.jpg', alt: 'Tom &amp; Jerry\r\nleaf', decorative: false },
    },
    { type: 'image', value: { id: 10, url: '/m/y.jpg', alt: '', decorative: true } },
    { type: 'image', value: null },
    {
      type: 'embed',
      value: {
        url: 'https://youtu.be/dQw4w9WgXcQ',
        provider_name: 'YouTube',
        title: 'T',
        thumbnail_url: '',
        embed_url: 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ',
      },
    },
    {
      type: 'embed',
      value: {
        url: 'https://vimeo.com/148751763',
        provider_name: 'Vimeo',
        title: 'T',
        thumbnail_url: '',
        embed_url: 'https://player.vimeo.com/video/148751763',
      },
    },
    { type: 'quote', value: 'line one\nline two\n\nthird' },
    {
      type: 'post_quote',
      value: {
        text: 'a < b\n\nc & d',
        post_id: 5,
        available: true,
        topic_id: 12,
        author: ada,
        is_blocked: false,
        is_muted: false,
      },
    },
    {
      type: 'post_quote',
      value: {
        text: 'gone',
        post_id: 6,
        available: false,
        topic_id: null,
        author: null,
        is_blocked: false,
        is_muted: false,
      },
    },
  ];
  const written = [
    {
      type: 'paragraph',
      value:
        '<p>Hello <strong>there</strong> <em>you</em></p><h2>Care</h2><ul><li><p>water</p></li></ul>',
    },
    {
      type: 'image',
      value: { image: 9, alt_text: 'Tom &amp; Jerry\r\nleaf', decorative: false },
    },
    { type: 'image', value: { image: 10, alt_text: '', decorative: true } },
    { type: 'embed', value: 'https://youtu.be/dQw4w9WgXcQ' },
    { type: 'embed', value: 'https://vimeo.com/148751763' },
    { type: 'quote', value: 'line one\nline two\n\nthird' },
    { type: 'post_quote', value: { post: 5, text: 'a < b\n\nc & d' } },
    { type: 'post_quote', value: { post: 6, text: 'gone' } },
  ];

  it('rehydrates every shape and re-serialises it unchanged', () => {
    const doc = throughEditor(bodyBlocksToDoc(stored));
    expect(docToBodyBlocks(doc)).toEqual(written);
    expect(isUnchangedBody(doc, stored)).toBe(true);
  });

  it('a link card and a linked paragraph settle after one pass', () => {
    // A link carries the editor's Link attributes once printed (as getHTML()
    // always did); the server's sanitizer keeps only href/title. What the
    // composer writes is stable from then on.
    const body: StreamFieldBlock[] = [
      { type: 'paragraph', value: '<p>see <a href="https://example.com/x">this</a></p>' },
      {
        type: 'link_preview',
        value: {
          url: 'https://example.com/a?b=1&c=2',
          title: 'T',
          description: '',
          site_name: '',
          domain: 'example.com',
          image_url: null,
        },
      },
    ];
    const once = docToBodyBlocks(throughEditor(bodyBlocksToDoc(body)));
    expect(once.map((b) => b.type)).toEqual(['paragraph']);
    expect(once[0].value).toContain('href="https://example.com/x"');
    expect(once[0].value).toContain('href="https://example.com/a?b=1&amp;c=2"');
    expect(
      docToBodyBlocks(throughEditor(bodyBlocksToDoc(structuredClone(once) as StreamFieldBlock[])))
    ).toEqual(once);
    expect(isUnchangedBody(throughEditor(bodyBlocksToDoc(body)), body)).toBe(true);
  });

  it('reports an edited document as changed', () => {
    const doc = bodyBlocksToDoc(stored);
    const edited = { ...doc, content: [...(doc.content ?? []), para(text('one more'))] };
    expect(isUnchangedBody(edited, stored)).toBe(false);
  });
});
