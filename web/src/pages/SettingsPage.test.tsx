// web/src/pages/SettingsPage.test.tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
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
    // Default: no blocked users, so the theme-control tests below (which
    // don't care about the blocked-users section) don't hang on an
    // unresolved auto-mocked promise.
    vi.mocked(forumService.fetchBlockedUsers).mockResolvedValue([]);
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
