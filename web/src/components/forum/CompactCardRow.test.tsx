import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import StreamFieldRenderer from '../StreamFieldRenderer';
import { CARD_BLOCK_TYPES, groupCardRuns, isCardBlock } from './cardRuns';
import type { StreamFieldBlock } from '@/types/blog';

// Todo 429: a run of 2+ consecutive cards renders the first as its full card
// and each later one as a compact row.

function embed(id: string, title: string, provider: string, player = true): StreamFieldBlock {
  return {
    id,
    type: 'embed',
    value: {
      url: `https://youtu.be/${id}`,
      title,
      provider_name: provider,
      thumbnail_url: `https://i.ytimg.com/${id}.jpg`,
      embed_url: player ? `https://www.youtube-nocookie.com/embed/${id}` : null,
    },
  };
}

const link: StreamFieldBlock = {
  id: 'lp',
  type: 'link_preview',
  value: {
    url: 'https://example.org/guide',
    title: 'Delta guide',
    description: 'How to',
    site_name: 'Example',
    domain: 'example.org',
    image_url: null,
  },
};

const paragraph: StreamFieldBlock = { id: 'p', type: 'paragraph', value: '<p>between</p>' };

const iframes = () => document.querySelectorAll('iframe');

describe('card runs', () => {
  it('renders 3 consecutive embeds as 1 full card + 2 compact rows', () => {
    render(
      <StreamFieldRenderer
        blocks={[
          embed('a', 'Alpha', 'YouTube'),
          embed('b', 'Bravo', 'YouTube'),
          embed('c', 'Charlie', 'Vimeo'),
        ]}
      />
    );

    // Only the first loads its player; the rows are named "title, site".
    expect(iframes()).toHaveLength(1);
    expect(iframes()[0].getAttribute('title')).toBe('Alpha');
    expect(screen.getByRole('button', { name: 'Bravo, YouTube' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Charlie, Vimeo' })).toBeInTheDocument();
  });

  it('renders a lone embed as today, with no row', () => {
    render(<StreamFieldRenderer blocks={[embed('a', 'Alpha', 'YouTube')]} />);

    expect(iframes()).toHaveLength(1);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('renders 2 embeds separated by a paragraph as 2 full cards', () => {
    render(
      <StreamFieldRenderer
        blocks={[embed('a', 'Alpha', 'YouTube'), paragraph, embed('b', 'Bravo', 'YouTube')]}
      />
    );

    expect(iframes()).toHaveLength(2);
    expect(screen.queryByRole('button', { name: 'Bravo, YouTube' })).toBeNull();
  });

  it('replaces a clicked video row with its sandboxed player', () => {
    render(
      <StreamFieldRenderer
        blocks={[embed('a', 'Alpha', 'YouTube'), embed('b', 'Bravo', 'YouTube')]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Bravo, YouTube' }));

    expect(screen.queryByRole('button', { name: 'Bravo, YouTube' })).toBeNull();
    const players = iframes();
    expect(players).toHaveLength(2);
    expect(players[1].getAttribute('src')).toBe('https://www.youtube-nocookie.com/embed/b');
    expect(players[1].getAttribute('sandbox')).toContain('allow-scripts');
  });

  it('makes each row a separately focusable element', () => {
    render(
      <StreamFieldRenderer
        blocks={[embed('a', 'Alpha', 'YouTube'), embed('b', 'Bravo', 'YouTube'), link]}
      />
    );

    const video = screen.getByRole('button', { name: 'Bravo, YouTube' });
    const card = screen.getByRole('link', { name: 'Delta guide, https://example.org/…' });
    expect(video).not.toBe(card);
    expect(card.getAttribute('href')).toBe('https://example.org/guide');
    expect(card.className).toContain('min-h-11');
    video.focus();
    expect(document.activeElement).toBe(video);
    card.focus();
    expect(document.activeElement).toBe(card);
  });

  it('moves focus to the player when a video row is activated', () => {
    render(
      <StreamFieldRenderer
        blocks={[embed('a', 'Alpha', 'YouTube'), embed('b', 'Bravo', 'YouTube')]}
      />
    );

    const row = screen.getByRole('button', { name: 'Bravo, YouTube' });
    row.focus();
    fireEvent.click(row);

    // Not dropped to <body>: the player's container, named like the row, has it.
    expect(document.activeElement).toBe(screen.getByRole('group', { name: 'Bravo, YouTube' }));
    expect(document.activeElement?.querySelector('iframe')).not.toBeNull();
  });

  it("names a link row by its real address, never the page's own site name", () => {
    const spoof: StreamFieldBlock = {
      id: 'spoof',
      type: 'link_preview',
      value: {
        url: 'https://evil.example/watch',
        title: 'Watch this',
        description: '',
        site_name: 'YouTube',
        domain: 'evil.example',
        image_url: null,
      },
    };
    render(<StreamFieldRenderer blocks={[embed('a', 'Alpha', 'YouTube'), spoof]} />);

    const row = screen.getByRole('link', { name: 'Watch this, https://evil.example/…' });
    expect(row).toHaveTextContent('https://evil.example/…');
    expect(row).not.toHaveTextContent('YouTube');
  });

  it('keeps an embed whose URL is unusable out of a run', () => {
    const bad = embed('b', 'Bravo', 'YouTube');
    if (bad.type === 'embed') bad.value.url = 'youtube.com/watch?v=x';
    expect(isCardBlock(bad)).toBe(false);
    expect(groupCardRuns([embed('a', 'A', 'YouTube'), bad]).map((item) => item.kind)).toEqual([
      'block',
      'block',
    ]);
  });

  it('makes a video row with no player a link, like its full card', () => {
    render(
      <StreamFieldRenderer
        blocks={[embed('a', 'Alpha', 'YouTube'), embed('b', 'Bravo', 'Vimeo', false)]}
      />
    );

    expect(screen.getByRole('link', { name: 'Bravo, Vimeo' }).getAttribute('href')).toBe(
      'https://youtu.be/b'
    );
  });

  // Todo 505: an untitled video row says its short address, never the full
  // URL a screen reader would spell out character by character.
  it('titles an untitled video row by its short address', () => {
    const untitled = embed('b', '', 'YouTube');
    if (untitled.type === 'embed') untitled.value.url = 'https://youtu.be/xyz?t=42';
    render(<StreamFieldRenderer blocks={[embed('a', 'Alpha', 'YouTube'), untitled]} />);

    const row = screen.getByRole('button', { name: 'https://youtu.be/…, YouTube' });
    expect(row).toHaveTextContent('https://youtu.be/…');
    expect(row).not.toHaveTextContent('xyz');
  });

  // Todo 518, finding 4: with no provider either, the row is named by its
  // short address alone, as the mobile row is (forum_card_runs_test.dart).
  it('names an untitled video row with no provider by its short address alone', () => {
    const bare = embed('c', '', '');
    if (bare.type === 'embed') bare.value.url = 'https://vimeo.com/77';
    render(<StreamFieldRenderer blocks={[embed('a', 'Alpha', 'YouTube'), bare]} />);

    const row = screen.getByRole('button', { name: 'https://vimeo.com/…' });
    expect(row).toHaveTextContent('https://vimeo.com/…');
    expect(row).not.toHaveTextContent('/77');
  });

  // Todo 518, finding 1 (owner decision 2026-10-02): an untitled video's full
  // card uses its short address too, so the same video is named one way
  // wherever it falls in a run.
  it('names an untitled video by its short address as a full card and as a row', () => {
    const untitled = (id: string) => {
      const block = embed(id, '', 'YouTube');
      if (block.type === 'embed') block.value.url = `https://youtu.be/${id}?t=42`;
      return block;
    };
    render(<StreamFieldRenderer blocks={[untitled('a'), untitled('b')]} />);

    expect(iframes()[0].getAttribute('title')).toBe('https://youtu.be/…');
    expect(screen.getByRole('button', { name: 'https://youtu.be/…, YouTube' })).toBeInTheDocument();
  });

  it('keeps a null link card out of a run (it renders nothing)', () => {
    const blank: StreamFieldBlock = { id: 'x', type: 'link_preview', value: null };
    expect(isCardBlock(blank)).toBe(false);
    const items = groupCardRuns([embed('a', 'A', 'YouTube'), blank, embed('b', 'B', 'YouTube')]);
    expect(items.map((item) => item.kind)).toEqual(['block', 'block', 'block']);
  });

  it('keeps each block on its own anchor inside a run', () => {
    render(
      <StreamFieldRenderer
        anchorPrefix="block"
        blocks={[paragraph, embed('a', 'Alpha', 'YouTube'), embed('b', 'Bravo', 'YouTube'), link]}
      />
    );

    expect(document.getElementById('block-1')?.querySelector('iframe')?.title).toBe('Alpha');
    expect(document.getElementById('block-2')).toContainElement(
      screen.getByRole('button', { name: 'Bravo, YouTube' })
    );
    expect(document.getElementById('block-3')).toContainElement(
      screen.getByRole('link', { name: 'Delta guide, https://example.org/…' })
    );
  });

  it('describes a link row as opening in a new tab, like the full card', () => {
    render(<StreamFieldRenderer blocks={[embed('a', 'Alpha', 'YouTube'), link]} />);

    expect(
      screen.getByRole('link', { name: 'Delta guide, https://example.org/…' })
    ).toHaveAccessibleDescription('Opens in a new tab');
  });

  it('keeps the card-type set in one constant', () => {
    expect([...CARD_BLOCK_TYPES].sort()).toEqual(['embed', 'link_preview']);
  });
});
