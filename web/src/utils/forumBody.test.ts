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
