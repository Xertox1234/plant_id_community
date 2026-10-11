import { describe, expect, it } from 'vitest';
import type { StreamFieldBlock } from '@/types/blog';
import { embedDisplay, untitledEmbedOrdinals, type EmbedDisplay } from './embedDisplay';

// Todo 518: one derivation of a video card's name, read by its compact row
// and its full card. The mobile tests pin the first four labels below too
// (forum_card_runs_test.dart), so the two clients cannot drift unnoticed.

describe('embedDisplay (todo 518)', () => {
  const cases: [string, { url: string; title: string; provider_name: string }, EmbedDisplay][] = [
    [
      'a titled video: "title, provider"',
      { url: 'https://youtu.be/b', title: 'Bravo', provider_name: 'YouTube' },
      { title: 'Bravo', detail: 'YouTube', label: 'Bravo, YouTube' },
    ],
    [
      'a titled video with no provider: the title alone',
      { url: 'https://youtu.be/x', title: 'No provider', provider_name: '' },
      { title: 'No provider', detail: '', label: 'No provider' },
    ],
    [
      'an untitled video: its short address, never the full URL',
      { url: 'https://youtu.be/xyz?t=42', title: '', provider_name: 'YouTube' },
      { title: 'https://youtu.be/…', detail: 'YouTube', label: 'https://youtu.be/…, YouTube' },
    ],
    [
      'an untitled video with no provider: the short address alone',
      { url: 'https://vimeo.com/77', title: '', provider_name: '' },
      { title: 'https://vimeo.com/…', detail: '', label: 'https://vimeo.com/…' },
    ],
    [
      'an untitled video at a bare origin: the origin, with no "/…"',
      { url: 'https://vimeo.com/', title: '', provider_name: 'Vimeo' },
      { title: 'https://vimeo.com', detail: 'Vimeo', label: 'https://vimeo.com, Vimeo' },
    ],
    [
      // Never in a run (isCardBlock refuses it), so only a full card shows it.
      'an untitled video whose URL is not an http(s) link: the raw URL',
      { url: 'youtube.com/watch?v=x', title: '', provider_name: '' },
      { title: 'youtube.com/watch?v=x', detail: '', label: 'youtube.com/watch?v=x' },
    ],
  ];

  it.each(cases)('%s', (_name, value, expected) => {
    expect(embedDisplay(value)).toEqual(expected);
  });
});

// Todo 563 (owner decision 2026-10-11): untitled videos that would share a
// name in one post body each carry an ordinal. The mobile twin
// (forum_body_renderer_test.dart) pins the same names.
describe('untitled embed names are unique within one body (todo 563)', () => {
  const embed = (url: string, title = '', provider_name = 'YouTube'): StreamFieldBlock => ({
    type: 'embed',
    value: { url, title, provider_name, thumbnail_url: '', embed_url: null },
  });

  it('numbers only the untitled videos whose names collide, in body order', () => {
    const blocks: StreamFieldBlock[] = [
      embed('https://youtu.be/a'),
      { type: 'paragraph', value: '<p>and</p>' },
      embed('https://vimeo.com/1', '', 'Vimeo'),
      embed('https://youtu.be/b', 'Titled'),
      embed('https://youtu.be/c'),
    ];
    expect([...untitledEmbedOrdinals(blocks)]).toEqual([
      [0, 1],
      [4, 2],
    ]);
  });

  it('gives a lone untitled video no ordinal', () => {
    expect(
      untitledEmbedOrdinals([embed('https://youtu.be/a'), embed('https://vimeo.com/1')]).size
    ).toBe(0);
  });

  it('skips a video with no URL at all', () => {
    expect(untitledEmbedOrdinals([embed(''), embed('')]).size).toBe(0);
  });

  it('appends the ordinal to the short address, in the title and the label', () => {
    expect(
      embedDisplay({ url: 'https://youtu.be/b', title: '', provider_name: 'YouTube' }, 2)
    ).toEqual({
      title: 'https://youtu.be/… (2)',
      detail: 'YouTube',
      label: 'https://youtu.be/… (2), YouTube',
    });
  });

  it('never numbers a titled video', () => {
    expect(
      embedDisplay({ url: 'https://youtu.be/b', title: 'Bravo', provider_name: '' }, 2).title
    ).toBe('Bravo');
  });
});
