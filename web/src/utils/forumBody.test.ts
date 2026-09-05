import { describe, it, expect } from 'vitest';
import { Editor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import {
  htmlToBodyBlocks,
  bodyBlocksToHtml,
  postQuoteHtml,
  postQuoteText,
  QUOTE_TEXT_MAX_CHARS,
} from './forumBody';
import { ForumImage } from '../components/forum/forumImageNode';
import { ForumBlockquoteAttrs } from '../components/forum/forumBlockquoteAttrs';
import type { StreamFieldBlock } from '@/types/blog';

describe('forumBody serialization', () => {
  it('htmlToBodyBlocks splits interleaved text and images into separate blocks', () => {
    const html = '<p>before</p><img src="https://cdn/x.jpg" alt="a" data-image-id="5"><p>after</p>';
    expect(htmlToBodyBlocks(html)).toEqual([
      { type: 'paragraph', value: '<p>before</p>' },
      { type: 'image', value: 5 },
      { type: 'paragraph', value: '<p>after</p>' },
    ]);
  });

  it('htmlToBodyBlocks does not make an image block for an <img> without an id', () => {
    // Only uploaded (id-bearing) images become image blocks.
    const blocks = htmlToBodyBlocks('<p>x</p><img src="https://cdn/y.jpg">');
    expect(blocks.some((b) => b.type === 'image')).toBe(false);
  });

  it('bodyBlocksToHtml rebuilds <img> carrying the wagtail id', () => {
    const body: StreamFieldBlock[] = [
      { type: 'paragraph', value: '<p>hi</p>' },
      { type: 'image', value: { id: 9, url: 'https://cdn/z.jpg', alt: 'cap' } },
    ];
    const html = bodyBlocksToHtml(body);
    expect(html).toContain('<p>hi</p>');
    expect(html).toContain('data-image-id="9"');
    expect(html).toContain('src="https://cdn/z.jpg"');
  });

  it('escapes a bare top-level text node instead of letting it become markup', () => {
    // `buffer` is joined into a `paragraph` block whose value is HTML, so a text
    // node's characters must be escaped on the way in (CodeQL js/xss-through-dom).
    // Also the correct rendering: the user typed "<", they did not open a tag.
    expect(htmlToBodyBlocks('a < b')).toEqual([{ type: 'paragraph', value: 'a &lt; b' }]);
    expect(htmlToBodyBlocks('<p>ok</p>plain & text')).toEqual([
      { type: 'paragraph', value: '<p>ok</p>plain &amp; text' },
    ]);
  });

  it('round-trips a body through HTML and back, preserving image ids and order', () => {
    const body: StreamFieldBlock[] = [
      { type: 'paragraph', value: '<p>look</p>' },
      { type: 'image', value: { id: 42, url: 'https://cdn/p.jpg', alt: '' } },
      { type: 'paragraph', value: '<p>done</p>' },
    ];
    expect(htmlToBodyBlocks(bodyBlocksToHtml(body))).toEqual([
      { type: 'paragraph', value: '<p>look</p>' },
      { type: 'image', value: 42 },
      { type: 'paragraph', value: '<p>done</p>' },
    ]);
  });

  it('round-trips through a REAL TipTap editor: ForumImage stays a top-level block with its id', () => {
    // Guards the seam the unit tests cannot: that the actual editor's getHTML()
    // emits an <img> at body level (block, not inline-in-<p>) and preserves
    // data-image-id through the ProseMirror schema — otherwise the image is
    // swept into a paragraph, nh3 strips it on save, and it vanishes in prod.
    const editor = new Editor({
      extensions: [StarterKit, ForumImage],
      content: '<p>a</p><img src="https://cdn/x.jpg" data-image-id="5"><p>b</p>',
    });
    try {
      expect(htmlToBodyBlocks(editor.getHTML())).toEqual([
        { type: 'paragraph', value: '<p>a</p>' },
        { type: 'image', value: 5 },
        { type: 'paragraph', value: '<p>b</p>' },
      ]);
    } finally {
      editor.destroy();
    }
  });
});

describe('forumBody quote blocks (audit M1)', () => {
  it('lifts a top-level <blockquote> into its own quote block as PLAIN text', () => {
    // BlockQuoteBlock is a Wagtail TextBlock — the value is text, never markup.
    expect(htmlToBodyBlocks('<p>before</p><blockquote><p>quoted</p></blockquote>')).toEqual([
      { type: 'paragraph', value: '<p>before</p>' },
      { type: 'quote', value: 'quoted' },
    ]);
  });

  it('joins a multi-paragraph blockquote instead of mashing the text together', () => {
    // Raw textContent would yield "onetwo".
    expect(htmlToBodyBlocks('<blockquote><p>one</p><p>two</p></blockquote>')).toEqual([
      { type: 'quote', value: 'one\n\ntwo' },
    ]);
  });

  it('drops an empty blockquote rather than emitting a blank quote block', () => {
    expect(htmlToBodyBlocks('<blockquote><p>   </p></blockquote>')).toEqual([]);
  });

  it('hoists an image nested in a blockquote out instead of silently losing it', () => {
    // textContent cannot see an <img>; without the hoist the user's upload vanishes.
    expect(
      htmlToBodyBlocks(
        '<blockquote><p>see</p><img src="https://cdn/x.jpg" data-image-id="7"></blockquote>'
      )
    ).toEqual([
      { type: 'quote', value: 'see' },
      { type: 'image', value: 7 },
    ]);
  });

  it('skips a nested image with a blank id instead of emitting value 0', () => {
    // `<img data-image-id="">` matches the selector but has no usable id.
    // Emitting 0 (or NaN -> null) fails validate_forum_body server-side, so ONE
    // unusable image would 400 the whole save. Match the top-level branch and
    // drop it. The real image alongside it must still survive.
    expect(
      htmlToBodyBlocks(
        '<blockquote><p>q</p><img data-image-id=""><img data-image-id="8"></blockquote>'
      )
    ).toEqual([
      { type: 'quote', value: 'q' },
      { type: 'image', value: 8 },
    ]);
  });

  it('ESCAPES quote text on the way back into composer HTML', () => {
    // The server leaves quote values unsanitized ("text by contract"), so an
    // unescaped write-back would turn stored text into real editor markup.
    const html = bodyBlocksToHtml([{ type: 'quote', value: '<script>alert(1)</script>' }]);
    expect(html).toContain('&lt;script&gt;');
    expect(html).not.toContain('<script>');
  });

  it('round-trips a quote containing markup-looking text unchanged (idempotent)', () => {
    const body: StreamFieldBlock[] = [
      { type: 'paragraph', value: '<p>intro</p>' },
      { type: 'quote', value: 'a < b\n\nsecond line' },
    ];
    const once = htmlToBodyBlocks(bodyBlocksToHtml(body));
    expect(once).toEqual([
      { type: 'paragraph', value: '<p>intro</p>' },
      { type: 'quote', value: 'a < b\n\nsecond line' },
    ]);
    // Stable under a second pass — re-editing a saved post must not drift.
    expect(htmlToBodyBlocks(bodyBlocksToHtml(once as StreamFieldBlock[]))).toEqual(once);
  });

  it('does not promote a single newline to a paragraph break on re-edit', () => {
    // A value with single "\n" separators can arrive from a non-browser client.
    // Splitting on /\n+/ would rewrite it to "\n\n" every time the post is
    // opened and saved, since blockquoteText always rejoins with "\n\n".
    const blocks = htmlToBodyBlocks(
      bodyBlocksToHtml([{ type: 'quote', value: 'line one\nline two' }])
    );
    expect(blocks).toEqual([{ type: 'quote', value: 'line one\nline two' }]);
  });

  it('escapes a bare-text blockquote through the full re-edit round trip', () => {
    // Pins the exact flow CodeQL js/xss-through-dom traces: blockquoteText's
    // `el.textContent` fallback (a blockquote with no element children) -> a
    // `quote` value -> bodyBlocksToHtml -> DOMParser. The escape is applied
    // where the value becomes HTML, so the payload stays inert text.
    const blocks = htmlToBodyBlocks('<blockquote><script>alert(1)</script></blockquote>');
    expect(blocks).toEqual([{ type: 'quote', value: 'alert(1)' }]);

    const evil = htmlToBodyBlocks(
      '<blockquote>a &lt;img src=x onerror=alert(1)&gt; b</blockquote>'
    );
    const html = bodyBlocksToHtml(evil as StreamFieldBlock[]);
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;img');
    // ...and re-parsing that HTML yields the same plain text, not an image block.
    expect(htmlToBodyBlocks(html)).toEqual(evil);
  });

  it('round-trips through a REAL TipTap editor: blockquote stays top-level', () => {
    // The seam the unit tests cannot cover — that StarterKit's Blockquote emits
    // at body level so htmlToBodyBlocks sees it (rather than nested in a <p>,
    // where nh3 would strip it on save and the quote would vanish in prod).
    const editor = new Editor({
      extensions: [StarterKit, ForumImage],
      content: '<p>a</p><blockquote><p>quoted</p></blockquote><p>b</p>',
    });
    try {
      expect(htmlToBodyBlocks(editor.getHTML())).toEqual([
        { type: 'paragraph', value: '<p>a</p>' },
        { type: 'quote', value: 'quoted' },
        { type: 'paragraph', value: '<p>b</p>' },
      ]);
    } finally {
      editor.destroy();
    }
  });
});

describe('forumBody embed blocks (todo 344)', () => {
  it('turns a paragraph that is only a YouTube or Vimeo link into an embed block', () => {
    const blocks = htmlToBodyBlocks(
      '<p>Watch this:</p><p>https://youtu.be/dQw4w9WgXcQ</p><p><a href="https://vimeo.com/148751763">https://vimeo.com/148751763</a></p>'
    );
    expect(blocks).toEqual([
      { type: 'paragraph', value: '<p>Watch this:</p>' },
      { type: 'embed', value: 'https://youtu.be/dQw4w9WgXcQ' },
      { type: 'embed', value: 'https://vimeo.com/148751763' },
    ]);
  });

  it('leaves a link inside prose, or an unknown provider, as ordinary paragraph text', () => {
    const blocks = htmlToBodyBlocks(
      '<p>See https://youtu.be/dQw4w9WgXcQ for details</p><p>https://example.com/video/1</p>'
    );
    expect(blocks.every((b) => b.type === 'paragraph')).toBe(true);
    expect(blocks).toHaveLength(1);
  });

  it('accepts a youtube.com/live share link as an embed, and drops a persisted non-http(s) embed url on re-edit', () => {
    expect(
      htmlToBodyBlocks('<p>https://www.youtube.com/live/abcDEF12345?feature=share</p>')
    ).toEqual([{ type: 'embed', value: 'https://www.youtube.com/live/abcDEF12345?feature=share' }]);
    expect(
      bodyBlocksToHtml([
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
    ).toBe('');
  });

  it('round-trips an embed envelope back to a link paragraph and then to an embed block', () => {
    const html = bodyBlocksToHtml([
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
    expect(html).toBe(
      '<p><a href="https://youtu.be/dQw4w9WgXcQ">https://youtu.be/dQw4w9WgXcQ</a></p>'
    );
    expect(htmlToBodyBlocks(html)).toEqual([
      { type: 'embed', value: 'https://youtu.be/dQw4w9WgXcQ' },
    ]);
  });
});

describe('forumBody post_quote blocks (todo 342)', () => {
  const ada = { username: 'ada', display_name: 'Ada', avatar: null, trust_level: 1 };

  it('turns a top-level blockquote carrying data-post-id into a post_quote block', () => {
    expect(
      htmlToBodyBlocks('<p>re:</p><blockquote data-post-id="5"><p>one</p><p>two</p></blockquote>')
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
      expect(htmlToBodyBlocks(`<blockquote${attr}><p>q</p></blockquote>`)).toEqual([
        { type: 'quote', value: 'q' },
      ]);
    }
  });

  it('writes an available post_quote back with its post id and ESCAPED text', () => {
    const html = bodyBlocksToHtml([
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
    expect(html).toBe(
      '<blockquote data-post-id="5"><p>&lt;script&gt;alert(1)&lt;/script&gt;</p><p>second</p></blockquote>'
    );
    // ...and re-parsing yields the WRITE shape with the original plain text.
    expect(htmlToBodyBlocks(html)).toEqual([
      { type: 'post_quote', value: { post: 5, text: '<script>alert(1)</script>\n\nsecond' } },
    ]);
  });

  it('keeps the post id of a quote whose post is no longer available on re-edit', () => {
    // The server exempts ids the stored body already carries from the
    // availability re-check on edit (existing_quote_ids), so the quote keeps
    // its id and attribution instead of silently degrading to a plain quote.
    const html = bodyBlocksToHtml([
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
    expect(html).toBe('<blockquote data-post-id="5"><p>gone</p></blockquote>');
    expect(htmlToBodyBlocks(html)).toEqual([
      { type: 'post_quote', value: { post: 5, text: 'gone' } },
    ]);
  });

  it('writes a single newline (a list-sourced quote) as <br> and reads it back as "\\n"', () => {
    // postQuoteText joins list items with one "\n". A bare newline inside a
    // <p> is collapsed to a space by ProseMirror, so it must travel as <br>,
    // and the <br> must come back as "\n" — never as a tag in `text`.
    const html = postQuoteHtml(7, 'one\ntwo\n\nthree');
    expect(html).toBe('<blockquote data-post-id="7"><p>one<br>two</p><p>three</p></blockquote>');
    expect(htmlToBodyBlocks(html)).toEqual([
      { type: 'post_quote', value: { post: 7, text: 'one\ntwo\n\nthree' } },
    ]);
    // A <br> with whitespace around it (a hand-edited body) trims per line.
    expect(htmlToBodyBlocks('<blockquote><p>a <br> b</p></blockquote>')).toEqual([
      { type: 'quote', value: 'a\nb' },
    ]);
  });

  it('postQuoteHtml builds exactly the composer form htmlToBodyBlocks reads back', () => {
    const html = postQuoteHtml(7, 'a < b\n\nc & d');
    expect(html).toBe('<blockquote data-post-id="7"><p>a &lt; b</p><p>c &amp; d</p></blockquote>');
    expect(htmlToBodyBlocks(html)).toEqual([
      { type: 'post_quote', value: { post: 7, text: 'a < b\n\nc & d' } },
    ]);
  });

  it('round-trips through a REAL TipTap editor only WITH the blockquote attribute extension', () => {
    const content = '<p>a</p><blockquote data-post-id="5"><p>q</p></blockquote><p>b</p>';
    // The composer's own configuration (StarterKit's blockquote plus
    // ForumBlockquoteAttrs): the id survives ProseMirror's parse/serialize.
    const editor = new Editor({
      extensions: [StarterKit, ForumImage, ForumBlockquoteAttrs],
      content,
    });
    try {
      expect(htmlToBodyBlocks(editor.getHTML())).toEqual([
        { type: 'paragraph', value: '<p>a</p>' },
        { type: 'post_quote', value: { post: 5, text: 'q' } },
        { type: 'paragraph', value: '<p>b</p>' },
      ]);
    } finally {
      editor.destroy();
    }
    // Control: without it the schema drops the unknown attribute and the
    // quote silently degrades — the exact failure the extension exists for.
    const bare = new Editor({ extensions: [StarterKit, ForumImage], content });
    try {
      expect(htmlToBodyBlocks(bare.getHTML())).toContainEqual({ type: 'quote', value: 'q' });
    } finally {
      bare.destroy();
    }
  });

  it('keeps the line breaks of a list-sourced quote through a REAL TipTap editor', () => {
    // The seam the unit test cannot cover: ProseMirror collapses a bare "\n"
    // inside a paragraph to a space, so list items would run together
    // ("one two"). Written as <br> (StarterKit's HardBreak) each item keeps
    // its own line, and the text reads back with "\n" between items.
    const editor = new Editor({
      extensions: [StarterKit, ForumImage, ForumBlockquoteAttrs],
      content: postQuoteHtml(5, 'one\ntwo\n\nthree'),
    });
    try {
      expect(editor.getHTML()).toContain('<br>');
      expect(htmlToBodyBlocks(editor.getHTML())).toEqual([
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
