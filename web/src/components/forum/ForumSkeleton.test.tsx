import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import {
  CategoryListSkeleton,
  SearchResultsSkeleton,
  ThreadDetailSkeleton,
  ThreadListSkeleton,
  UserProfileSkeleton,
} from './ForumSkeleton';

const PAGES: Array<[string, () => ReactElement]> = [
  ['CategoryListSkeleton', () => <CategoryListSkeleton />],
  ['ThreadListSkeleton', () => <ThreadListSkeleton withHeader />],
  ['ThreadDetailSkeleton', () => <ThreadDetailSkeleton />],
  ['SearchResultsSkeleton', () => <SearchResultsSkeleton />],
  ['UserProfileSkeleton', () => <UserProfileSkeleton />],
];

describe('ForumSkeleton', () => {
  // The page tests query getByRole('status') while loading — that throws on
  // zero OR multiple matches, so every composition must expose exactly one.
  it.each(PAGES)('%s exposes exactly one polite status root with sr-only text', (_name, make) => {
    render(make());
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(status).toHaveTextContent(/Loading/);
  });

  it.each(PAGES)('%s hides every pulse block from assistive tech', (_name, make) => {
    const { container } = render(make());
    const blocks = container.querySelectorAll('.bg-surface-3');
    expect(blocks.length).toBeGreaterThan(0);
    blocks.forEach((block) => {
      expect(block.closest('[aria-hidden="true"]')).not.toBeNull();
    });
  });

  it('never renders a heading — the e2e overflow check gates on the loaded h1', () => {
    for (const [, make] of PAGES) {
      const { container, unmount } = render(make());
      expect(container.querySelector('h1, h2, h3')).toBeNull();
      unmount();
    }
  });

  it('ThreadListSkeleton adds the board chrome only with withHeader, keeping five rows', () => {
    const { container: bare, unmount } = render(<ThreadListSkeleton />);
    const bareBlocks = bare.querySelectorAll('.bg-surface-3').length;
    expect(bare.querySelectorAll('.canopy-card')).toHaveLength(5);
    unmount();

    const { container: full } = render(<ThreadListSkeleton withHeader />);
    expect(full.querySelectorAll('.bg-surface-3').length).toBeGreaterThan(bareBlocks);
    expect(full.querySelectorAll('.canopy-card')).toHaveLength(5);
  });

  it('UserProfileSkeleton keeps the "Loading profile" wording the page used before', () => {
    render(<UserProfileSkeleton />);
    const status = screen.getByRole('status', { name: 'Loading profile…' });
    expect(status).toHaveTextContent('Loading profile…');
  });
});
