import { describe, it, expect } from 'vitest';
import { Editor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { htmlToBodyBlocks, bodyBlocksToHtml } from './forumBody';
import { ForumImage } from '../components/forum/forumImageNode';
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
