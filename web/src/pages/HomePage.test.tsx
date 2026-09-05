// web/src/pages/HomePage.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import HomePage from './HomePage';
import { useAuth } from '../contexts/AuthContext';
import * as forumService from '../services/forumService';
import type { ForumMyStats, RecentTopic } from '../types/forum';

vi.mock('../contexts/AuthContext', () => ({ useAuth: vi.fn() }));

// HomeActivity's two feeds (todo 315). Mocked here rather than stubbing the
// component out, so the "logged-out Home issues no extra requests" assertion
// below is checking the real wiring.
vi.mock('../services/forumService');

vi.mock('../utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));

const mockAuth = (isAuthenticated: boolean, { id = 1, isLoading = false } = {}) =>
  ({
    user: isAuthenticated ? { id } : null,
    isAuthenticated,
    isLoading,
  }) as unknown as ReturnType<typeof useAuth>;

const myStats: ForumMyStats = {
  posts: 12,
  solutions_accepted: 3,
  identifications_shared: 7,
  streak_days: 4,
  badge_name: 'Botanist',
  badge_progress: 7,
  badge_target: 20,
  badges: [],
};

const recentTopic: RecentTopic = {
  id: 42,
  slug: 'monstera-leaf-curl',
  title: 'Monstera leaf curl',
  board: { id: 7, name: 'Care & problems', slug: 'care-problems' },
  reply_count: 3,
  last_post_at: '2026-09-01T10:00:00Z',
  is_pinned: false,
  thumbnail_url: null,
};

const renderHome = () =>
  render(
    <BrowserRouter>
      <HomePage />
    </BrowserRouter>
  );

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue(mockAuth(false));
    vi.mocked(forumService.fetchMyStats).mockResolvedValue(myStats);
    vi.mocked(forumService.fetchRecentTopics).mockResolvedValue([recentTopic]);
  });

  it('renders the hero headline and CTA links, not a GrainOverlay or ClayButton', () => {
    renderHome();
    expect(
      screen.getByRole('heading', { level: 2, name: /discover the world of plants/i })
    ).toBeInTheDocument();
    expect(screen.queryByTestId('grain-overlay')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Home' })).toHaveClass('sr-only');

    const getStarted = screen.getByRole('link', { name: /get started/i });
    expect(getStarted).toHaveAttribute('href', '/identify');
    const joinCommunity = screen.getByRole('link', { name: /join community/i });
    expect(joinCommunity).toHaveAttribute('href', '/forum');
  });

  it('renders the three feature cards as links to their pages', () => {
    renderHome();

    expect(screen.getByRole('link', { name: /ai plant identification/i })).toHaveAttribute(
      'href',
      '/identify'
    );
    expect(screen.getByRole('link', { name: /discussion forum/i })).toHaveAttribute(
      'href',
      '/forum'
    );
    expect(screen.getByRole('link', { name: /plant blog/i })).toHaveAttribute('href', '/blog');
  });

  describe('activity feed (todo 315)', () => {
    it('shows the logged-in activity feed for an authenticated visitor', async () => {
      vi.mocked(useAuth).mockReturnValue(mockAuth(true));
      renderHome();

      expect(await screen.findByRole('heading', { name: 'Your season' })).toBeInTheDocument();
      expect(await screen.findByRole('heading', { name: 'Active now' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /monstera leaf curl/i })).toBeInTheDocument();
      // The evergreen marketing row stays for members too.
      expect(screen.getByRole('link', { name: /ai plant identification/i })).toBeInTheDocument();
    });

    it('renders no activity feed and issues no requests for an anonymous visitor', async () => {
      renderHome();

      // Give any errant effect a tick to fire before asserting the negative.
      await waitFor(() =>
        expect(screen.getByRole('heading', { level: 1, name: 'Home' })).toBeInTheDocument()
      );
      expect(screen.queryByRole('heading', { name: 'Your season' })).not.toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: 'Active now' })).not.toBeInTheDocument();
      // AC2: logged-out Home is unchanged from Canopy PR 4 — not merely
      // visually, but down to making zero extra network calls.
      expect(forumService.fetchMyStats).not.toHaveBeenCalled();
      expect(forumService.fetchRecentTopics).not.toHaveBeenCalled();
    });

    // Review finding 2. AuthProvider.initAuth seeds `user` from
    // getStoredUser() (sessionStorage) BEFORE getCurrentUser() verifies with
    // the backend, so `isAuthenticated` is briefly true for a visitor whose
    // session has already expired. Gating on `isAuthenticated` alone would
    // fire both requests and flash the previous session's stats.
    it('issues no requests while auth is still being verified', async () => {
      vi.mocked(useAuth).mockReturnValue(mockAuth(true, { isLoading: true }));
      renderHome();

      await waitFor(() =>
        expect(screen.getByRole('heading', { level: 1, name: 'Home' })).toBeInTheDocument()
      );
      expect(screen.queryByRole('heading', { name: 'Your season' })).not.toBeInTheDocument();
      expect(forumService.fetchMyStats).not.toHaveBeenCalled();
      expect(forumService.fetchRecentTopics).not.toHaveBeenCalled();
    });

    // Review finding 1. `isAuthenticated` is `!!user`, so it stays true across
    // an identity change (revalidateIdentity swaps the user on tab focus,
    // todo 297). Without `key={user?.id}` React reuses the HomeActivity
    // instance and its mount-once effect never refetches — the header would
    // show account B while "Your season" still showed account A's numbers.
    it('refetches when the identity changes underneath a still-authenticated session', async () => {
      vi.mocked(useAuth).mockReturnValue(mockAuth(true, { id: 1 }));
      const { rerender } = renderHome();
      await screen.findByRole('heading', { name: 'Your season' });
      expect(forumService.fetchMyStats).toHaveBeenCalledTimes(1);

      // Same session, different account — exactly what tab-focus
      // revalidation produces.
      vi.mocked(useAuth).mockReturnValue(mockAuth(true, { id: 2 }));
      rerender(
        <BrowserRouter>
          <HomePage />
        </BrowserRouter>
      );

      await waitFor(() => expect(forumService.fetchMyStats).toHaveBeenCalledTimes(2));
      expect(forumService.fetchRecentTopics).toHaveBeenCalledTimes(2);
    });
  });
});
