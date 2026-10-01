import { createElement } from 'react';
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import LinkPreviewCard from './LinkPreviewCard';
import { isCardBlock } from './cardRuns';
import { linkPreviewDisplay } from './linkPreviewDisplay';
import { API_URL } from '@/services/blogService';
import type { LinkPreviewBlockValue } from '@/types/blog';

// Todo 453: one derivation of a link card's display, shared by the full card,
// its compact row and the run rule.

const FULL_URL = 'https://example.org/guide/part-2?x=1';
const SHORT = 'https://example.org/…';

function preview(overrides: Partial<LinkPreviewBlockValue> = {}): LinkPreviewBlockValue {
  return {
    url: FULL_URL,
    title: 'Delta guide',
    description: 'How to',
    site_name: 'Example',
    domain: 'example.org',
    image_url: null,
    ...overrides,
  };
}

describe('linkPreviewDisplay (todo 453)', () => {
  it('derives the href, short address, title and "title, address" label', () => {
    expect(linkPreviewDisplay(preview())).toEqual({
      href: FULL_URL,
      address: SHORT,
      title: 'Delta guide',
      detail: SHORT,
      label: `Delta guide, ${SHORT}`,
      imageSrc: null,
    });
  });

  it('falls back to the site name, the domain, then the address', () => {
    expect(linkPreviewDisplay(preview({ title: '' }))?.title).toBe('Example');
    expect(linkPreviewDisplay(preview({ title: '', site_name: '' }))?.title).toBe('example.org');
    const bare = linkPreviewDisplay(preview({ title: '', site_name: '', domain: '' }));
    expect(bare?.title).toBe(SHORT);
    // The title IS the address: no second line, and the label says it once.
    expect(bare?.detail).toBe('');
    expect(bare?.label).toBe(SHORT);
  });

  it('is null for a missing envelope or a URL it will not link to', () => {
    expect(linkPreviewDisplay(null)).toBeNull();
    expect(linkPreviewDisplay(undefined)).toBeNull();
    for (const url of ['', 'javascript:alert(1)', 'example.org/x', 'https://u:p@example.org/']) {
      expect(linkPreviewDisplay(preview({ url }))).toBeNull();
    }
  });

  it('takes a post card image from our media, a composer image from https only', () => {
    const stored = '/media/forum/link-previews/' + 'a'.repeat(64) + '.webp';
    expect(linkPreviewDisplay(preview({ image_url: stored }), 'post')?.imageSrc).toBe(
      `${API_URL}${stored}`
    );
    expect(
      linkPreviewDisplay(preview({ image_url: 'https://cdn.example.org/og.png' }), 'composer')
        ?.imageSrc
    ).toBe('https://cdn.example.org/og.png');
    expect(
      linkPreviewDisplay(preview({ image_url: 'http://cdn.example.org/og.png' }), 'composer')
        ?.imageSrc
    ).toBeNull();
  });

  it('joins a run exactly when the full card renders something', () => {
    const cases: (LinkPreviewBlockValue | null)[] = [
      null,
      preview(),
      preview({ url: '' }),
      preview({ url: 'javascript:alert(1)' }),
      preview({ url: 'https://u:p@example.org/' }),
      preview({ url: 'example.org/guide' }),
      preview({ title: '', site_name: '', domain: '' }),
      preview({ url: 'http://example.org' }),
    ];
    for (const value of cases) {
      const renders = value
        ? render(createElement(LinkPreviewCard, { preview: value, variant: 'post' })).container
            .childElementCount > 0
        : false;
      expect(isCardBlock({ id: 'lp', type: 'link_preview', value })).toBe(renders);
      expect(linkPreviewDisplay(value) !== null).toBe(renders);
    }
  });
});
