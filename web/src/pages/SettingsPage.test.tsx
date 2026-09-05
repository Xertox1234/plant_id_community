// web/src/pages/SettingsPage.test.tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '../contexts/ThemeContext';
import SettingsPage, { EmailDigestSection, NotificationPreferencesSection } from './SettingsPage';
import * as forumService from '../services/forumService';
import type {
  ForumMyProfile,
  NotificationChannel,
  NotificationPreferences,
  NotificationVerb,
} from '../types/forum';

vi.mock('../services/forumService');

// The resolved matrix as the API sends it (todo 343): ONLY the cells with a
// delivery path — push for every event, email for replies alone today. The
// keys say which cells exist. Deliberately mixed so "checked per the API" is
// a real assertion rather than "everything on".
const notificationMatrix: NotificationPreferences = {
  reply: { push: true, email: false },
  mention: { push: true },
  quote: { push: false },
  solution: { push: true },
};

// GET me/profile/ fixture (todos 340 + 343). Spread it per test — `mockReset: true`
// wipes mock values between tests, so every describe seeds its own.
const profileBase: Omit<ForumMyProfile, 'notification_preferences'> = {
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
const myProfile: ForumMyProfile = { ...profileBase, notification_preferences: notificationMatrix };

/** A profile from a backend that predates todo 343 — no `notification_preferences`
 * key at all (web and backend deploy on separate pipelines). */
const legacyProfile: ForumMyProfile = { ...profileBase };

/** `myProfile` as the server returns it after merging `{ mention: { push: false } }`. */
const withMentionPushOff: ForumMyProfile = {
  ...myProfile,
  notification_preferences: { ...notificationMatrix, mention: { push: false } },
};

// Human labels the matrix renders — the accessible name of a cell is
// `${channel} for ${event}`.
const VERB_LABELS: Record<NotificationVerb, string> = {
  reply: 'Replies to topics you follow',
  mention: 'Mentions',
  quote: 'Quotes of your posts',
  solution: 'Answer accepted',
};
const CHANNEL_LABELS: Record<NotificationChannel, string> = { push: 'Push', email: 'Email' };

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

// The two profile-backed sections are rendered STANDALONE below: each owns
// its profile fetch, so the call counts and the `mockResolvedValueOnce`
// chains are that section's alone and cannot depend on where it sits in the
// page's JSX. The page-level smoke test at the end covers composition.
describe('EmailDigestSection (todo 340)', () => {
  it('renders the section copy and the current frequency from the API', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({
      ...myProfile,
      digest_frequency: 'weekly',
    });

    render(<EmailDigestSection />);

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

    const { container } = render(<EmailDigestSection />);
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

    render(<EmailDigestSection />);
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

    const { container } = render(<EmailDigestSection />);
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

    render(<EmailDigestSection />);

    expect(await screen.findByText('Request failed')).toBeInTheDocument();
    expect(screen.queryByLabelText('Frequency')).toBeNull();

    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));

    // The SECOND response is what renders — a refetch happened.
    expect(await screen.findByLabelText('Frequency')).toHaveValue('weekly');
    expect(forumService.fetchMyForumProfile).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('Request failed')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
  });
});

describe('NotificationPreferencesSection (todo 343)', () => {
  const cell = (verb: NotificationVerb, channel: NotificationChannel) =>
    screen.getByRole('checkbox', { name: `${CHANNEL_LABELS[channel]} for ${VERB_LABELS[verb]}` });

  it('renders a labelled cell for every event × channel the API sent, checked per the fixture, and "—" where it did not', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });

    render(<NotificationPreferencesSection />);

    expect(screen.getByText('Notifications')).toBeInTheDocument();
    expect(screen.getByText(/in-app notifications are always on/i)).toBeInTheDocument();
    // No cells until the profile has loaded.
    expect(screen.queryByRole('checkbox')).toBeNull();

    expect(await screen.findByRole('checkbox', { name: 'Push for Mentions' })).toBeChecked();
    // 4 push cells + the one email cell the API sent (reply) — nothing else.
    expect(screen.getAllByRole('checkbox')).toHaveLength(5);
    const matrix = Object.entries(notificationMatrix) as [
      NotificationVerb,
      Partial<Record<NotificationChannel, boolean>>,
    ][];
    for (const [verb, channels] of matrix) {
      for (const [channel, on] of Object.entries(channels) as [NotificationChannel, boolean][]) {
        const box = cell(verb, channel);
        if (on) expect(box).toBeChecked();
        else expect(box).not.toBeChecked();
        expect(box).toBeEnabled();
      }
    }
    // The three email cells the API did NOT send (mention, quote, solution)
    // are a muted dash for sighted users and "Not available" for a screen
    // reader — never a checkbox the server would 400 on.
    for (const verb of ['mention', 'quote', 'solution'] as const) {
      expect(screen.queryByRole('checkbox', { name: `Email for ${VERB_LABELS[verb]}` })).toBeNull();
    }
    const dashes = screen.getAllByText('—');
    expect(dashes).toHaveLength(3);
    for (const dash of dashes) expect(dash).toHaveAttribute('aria-hidden', 'true');
    const unavailable = screen.getAllByText('Not available');
    expect(unavailable).toHaveLength(3);
    for (const note of unavailable) expect(note).toHaveClass('sr-only');
    expect(forumService.fetchMyForumProfile).toHaveBeenCalledTimes(1);
  });

  it('exposes the grid as a table: sr-only caption, scoped column and row headers', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });

    render(<NotificationPreferencesSection />);
    await screen.findByRole('checkbox', { name: 'Push for Mentions' });

    // The caption is the table's accessible name.
    const table = screen.getByRole('table', { name: 'Notification channels by event' });
    const caption = table.querySelector('caption');
    expect(caption).toHaveTextContent('Notification channels by event');
    expect(caption).toHaveClass('sr-only');

    const columns = screen.getAllByRole('columnheader');
    expect(columns.map((th) => th.textContent)).toEqual(['Event', 'Push', 'Email']);
    for (const th of columns) expect(th).toHaveAttribute('scope', 'col');

    const rows = screen.getAllByRole('rowheader');
    expect(rows.map((th) => th.textContent)).toEqual([
      VERB_LABELS.reply,
      VERB_LABELS.mention,
      VERB_LABELS.quote,
      VERB_LABELS.solution,
    ]);
    for (const th of rows) expect(th).toHaveAttribute('scope', 'row');
  });

  it('toggling a cell PATCHes exactly that cell and announces "Saved" in the always-mounted live region', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });
    vi.mocked(forumService.updateMyForumProfile).mockResolvedValue(withMentionPushOff);

    const { container } = render(<NotificationPreferencesSection />);
    // Present from the very first paint — before the profile has even loaded —
    // so it cannot live inside the loading/loaded conditional.
    const regionBeforeLoad = container.querySelector('#notification-preferences-status');
    expect(regionBeforeLoad).not.toBeNull();
    const box = await screen.findByRole('checkbox', { name: 'Push for Mentions' });
    expect(box).toBeChecked();

    // Present and EMPTY before the toggle (docs/rules/react.md).
    const region = container.querySelector('#notification-preferences-status');
    expect(region).toBe(regionBeforeLoad); // the same node survived the load
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveClass('sr-only');
    expect(region?.textContent).toBe('');

    await userEvent.click(box);

    await waitFor(() =>
      expect(forumService.updateMyForumProfile).toHaveBeenCalledWith({
        notification_preferences: { mention: { push: false } },
      })
    );
    // Exactly one PATCH, carrying ONLY the toggled cell — not the row, not the matrix.
    expect(vi.mocked(forumService.updateMyForumProfile).mock.calls).toStrictEqual([
      [{ notification_preferences: { mention: { push: false } } }],
    ]);
    await waitFor(() => expect(region).toHaveTextContent('Saved'));
    expect(region).not.toHaveClass('sr-only');
    // Same node — the text swapped inside it; nothing was remounted.
    expect(container.querySelector('#notification-preferences-status')).toBe(region);
    expect(box).not.toBeChecked();
    expect(box).toBeEnabled();
    // Every other cell is untouched.
    expect(cell('reply', 'email')).not.toBeChecked();
    expect(cell('quote', 'push')).not.toBeChecked();
    expect(cell('reply', 'push')).toBeChecked();
  });

  it('reverts the cell and shows the error in the live region when the save fails', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });
    // authenticatedFetch's own fallback message for an unreadable error body.
    vi.mocked(forumService.updateMyForumProfile).mockRejectedValue(new Error('Request failed'));

    const { container } = render(<NotificationPreferencesSection />);
    const box = await screen.findByRole('checkbox', { name: 'Push for Mentions' });
    expect(box).toBeChecked();
    await userEvent.click(box);

    const region = container.querySelector('#notification-preferences-status');
    await waitFor(() => expect(region).toHaveTextContent('Request failed'));
    expect(region).toHaveClass('text-error');
    expect(box).toBeChecked(); // back to the last SAVED value
    expect(box).toBeEnabled();
    expect(cell('reply', 'push')).toBeChecked(); // a neighbouring cell never moved
  });

  it('disables every cell while a save is in flight, ignores a second toggle, and refocuses the toggled cell after', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });
    let resolveSave: ((profile: ForumMyProfile) => void) | null = null;
    vi.mocked(forumService.updateMyForumProfile).mockImplementation(
      () =>
        new Promise<ForumMyProfile>((resolve) => {
          resolveSave = resolve;
        })
    );

    render(<NotificationPreferencesSection />);
    const box = await screen.findByRole('checkbox', { name: 'Push for Mentions' });
    await userEvent.click(box);

    await waitFor(() => expect(box).toBeDisabled());
    for (const each of screen.getAllByRole('checkbox')) expect(each).toBeDisabled();
    expect(box).toHaveAttribute('aria-busy', 'true');
    expect(box).not.toBeChecked(); // optimistic while the save is pending
    // A second toggle while the first is in flight must not fire a second
    // PATCH (the cells are disabled; the handler also guards).
    fireEvent.click(cell('reply', 'email'));
    expect(forumService.updateMyForumProfile).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveSave?.(withMentionPushOff);
    });

    await waitFor(() => expect(box).toBeEnabled());
    for (const each of screen.getAllByRole('checkbox')) expect(each).toBeEnabled();
    expect(box).toHaveFocus(); // refocused after the disable/enable cycle
    expect(box).not.toHaveAttribute('aria-busy');
    expect(box).not.toBeChecked();
    expect(cell('reply', 'email')).not.toBeChecked(); // the ignored toggle left it alone
  });

  it('leaves focus where the user put it when they moved on before the save resolved', async () => {
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });
    let resolveSave: ((profile: ForumMyProfile) => void) | null = null;
    vi.mocked(forumService.updateMyForumProfile).mockImplementation(
      () =>
        new Promise<ForumMyProfile>((resolve) => {
          resolveSave = resolve;
        })
    );

    // Something focusable OUTSIDE the section, as the rest of the page is.
    render(
      <>
        <NotificationPreferencesSection />
        <button type="button">Elsewhere</button>
      </>
    );
    const box = await screen.findByRole('checkbox', { name: 'Push for Mentions' });
    await userEvent.click(box);
    await waitFor(() => expect(box).toBeDisabled());

    const elsewhere = screen.getByRole('button', { name: 'Elsewhere' });
    elsewhere.focus();
    expect(elsewhere).toHaveFocus();

    await act(async () => {
      resolveSave?.(withMentionPushOff);
    });

    await waitFor(() => expect(box).toBeEnabled());
    expect(elsewhere).toHaveFocus(); // not yanked back to the cell
    expect(box).not.toHaveFocus();
  });

  it('shows the load error with a Retry button that refetches', async () => {
    vi.mocked(forumService.fetchMyForumProfile)
      .mockRejectedValueOnce(new Error('Request failed'))
      .mockResolvedValueOnce(withMentionPushOff);

    render(<NotificationPreferencesSection />);

    expect(await screen.findByText('Request failed')).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).toBeNull();

    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));

    // The SECOND response is what renders (mention push off) — a refetch happened.
    expect(await screen.findByRole('checkbox', { name: 'Push for Mentions' })).not.toBeChecked();
    expect(screen.getAllByRole('checkbox')).toHaveLength(5);
    expect(forumService.fetchMyForumProfile).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('Request failed')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
  });

  it.each([
    ['absent (backend predates the field)', legacyProfile],
    [
      'not an object',
      { ...myProfile, notification_preferences: null as unknown as NotificationPreferences },
    ],
  ])(
    'treats a profile whose matrix is %s as a load failure — message + Retry, no cells, no crash',
    async (_label, profile) => {
      vi.mocked(forumService.fetchMyForumProfile)
        .mockResolvedValueOnce(profile)
        .mockResolvedValueOnce({ ...myProfile });

      expect(() => render(<NotificationPreferencesSection />)).not.toThrow();

      expect(
        await screen.findByText('Notification preferences are not available yet.')
      ).toBeInTheDocument();
      expect(screen.queryByRole('checkbox')).toBeNull();
      expect(screen.queryByRole('table')).toBeNull();

      // Retry is the way out once the backend catches up.
      await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
      expect(await screen.findByRole('checkbox', { name: 'Push for Mentions' })).toBeChecked();
      expect(forumService.fetchMyForumProfile).toHaveBeenCalledTimes(2);
      expect(screen.queryByText('Notification preferences are not available yet.')).toBeNull();
    }
  );
});

describe('SettingsPage composes the profile-backed sections', () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.density;
    delete document.documentElement.dataset.mode;
    vi.mocked(forumService.fetchBlockedUsers).mockResolvedValue([]);
    vi.mocked(forumService.fetchMutedUsers).mockResolvedValue([]);
    vi.mocked(forumService.fetchMyForumProfile).mockResolvedValue({ ...myProfile });
  });

  it('renders the digest and notification sections together, each with its own profile fetch', async () => {
    renderPage();

    expect(await screen.findByLabelText('Frequency')).toHaveValue('off');
    expect(await screen.findByRole('checkbox', { name: 'Push for Mentions' })).toBeChecked();
    expect(screen.getAllByRole('checkbox')).toHaveLength(5);
    // Section-owned state: one GET per profile-backed section, in whatever order.
    expect(forumService.fetchMyForumProfile).toHaveBeenCalledTimes(2);
  });
});
