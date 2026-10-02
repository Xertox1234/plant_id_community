import { describe, expect, it } from 'vitest';
import { embedDisplay, type EmbedDisplay } from './embedDisplay';

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
