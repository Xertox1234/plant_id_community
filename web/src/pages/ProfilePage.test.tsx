import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import ProfilePage from './ProfilePage';
import * as profileService from '../services/profileService';
import type { UserProfile } from '../types/auth';

const authState = vi.hoisted(() => ({
  user: { id: 7, email: 'ada@example.com', name: 'Ada' } as {
    id: number;
    email: string;
    name: string;
  },
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: authState.user }),
}));

vi.mock('../services/profileService', () => ({
  fetchProfile: vi.fn(),
  updateProfile: vi.fn(),
  fetchDashboardStats: vi.fn(),
}));

// The stats section links into the forum, so the page needs a router.
function renderPage() {
  return render(
    <MemoryRouter>
      <ProfilePage />
    </MemoryRouter>
  );
}

const profile: UserProfile = {
  id: 7,
  username: 'ada',
  email: 'ada@example.com',
  first_name: 'Ada',
  last_name: 'Lovelace',
  display_name: 'Ada Lovelace',
  bio: 'Ferns, mostly.',
  location: 'London',
  website: '',
};

describe('ProfilePage (web dead-code audit M3)', () => {
  beforeEach(() => {
    authState.user = { id: 7, email: 'ada@example.com', name: 'Ada' };
    vi.mocked(profileService.fetchProfile).mockReset().mockResolvedValue(profile);
    vi.mocked(profileService.updateProfile).mockReset();
    vi.mocked(profileService.fetchDashboardStats)
      .mockReset()
      .mockResolvedValue({
        forum_stats: { total_topics: 2, total_posts: 5, topics_this_month: 1, posts_this_month: 3 },
        recent_activity: [],
      });
  });

  it('loads the profile into an editable form, with email read-only', async () => {
    renderPage();

    expect(await screen.findByLabelText('First name')).toHaveValue('Ada');
    expect(screen.getByLabelText('Last name')).toHaveValue('Lovelace');
    expect(screen.getByLabelText('Bio')).toHaveValue('Ferns, mostly.');
    expect(screen.getByLabelText('Location')).toHaveValue('London');
    // Email is shown but is not an input: changing it needs re-verification.
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
    expect(screen.getAllByText('ada@example.com').length).toBeGreaterThan(0);
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
  });

  it('keeps Save disabled until something changes', async () => {
    renderPage();
    await screen.findByLabelText('First name');
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();

    await userEvent.type(screen.getByLabelText('Location'), ', UK');
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeEnabled();
  });

  it('sends only the changed fields and confirms the save', async () => {
    vi.mocked(profileService.updateProfile).mockResolvedValue({
      ...profile,
      bio: 'Ferns and mosses.',
    });
    renderPage();
    const bio = await screen.findByLabelText('Bio');

    await userEvent.clear(bio);
    await userEvent.type(bio, 'Ferns and mosses.');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() =>
      expect(profileService.updateProfile).toHaveBeenCalledWith({ bio: 'Ferns and mosses.' })
    );
    expect(await screen.findByText('Profile saved.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
  });

  it('shows the server error when a save is rejected', async () => {
    vi.mocked(profileService.updateProfile).mockRejectedValue(
      new Error('website: Enter a valid URL.')
    );
    renderPage();
    const website = await screen.findByLabelText('Website');

    await userEvent.type(website, 'not a url');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('website: Enter a valid URL.')).toBeInTheDocument();
  });

  it('shows an error instead of the form when the profile cannot load', async () => {
    vi.mocked(profileService.fetchProfile).mockRejectedValue(new Error('HTTP 500'));
    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 500');
    expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument();
  });

  it('shows the forum activity section below the form (todo 411)', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Forum activity' })).toBeInTheDocument();
    expect(await screen.findByText('Topics')).toBeInTheDocument();
    expect(screen.getByText('3 in the last 30 days')).toBeInTheDocument();
    expect(profileService.fetchDashboardStats).toHaveBeenCalledTimes(1);
  });

  it('keeps the form usable when only the stats fail to load', async () => {
    vi.mocked(profileService.fetchDashboardStats).mockRejectedValue(new Error('Stats down'));
    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent('Stats down');
    expect(await screen.findByLabelText('First name')).toHaveValue('Ada');
  });

  it('remounts the whole page when the signed-in account changes (PR #821)', async () => {
    const { rerender } = renderPage();
    expect(await screen.findByLabelText('First name')).toHaveValue('Ada');
    expect(profileService.fetchProfile).toHaveBeenCalledTimes(1);

    // A tab-focus identity check swaps the session to another account.
    authState.user = { id: 8, email: 'bea@example.com', name: 'Bea' };
    vi.mocked(profileService.fetchProfile).mockResolvedValue({
      ...profile,
      id: 8,
      first_name: 'Bea',
    });
    rerender(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByLabelText('First name')).toHaveValue('Bea'));
    expect(profileService.fetchProfile).toHaveBeenCalledTimes(2);
    expect(profileService.fetchDashboardStats).toHaveBeenCalledTimes(2);
  });
});
