import { createElement } from 'react';
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import LinkPreviewCard from './LinkPreviewCard';
import { isCardBlock } from './cardRuns';
import { linkPreviewDisplay } from './linkPreviewDisplay';
import { API_ORIGIN } from '@/config/api';
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
    expect(linkPreviewDisplay(preview(), 'post')).toEqual({
      href: FULL_URL,
      address: SHORT,
      title: 'Delta guide',
      detail: SHORT,
      label: `Delta guide, ${SHORT}`,
      imageSrc: null,
    });
  });

  it('falls back to the site name, the domain, then the address', () => {
    expect(linkPreviewDisplay(preview({ title: '' }), 'post')?.title).toBe('Example');
    expect(linkPreviewDisplay(preview({ title: '', site_name: '' }), 'post')?.title).toBe(
      'example.org'
    );
    const bare = linkPreviewDisplay(preview({ title: '', site_name: '', domain: '' }), 'post');
    expect(bare?.title).toBe(SHORT);
    // The title IS the address: no second line, and the label says it once.
    expect(bare?.detail).toBe('');
    expect(bare?.label).toBe(SHORT);
  });

  it('is null for a missing envelope or a URL it will not link to', () => {
    for (const variant of ['post', 'composer'] as const) {
      expect(linkPreviewDisplay(null, variant)).toBeNull();
      expect(linkPreviewDisplay(undefined, variant)).toBeNull();
      for (const url of ['', 'javascript:alert(1)', 'example.org/x', 'https://u:p@example.org/']) {
        expect(linkPreviewDisplay(preview({ url }), variant)).toBeNull();
      }
    }
  });

  it('takes a post card image from our media, a composer image from https only', () => {
    const stored = '/media/forum/link-previews/' + 'a'.repeat(64) + '.webp';
    expect(linkPreviewDisplay(preview({ image_url: stored }), 'post')?.imageSrc).toBe(
      `${API_ORIGIN}${stored}`
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

  // Todo 505: the nearest neighbours each image source must refuse.
  it('refuses a script or data image on a post card', () => {
    for (const image_url of ['javascript:alert(1)', 'data:image/png;base64,AAAA', 'og.png']) {
      expect(linkPreviewDisplay(preview({ image_url }), 'post')?.imageSrc).toBeNull();
    }
  });

  it('passes an absolute post image through unchanged (an R2 media URL)', () => {
    // With USE_R2 the stored image is an absolute URL on the media domain,
    // with no /media/ path, so mediaUrl passes it through; a post card does
    // not insist on https because local media is served over http.
    const r2 = 'https://media.example.org/forum/link-previews/abc.webp';
    expect(linkPreviewDisplay(preview({ image_url: r2 }), 'post')?.imageSrc).toBe(r2);
  });

  it('never resolves a composer image through our media', () => {
    // A relative /media/ path is OUR copy, which only a stored post card has:
    // the composer shows the linked site's own https image or nothing.
    const stored = '/media/forum/link-previews/' + 'a'.repeat(64) + '.webp';
    expect(linkPreviewDisplay(preview({ image_url: stored }), 'composer')?.imageSrc).toBeNull();
    expect(
      linkPreviewDisplay(preview({ image_url: 'javascript:alert(1)' }), 'composer')?.imageSrc
    ).toBeNull();
  });

  it('makes every caller name its image source', () => {
    // Todo 505: no default, so leaving the variant out is a type error rather
    // than a silent choice of image source. Vitest does not typecheck, so tsc
    // is what enforces this (todo 518): tsconfig.json includes src/**/*, test
    // files too, and web-ci runs `npm run type-check` (tsc --noEmit). With an
    // optional variant the directive goes unused, and tsc fails (TS2578).
    // @ts-expect-error variant is required
    expect(linkPreviewDisplay(preview())).not.toBeNull();
  });

  // Each case states whether the card SHOULD render (todo 505). The parity
  // checks below cannot fail on their own if linkPreviewDisplay's null rule is
  // wrong, since the card, isCardBlock and the run all read that one
  // function; they only catch a call site that stops using it. The explicit
  // `expected` is what pins the rule itself.
  const parityCases: [string, LinkPreviewBlockValue | null, boolean][] = [
    ['no envelope', null, false],
    ['an https link', preview(), true],
    ['an http link', preview({ url: 'http://example.org' }), true],
    ['an untitled link', preview({ title: '', site_name: '', domain: '' }), true],
    ['an empty URL', preview({ url: '' }), false],
    ['a javascript: URL', preview({ url: 'javascript:alert(1)' }), false],
    ['a URL with credentials', preview({ url: 'https://u:p@example.org/' }), false],
    ['a schemeless URL', preview({ url: 'example.org/guide' }), false],
  ];

  it.each(parityCases)(
    'joins a run exactly when the full card renders: %s',
    (_name, value, expected) => {
      for (const variant of ['post', 'composer'] as const) {
        const renders = value
          ? render(createElement(LinkPreviewCard, { preview: value, variant })).container
              .childElementCount > 0
          : false;
        expect(renders).toBe(expected);
        expect(linkPreviewDisplay(value, variant) !== null).toBe(expected);
      }
      expect(isCardBlock({ id: 'lp', type: 'link_preview', value })).toBe(expected);
    }
  );
});
