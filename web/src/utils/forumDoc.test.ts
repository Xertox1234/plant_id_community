import { describe, expect, it } from 'vitest';
import { generateHTML, type JSONContent } from '@tiptap/react';
import { FORUM_SCHEMA_EXTENSIONS } from '../components/forum/forumEditorSchema';
import type { StreamFieldBlock } from '@/types/blog';
import { docToBodyBlocks, isBlankHtml } from './forumBody';
import { isBlankDoc, postQuoteNode, postQuoteText, QUOTE_TEXT_MAX_CHARS } from './forumDoc';

/**
 * The shared quote rule (owner decision, audit F3), written out on its own so
 * it can disagree with postQuoteText: whitespace collapsed and trimmed, HTML
 * entities decoded, one trailing "…" ignored, the rest a contiguous piece of
 * the post's plain text, with block boundaries and <br> as whitespace.
 */
const collapse = (s: string) => s.replace(/\s+/g, ' ').trim();

function plainText(body: StreamFieldBlock[]): string {
  const decode = (html: string) => {
    const el = document.createElement('textarea');
    el.innerHTML = html;
    return el.value;
  };
  const parts = body.map((block) => {
    const value = (block as { value: unknown }).value;
    if (block.type === 'paragraph') {
      const spaced = String(value).replace(
        /<\/?(?:p|div|li|ul|ol|h[1-6]|blockquote|pre|br|hr)\b[^>]*>/gi,
        ' '
      );
      return decode(spaced.replace(/<[^>]*>/g, ''));
    }
    if (typeof value === 'string') return value;
    const record = (value ?? {}) as Record<string, unknown>;
    return String(record.text ?? record.code ?? '');
  });
  return collapse(parts.join(' '));
}

function quoteMatches(quote: string, body: StreamFieldBlock[]): boolean {
  const text = collapse(collapse(quote).replace(/…$/, ''));
  return text !== '' && plainText(body).includes(text);
}

const blocks = (...list: unknown[]) => list as StreamFieldBlock[];
const para = (value: string) => ({ type: 'paragraph', value });

describe('postQuoteText follows the shared quote rule (audit F3)', () => {
  it.each<[string, StreamFieldBlock[]]>([
    ['marks', blocks(para('<p>Water <strong>week</strong>ly, <em>not</em> daily</p>'))],
    ['line breaks', blocks(para('<p>one<br>two<br><br>three</p>'))],
    [
      'paragraphs and headings',
      blocks({ type: 'heading', value: 'Care' }, para('<p>a</p><p>b</p>')),
    ],
    ['a list', blocks(para('<ul><li>one</li><li><p>two</p></li></ul><p>after</p>'))],
    ['a nested list', blocks(para('<ul><li>a<ul><li>b</li><li>c</li></ul></li><li>d</li></ul>'))],
    ['two paragraphs in a list item', blocks(para('<ol><li><p>one</p><p>two</p></li></ol>'))],
    ['loose inline text', blocks(para('plain <b>bold</b> tail'))],
    ['loose text around a block', blocks(para('before<p>inside</p>after'))],
    ['entities and no-break spaces', blocks(para('<p>5&nbsp;&lt;&nbsp;6 &amp; 7&#8230;</p>'))],
    ['text that ends in its own ellipsis', blocks(para('<p>well… maybe…</p>'))],
    [
      'a legacy quote',
      blocks(para('<p>a</p>'), { type: 'quote', value: 'x\ny\n\nz' }, para('<p>b</p>')),
    ],
    [
      'an image in the middle',
      blocks(para('<p>a</p>'), { type: 'image', value: { id: 1, url: '/x' } }, para('<p>b</p>')),
    ],
    [
      "another member's quote in the middle",
      blocks(
        para('<p>a</p>'),
        { type: 'post_quote', value: { text: 'third person', post_id: 3 } },
        para('<p>b</p>')
      ),
    ],
    [
      "another member's quote first",
      blocks({ type: 'post_quote', value: { text: 'third person', post_id: 3 } }, para('<p>b</p>')),
    ],
    [
      'code in the middle',
      blocks(para('<p>a</p>'), { type: 'code', value: { code: 'x = 1' } }, para('<p>b</p>')),
    ],
    ['a long post', blocks(para(`<p>${'word '.repeat(400)}</p>`))],
    ['an emoji at the cut', blocks(para(`<p>${'x'.repeat(QUOTE_TEXT_MAX_CHARS - 1)}🌱🌱🌱</p>`))],
  ])('%s, also after a round trip through the composer', (_name, body) => {
    const text = postQuoteText(body);
    expect(quoteMatches(text, body), `${JSON.stringify(text)} in ${plainText(body)}`).toBe(true);
    const [sent] = docToBodyBlocks({ type: 'doc', content: [postQuoteNode(7, text)!] });
    const sentText = (sent.value as { text: string }).text;
    expect(quoteMatches(sentText, body), JSON.stringify(sentText)).toBe(true);
    // No half of an emoji: a lone surrogate does not survive UTF-8.
    expect(new TextDecoder().decode(new TextEncoder().encode(sentText))).toBe(sentText);
  });

  it('never quotes the third person, and marks where it stopped', () => {
    const body = blocks(
      para('<p>a</p>'),
      { type: 'post_quote', value: { text: 'third person', post_id: 3 } },
      para('<p>b</p>')
    );
    expect(postQuoteText(body)).toBe('a…');
  });
});

describe('isBlankDoc needs no schema but keeps the serialised rule (audit F110)', () => {
  const p = (...content: JSONContent[]): JSONContent => ({ type: 'paragraph', content });
  const t = (text: string): JSONContent => ({ type: 'text', text });
  it.each<[string, JSONContent[]]>([
    ['empty paragraph', [{ type: 'paragraph' }]],
    ['spaces', [p(t('   '))]],
    ['no-break space', [p(t(' '))]],
    ['em space', [p(t(' '))]],
    ['hard break', [p({ type: 'hardBreak' })]],
    ['mention', [p({ type: 'mention', attrs: { id: 'ada', label: 'ada' } })]],
    ['image', [{ type: 'image', attrs: { src: '/x', imageId: '1' } }]],
    ['rule', [{ type: 'horizontalRule' }]],
    ['less-than', [p(t('<'))]],
    [
      'text in a list',
      [{ type: 'bulletList', content: [{ type: 'listItem', content: [p(t('x'))] }] }],
    ],
  ])('%s', (_name, content) => {
    const doc = { type: 'doc', content };
    expect(isBlankDoc(doc)).toBe(isBlankHtml(generateHTML(doc, FORUM_SCHEMA_EXTENSIONS)));
  });
});
