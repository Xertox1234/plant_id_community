import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import UserProfilePage from './UserProfilePage';
import * as forumService from '../../services/forumService';
import type { ForumUserProfile } from '../../types/forum';

vi.mock('../../services/forumService');

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
  beforeEach(() => vi.clearAllMocks());

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
});
