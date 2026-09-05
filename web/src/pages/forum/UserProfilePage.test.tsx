import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import UserProfilePage from './UserProfilePage';
import * as forumService from '../../services/forumService';
import { useAuth } from '../../contexts/AuthContext';
import type { ForumUserProfile } from '../../types/forum';

vi.mock('../../services/forumService');
vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));
const announceMock = vi.hoisted(() => vi.fn());
vi.mock('../../contexts/AnnouncerContext', () => ({ useAnnounce: () => announceMock }));

const mockAuth = (isAuthenticated: boolean) =>
  ({ isAuthenticated }) as unknown as ReturnType<typeof useAuth>;

function renderProfile(username = 'ada') {
  return render(
    <MemoryRouter initialEntries={[`/forum/users/${username}`]}>
      <Routes>
        <Route path="/forum/users/:username" element={<UserProfilePage />} />
      </Routes>
    </MemoryRouter>
  );
}

const mockProfile: ForumUserProfile = {
  username: 'ada',
  display_name: 'Ada L.',
  avatar: null,
  trust_level: 3,
  bio: 'I like ferns.',
  signature: '',
  post_count: 42,
  joined_at: new Date('2026-01-01T00:00:00Z').toISOString(),
  recent_topics: [
    {
      id: 5,
      slug: 'fern-care',
      title: 'Fern care',
      board_id: 1,
      board_slug: 'general',
      reply_count: 2,
      created_at: new Date('2026-07-01T00:00:00Z').toISOString(),
    },
  ],
  recent_posts: [
    {
      id: 9,
      topic_id: 6,
      topic_slug: 'watering',
      topic_title: 'Watering thread',
      board_id: 1,
      board_slug: 'general',
      created_at: new Date('2026-07-02T00:00:00Z').toISOString(),
    },
  ],
};

describe('UserProfilePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default to authenticated so the block button renders; individual tests
    // override where the logged-out/own-profile case matters.
    vi.mocked(useAuth).mockReturnValue(mockAuth(true));
  });

  it('renders identity, trust badge, bio, and recent-activity links', async () => {
    vi.spyOn(forumService, 'fetchUserProfile').mockResolvedValue(mockProfile);

    renderProfile('ada');

    expect(await screen.findByRole('heading', { name: 'Ada L.' })).toBeInTheDocument();
    expect(screen.getByText('Regular')).toBeInTheDocument(); // trust_level 3
    expect(screen.getByText('I like ferns.')).toBeInTheDocument();
    expect(screen.getByText(/42\s+posts/)).toBeInTheDocument();

    // Recent topic links to the thread; recent reply links to the post anchor.
    expect(screen.getByRole('link', { name: 'Fern care' })).toHaveAttribute(
      'href',
      '/forum/1-general/5-fern-care'
    );
    expect(screen.getByRole('link', { name: 'Watering thread' })).toHaveAttribute(
      'href',
      '/forum/1-general/6-watering#post-9'
    );

    // Fetched by the :username route param.
    expect(forumService.fetchUserProfile).toHaveBeenCalledWith('ada');
  });

  it('shows an error state when the profile is not found', async () => {
    vi.spyOn(forumService, 'fetchUserProfile').mockRejectedValue(new Error('Profile not found'));

    renderProfile('ghost');

    expect(await screen.findByText('Profile not found')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to the forum/i })).toBeInTheDocument();
  });

  it('hides the block button when can_block is false (own profile, backend authority)', async () => {
    vi.spyOn(forumService, 'fetchUserProfile').mockResolvedValue({
      ...mockProfile,
      can_block: false,
    });

    renderProfile('ada');

    await screen.findByRole('heading', { name: 'Ada L.' });
    expect(screen.queryByRole('button', { name: /block/i })).not.toBeInTheDocument();
  });

  it('hides the block button for an anonymous viewer even when can_block is true', async () => {
    vi.mocked(useAuth).mockReturnValue(mockAuth(false));
    vi.spyOn(forumService, 'fetchUserProfile').mockResolvedValue({
      ...mockProfile,
      can_block: true,
    });

    renderProfile('ada');

    await screen.findByRole('heading', { name: 'Ada L.' });
    expect(screen.queryByRole('button', { name: /block/i })).not.toBeInTheDocument();
  });

  it('blocks a user optimistically, then refetches to match the real backend contract', async () => {
    // PublicProfileView skips recent_topics/recent_posts entirely and
    // returns [] once blocked (see the backend's Work Log) — the refetch
    // after a successful block must bring the client in line with that,
    // not just flip the flag and leave stale pre-block activity in place.
    vi.spyOn(forumService, 'fetchUserProfile')
      .mockResolvedValueOnce({ ...mockProfile, can_block: true, is_blocked: false })
      .mockResolvedValueOnce({
        ...mockProfile,
        can_block: true,
        is_blocked: true,
        recent_topics: [],
        recent_posts: [],
      });
    vi.spyOn(forumService, 'blockUser').mockResolvedValue(undefined);

    renderProfile('ada');

    const blockBtn = await screen.findByRole('button', { name: /^block$/i });
    await userEvent.click(blockBtn);

    // Optimistic — flips to "Unblock" before the request resolves.
    expect(await screen.findByRole('button', { name: /^unblock$/i })).toBeInTheDocument();
    expect(forumService.blockUser).toHaveBeenCalledWith('ada');

    // Refetched: the notice is truthful (activity hidden, not "shown
    // below"), and the stale pre-block topic/reply no longer render.
    expect(
      await screen.findByText("You've blocked this member — their recent activity is hidden.")
    ).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Fern care' })).not.toBeInTheDocument();
    expect(screen.getByText('No topics yet.')).toBeInTheDocument();
    expect(screen.getByText('No replies yet.')).toBeInTheDocument();
    expect(forumService.fetchUserProfile).toHaveBeenCalledTimes(2);
  });

  it('announces the block failure for screen readers (audit M4)', async () => {
    vi.spyOn(forumService, 'fetchUserProfile').mockResolvedValue({
      ...mockProfile,
      can_block: true,
      is_blocked: false,
    });
    vi.spyOn(forumService, 'blockUser').mockRejectedValue(new Error('Failed to block user'));

    renderProfile('ada');
    await userEvent.click(await screen.findByRole('button', { name: /^block$/i }));

    await screen.findByText('Failed to block user');
    expect(announceMock).toHaveBeenCalledWith('Failed to block user', 'assertive');
  });

  it('rolls back and shows an error when blocking fails', async () => {
    vi.spyOn(forumService, 'fetchUserProfile').mockResolvedValue({
      ...mockProfile,
      can_block: true,
      is_blocked: false,
    });
    vi.spyOn(forumService, 'blockUser').mockRejectedValue(new Error('Failed to block user'));

    renderProfile('ada');

    const blockBtn = await screen.findByRole('button', { name: /^block$/i });
    await userEvent.click(blockBtn);

    // Rolled back to "Block" and the failure is surfaced.
    expect(await screen.findByText('Failed to block user')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^block$/i })).toBeInTheDocument();
  });

  it('unblocks a user optimistically, then refetches to restore real activity', async () => {
    // While blocked the client only ever saw [], so unblocking needs a real
    // refetch — a client-side "restore" has no real data to restore from.
    vi.spyOn(forumService, 'fetchUserProfile')
      .mockResolvedValueOnce({
        ...mockProfile,
        can_block: true,
        is_blocked: true,
        recent_topics: [],
        recent_posts: [],
      })
      .mockResolvedValueOnce({ ...mockProfile, can_block: true, is_blocked: false });
    vi.spyOn(forumService, 'unblockUser').mockResolvedValue(undefined);

    renderProfile('ada');

    const unblockBtn = await screen.findByRole('button', { name: /^unblock$/i });
    await userEvent.click(unblockBtn);

    expect(await screen.findByRole('button', { name: /^block$/i })).toBeInTheDocument();
    expect(forumService.unblockUser).toHaveBeenCalledWith('ada');

    // Real activity is back and the blocked notice is gone.
    expect(await screen.findByRole('link', { name: 'Fern care' })).toBeInTheDocument();
    expect(
      screen.queryByText("You've blocked this member — their recent activity is hidden.")
    ).not.toBeInTheDocument();
  });
});
