// web/src/pages/SettingsPage.test.tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '../contexts/ThemeContext';
import SettingsPage from './SettingsPage';
import * as forumService from '../services/forumService';
import type { ForumMyProfile } from '../types/forum';

vi.mock('../services/forumService');

// GET me/profile/ fixture (todo 340). Spread it per test — `mockReset: true`
// wipes mock values between tests, so every describe seeds its own.
const myProfile: ForumMyProfile = {
  display_name: 'Jane Doe',
  bio: '',
  signature: '',
  title: '',
  trust_level: 1,
  post_count: 3,
  capabilities: { can_react: true, can_reply: true, can_create_topic: true },
  avatar: null,
  digest_frequency: 'off',
};

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
    // Default: no blocked/muted users and a digest-off profile, so the
    // theme-control tests below (which don't care about those sections) don't
    // hang on an unresolved auto-mocked promise.
    vi.mocked(forumService.fetchBlockedUsers).mockResolvedValue([]);
    vi.mocked(forumService.fetchMutedUsers).mockResolvedValue([]);
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });
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
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });
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
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });
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

describe('SettingsPage email digest (todo 340)', () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.density;
    delete document.documentElement.dataset.mode;
    vi.mocked(forumService.fetchBlockedUsers).mockResolvedValue([]);
    vi.mocked(forumService.fetchMutedUsers).mockResolvedValue([]);
  });

  it('renders the section copy and the current frequency from the API', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({
      ...myProfile,
      digest_frequency: 'weekly',
    });

    renderPage();

    expect(screen.getByText('Email digest')).toBeInTheDocument();
    expect(screen.getByText(/off by default/i)).toBeInTheDocument();
    // No control until the profile has loaded.
    expect(screen.queryByLabelText('Frequency')).toBeNull();

    const select = await screen.findByLabelText('Frequency');
    expect(select).toHaveValue('weekly');
    expect(screen.getByRole('option', { name: 'Off' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Weekly' })).toBeInTheDocument();
    expect(forumService.fetchMyForumProfile).toHaveBeenCalledTimes(1);
  });

  it('saves a change and announces "Saved" in the always-mounted live region', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });
    vi.mocked(forumService.updateMyForumProfile).mockResolvedValue({
      ...myProfile,
      digest_frequency: 'weekly',
    });

    const { container } = renderPage();
    // Present from the very first paint — before the profile has even loaded —
    // so it cannot live inside the loading/loaded conditional.
    const regionBeforeLoad = container.querySelector('#digest-frequency-status');
    expect(regionBeforeLoad).not.toBeNull();
    const select = await screen.findByLabelText('Frequency');
    expect(select).toHaveValue('off');

    // The region is present and EMPTY before the change — a `findByText('Saved')`
    // after the fact would pass for a conditionally mounted node too, which is
    // the anti-pattern a live region exists to avoid (docs/rules/react.md).
    const region = container.querySelector('#digest-frequency-status');
    expect(region).not.toBeNull();
    expect(region).toBe(regionBeforeLoad); // the same node survived the load
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveClass('sr-only');
    expect(region?.textContent).toBe('');

    await userEvent.selectOptions(select, 'weekly');

    await waitFor(() =>
      expect(forumService.updateMyForumProfile).toHaveBeenCalledWith({ digest_frequency: 'weekly' })
    );
    await waitFor(() => expect(region).toHaveTextContent('Saved'));
    expect(region).not.toHaveClass('sr-only');
    // Same node — the text swapped inside it; nothing was remounted.
    expect(container.querySelector('#digest-frequency-status')).toBe(region);
    expect(select).toHaveValue('weekly');
    expect(select).toBeEnabled();
  });

  it('disables the control while a save is in flight and re-enables it after', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });
    let resolveSave: ((profile: ForumMyProfile) => void) | null = null;
    vi.mocked(forumService.updateMyForumProfile).mockImplementation(
      () =>
        new Promise<ForumMyProfile>((resolve) => {
          resolveSave = resolve;
        })
    );

    renderPage();
    const select = await screen.findByLabelText('Frequency');
    await userEvent.selectOptions(select, 'weekly');

    await waitFor(() => expect(select).toBeDisabled());
    expect(select).toHaveAttribute('aria-busy', 'true');
    expect(select).toHaveValue('weekly'); // optimistic while the save is pending
    // A second change while the first is in flight must not fire a second
    // PATCH (the control is disabled; the handler also guards).
    fireEvent.change(select, { target: { value: 'off' } });
    expect(forumService.updateMyForumProfile).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveSave?.({ ...myProfile, digest_frequency: 'weekly' });
    });

    await waitFor(() => expect(select).toBeEnabled());
    expect(select).toHaveFocus(); // refocused after the disable/enable cycle
    expect(select).not.toHaveAttribute('aria-busy');
    expect(select).toHaveValue('weekly');
  });

  it('reverts to the last saved value and shows the error when the save fails', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });
    // authenticatedFetch's own fallback message for an unreadable error body.
    vi.mocked(forumService.updateMyForumProfile).mockRejectedValue(new Error('Request failed'));

    const { container } = renderPage();
    const select = await screen.findByLabelText('Frequency');
    await userEvent.selectOptions(select, 'weekly');

    const region = container.querySelector('#digest-frequency-status');
    await waitFor(() => expect(region).toHaveTextContent('Request failed'));
    expect(region).toHaveClass('text-error');
    expect(select).toHaveValue('off');
    expect(select).toBeEnabled();
  });

  it('shows the load error with a Retry button that refetches', async () => {
    vi.mocked(forumService.fetchMyForumProfile)
      .mockRejectedValueOnce(new Error('Request failed'))
      .mockResolvedValueOnce({ ...myProfile, digest_frequency: 'weekly' });

    renderPage();

    expect(await screen.findByText('Request failed')).toBeInTheDocument();
    expect(screen.queryByLabelText('Frequency')).toBeNull();

    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByLabelText('Frequency')).toHaveValue('weekly');
    expect(forumService.fetchMyForumProfile).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('Request failed')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
  });
});
