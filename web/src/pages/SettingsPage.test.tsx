// web/src/pages/SettingsPage.test.tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '../contexts/ThemeContext';
import SettingsPage from './SettingsPage';
import * as forumService from '../services/forumService';

vi.mock('../services/forumService');

const renderPage = () =>
  render(
    <ThemeProvider>
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    </ThemeProvider>
  );

describe('SettingsPage theme controls', () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.density;
    delete document.documentElement.dataset.mode;
    // Default: no blocked/muted users, so the theme-control tests below (which
    // don't care about those sections) don't hang on an unresolved
    // auto-mocked promise.
    vi.mocked(forumService.fetchBlockedUsers).mockResolvedValue([]);
    vi.mocked(forumService.fetchMutedUsers).mockResolvedValue([]);
  });

  it('renders no palette controls', () => {
    renderPage();
    expect(screen.queryByRole('button', { name: /loam/i })).toBeNull();
  });

  it('changing density applies it to <html>', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /compact/i }));
    expect(document.documentElement).toHaveAttribute('data-density', 'compact');
  });

  it('dark toggle flips mode on <html>', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /light/i }));
    expect(document.documentElement).toHaveAttribute('data-mode', 'light');
  });
});

describe('SettingsPage blocked users (todo 284/M9)', () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.density;
    delete document.documentElement.dataset.mode;
    vi.mocked(forumService.fetchMutedUsers).mockResolvedValue([]);
  });

  it('shows an empty state when the caller has blocked no one', async () => {
    vi.mocked(forumService.fetchBlockedUsers).mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText("You haven't blocked anyone.")).toBeInTheDocument();
  });

  it('lists blocked users, most recently blocked first (server order preserved)', async () => {
    vi.mocked(forumService.fetchBlockedUsers).mockResolvedValue([
      {
        username: 'noisy-neighbor',
        display_name: 'Noisy Neighbor',
        avatar: null,
        trust_level: 1,
        title: '',
        blocked_at: new Date('2026-08-01T00:00:00Z').toISOString(),
      },
      {
        username: 'spammer',
        display_name: '',
        avatar: null,
        trust_level: null,
        title: '',
        blocked_at: new Date('2026-07-01T00:00:00Z').toISOString(),
      },
    ]);

    renderPage();

    expect(await screen.findByText('Noisy Neighbor')).toBeInTheDocument();
    // Falls back to username when display_name is empty.
    expect(screen.getByText('spammer')).toBeInTheDocument();
  });

  it('removes a row from the list when Unblock succeeds, without a refetch', async () => {
    vi.mocked(forumService.fetchBlockedUsers).mockResolvedValue([
      {
        username: 'noisy-neighbor',
        display_name: 'Noisy Neighbor',
        avatar: null,
        trust_level: 1,
        title: '',
        blocked_at: new Date('2026-08-01T00:00:00Z').toISOString(),
      },
    ]);
    vi.mocked(forumService.unblockUser).mockResolvedValue(undefined);

    renderPage();

    await screen.findByText('Noisy Neighbor');
    await userEvent.click(screen.getByRole('button', { name: /unblock/i }));

    expect(forumService.unblockUser).toHaveBeenCalledWith('noisy-neighbor');
    expect(await screen.findByText("You haven't blocked anyone.")).toBeInTheDocument();
    // Only the initial mount call — removal is local, not a refetch.
    expect(forumService.fetchBlockedUsers).toHaveBeenCalledTimes(1);
  });

  it('surfaces an error and keeps the row when Unblock fails', async () => {
    vi.mocked(forumService.fetchBlockedUsers).mockResolvedValue([
      {
        username: 'noisy-neighbor',
        display_name: 'Noisy Neighbor',
        avatar: null,
        trust_level: 1,
        title: '',
        blocked_at: new Date('2026-08-01T00:00:00Z').toISOString(),
      },
    ]);
    vi.mocked(forumService.unblockUser).mockRejectedValue(new Error('Failed to unblock user'));

    renderPage();

    await screen.findByText('Noisy Neighbor');
    await userEvent.click(screen.getByRole('button', { name: /unblock/i }));

    expect(await screen.findByText('Failed to unblock user')).toBeInTheDocument();
    expect(screen.getByText('Noisy Neighbor')).toBeInTheDocument();
  });
});

describe('SettingsPage muted users (todo 347)', () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.density;
    delete document.documentElement.dataset.mode;
    vi.mocked(forumService.fetchBlockedUsers).mockResolvedValue([]);
  });

  it('shows an empty state and explains that a mute is one-way', async () => {
    vi.mocked(forumService.fetchMutedUsers).mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText("You haven't muted anyone.")).toBeInTheDocument();
    expect(
      screen.getByText(/hides a member's posts and notifications from you only/i)
    ).toBeInTheDocument();
  });

  it('lists muted users in server order and removes a row when Unmute succeeds, without a refetch', async () => {
    vi.mocked(forumService.fetchMutedUsers).mockResolvedValue([
      {
        username: 'chatty',
        display_name: 'Chatty Cathy',
        avatar: null,
        trust_level: 2,
        title: '',
        muted_at: new Date('2026-08-01T00:00:00Z').toISOString(),
      },
      {
        username: 'loud',
        display_name: '',
        avatar: null,
        trust_level: null,
        title: '',
        muted_at: new Date('2026-07-01T00:00:00Z').toISOString(),
      },
    ]);
    vi.mocked(forumService.unmuteUser).mockResolvedValue(undefined);

    renderPage();

    expect(await screen.findByText('Chatty Cathy')).toBeInTheDocument();
    expect(screen.getByText('loud')).toBeInTheDocument(); // username fallback
    await userEvent.click(screen.getAllByRole('button', { name: /unmute/i })[0]);

    expect(forumService.unmuteUser).toHaveBeenCalledWith('chatty');
    await waitFor(() => expect(screen.queryByText('Chatty Cathy')).not.toBeInTheDocument());
    expect(screen.getByText('loud')).toBeInTheDocument();
    expect(forumService.fetchMutedUsers).toHaveBeenCalledTimes(1);
  });

  it('surfaces an error and keeps the row when Unmute fails', async () => {
    vi.mocked(forumService.fetchMutedUsers).mockResolvedValue([
      {
        username: 'chatty',
        display_name: 'Chatty Cathy',
        avatar: null,
        trust_level: 2,
        title: '',
        muted_at: new Date('2026-08-01T00:00:00Z').toISOString(),
      },
    ]);
    vi.mocked(forumService.unmuteUser).mockRejectedValue(new Error('Failed to unmute user'));

    renderPage();

    await screen.findByText('Chatty Cathy');
    await userEvent.click(screen.getByRole('button', { name: /unmute/i }));

    expect(await screen.findByText('Failed to unmute user')).toBeInTheDocument();
    expect(screen.getByText('Chatty Cathy')).toBeInTheDocument();
  });
});
