/**
 * SettingsPage Component
 *
 * Application settings page — theme controls (density, dark mode).
 * Allows users to configure app preferences and notifications.
 *
 * Features (planned):
 * - Email digest opt-in ← LIVE (todo 340)
 * - Notification preferences (push / email per event) ← LIVE (todo 343)
 * - Privacy settings — blocked users ← LIVE (todo 284/M9); muted users ← LIVE (todo 347)
 * - Theme preferences (density / dark mode) ← LIVE in Phase A
 * - Language selection
 * - Account deletion
 */
import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { useTheme, type Density } from '../contexts/ThemeContext';
import {
  fetchBlockedUsers,
  unblockUser,
  fetchMutedUsers,
  unmuteUser,
  fetchMyForumProfile,
  updateMyForumProfile,
} from '../services/forumService';
import { specimenAvatar } from '../utils/forumAvatars';
import { logger } from '../utils/logger';
import Eyebrow from '../components/ui/Eyebrow';
import Avatar from '../components/ui/Avatar';
import type {
  BlockedUser,
  MutedUser,
  DigestFrequency,
  ForumMyProfile,
  NotificationChannel,
  NotificationPreferences,
  NotificationVerb,
} from '../types/forum';

const DENSITIES: Density[] = ['comfortable', 'cozy', 'compact'];

function ThemeControls() {
  const { density, mode, setDensity, toggleMode } = useTheme();
  return (
    <div className="space-y-8 p-screen">
      <section>
        <Eyebrow>Appearance</Eyebrow>
        <button
          onClick={toggleMode}
          className="mt-2 rounded-pill border border-line px-4 py-2 text-ink"
        >
          {mode === 'dark' ? 'Switch to Light' : 'Switch to Dark'}
        </button>
      </section>

      <section>
        <Eyebrow>Density</Eyebrow>
        <div className="mt-2 inline-flex rounded-pill border border-line p-1">
          {DENSITIES.map((d) => (
            <button
              key={d}
              onClick={() => setDensity(d)}
              aria-pressed={density === d}
              className={`rounded-pill px-4 py-1 capitalize ${
                density === d ? 'bg-primary text-on-primary' : 'text-ink-3'
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

const DIGEST_OPTIONS: { value: DigestFrequency; label: string }[] = [
  { value: 'off', label: 'Off' },
  { value: 'weekly', label: 'Weekly' },
];

function isDigestFrequency(value: string): value is DigestFrequency {
  return DIGEST_OPTIONS.some((option) => option.value === value);
}

export function EmailDigestSection() {
  // The caller's own profile (todo 340). `digest_frequency` is the only
  // field this section edits; the rest rides along untouched.
  const [profile, setProfile] = useState<ForumMyProfile | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Bumped by Retry so the load effect re-runs.
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [saving, setSaving] = useState(false);
  const selectRef = useRef<HTMLSelectElement>(null);
  const [refocusRequest, setRefocusRequest] = useState(0);
  useEffect(() => {
    // Same guard as the preferences grid (todo 343 review): never yank focus
    // back from wherever the user went while the save was in flight.
    if (refocusRequest > 0 && document.activeElement === document.body) {
      selectRef.current?.focus();
    }
  }, [refocusRequest]);
  // Outcome of the last save — "Saved" or the error — rendered in ONE
  // always-mounted live region below.
  const [notice, setNotice] = useState<{ text: string; tone: 'saved' | 'error' } | null>(null);

  useEffect(() => {
    let ignore = false;
    fetchMyForumProfile()
      .then((data) => {
        if (!ignore) setProfile(data);
      })
      .catch((err) => {
        if (!ignore) {
          setLoadError(err instanceof Error ? err.message : 'Failed to load email preferences');
        }
      });
    return () => {
      ignore = true;
    };
  }, [loadAttempt]);

  const retry = () => {
    setLoadError(null);
    setLoadAttempt((n) => n + 1);
  };

  const handleChange = async (event: ChangeEvent<HTMLSelectElement>) => {
    if (saving) return; // disabled meanwhile, and a programmatic change must not race
    const next = event.target.value;
    if (!profile || !isDigestFrequency(next) || next === profile.digest_frequency) return;
    const previous = profile.digest_frequency;
    setNotice(null);
    setSaving(true);
    // Optimistic: the control shows the new choice while the save is in
    // flight (it is disabled meanwhile, so no second change can race it)…
    setProfile({ ...profile, digest_frequency: next });
    try {
      const updated = await updateMyForumProfile({ digest_frequency: next });
      setProfile(updated);
      setNotice({ text: 'Saved', tone: 'saved' });
    } catch (err) {
      logger.error('Error updating digest frequency', {
        component: 'SettingsPage',
        error: err,
        context: { digest_frequency: next },
      });
      // …and reverts to the last SAVED value when it fails.
      setProfile((cur) => (cur ? { ...cur, digest_frequency: previous } : cur));
      setNotice({
        text: err instanceof Error ? err.message : 'Failed to save email preferences',
        tone: 'error',
      });
    } finally {
      setSaving(false);
      // Disabling the select while saving blurred a keyboard user to <body>;
      // focusing here is a no-op (still disabled this tick) — the effect
      // below refocuses once React has re-enabled it (ConversationPage's
      // pattern).
      setRefocusRequest((n) => n + 1);
    }
  };

  return (
    <section className="p-screen">
      <Eyebrow>Email digest</Eyebrow>
      <p className="mt-1 text-sm text-ink-3">
        A weekly email with new replies on topics you follow and the most active topics you have not
        seen. Off by default.
      </p>
      {profile === null ? (
        loadError ? (
          <div className="mt-2">
            <p className="text-sm text-error">{loadError}</p>
            <button
              type="button"
              onClick={retry}
              className="mt-1 min-h-11 px-3 py-1 text-sm text-primary hover:bg-primary/10 rounded-pill"
            >
              Retry
            </button>
          </div>
        ) : (
          <p className="mt-2 text-sm text-ink-3">Loading…</p>
        )
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <label htmlFor="digest-frequency" className="text-sm font-medium text-ink-2">
            Frequency
          </label>
          <select
            id="digest-frequency"
            ref={selectRef}
            value={profile.digest_frequency}
            onChange={handleChange}
            disabled={saving}
            aria-busy={saving || undefined}
            aria-describedby="digest-frequency-status"
            className="min-h-11 rounded-sm border border-line bg-surface-2/60 px-3 py-2 text-ink focus:ring-2 focus:ring-secondary focus:outline-none disabled:opacity-50"
          >
            {DIGEST_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      )}
      {/* Save outcome — ALWAYS mounted, only the text swaps; `sr-only` while
          empty. It sits outside the load/loaded conditional above on purpose:
          a live region under a conditionally rendered ancestor is recreated
          with its content and announces nothing (docs/rules/react.md). */}
      <p
        id="digest-frequency-status"
        aria-live="polite"
        aria-atomic="true"
        className={
          notice
            ? `mt-2 text-sm ${notice.tone === 'error' ? 'text-error' : 'text-ink-3'}`
            : 'sr-only'
        }
      >
        {notice?.text}
      </p>
    </section>
  );
}

const NOTIFICATION_VERBS: { verb: NotificationVerb; label: string }[] = [
  { verb: 'reply', label: 'Replies to topics you follow' },
  { verb: 'mention', label: 'Mentions' },
  { verb: 'quote', label: 'Quotes of your posts' },
  { verb: 'solution', label: 'Answer accepted' },
];

const NOTIFICATION_CHANNELS: { channel: NotificationChannel; label: string }[] = [
  { channel: 'push', label: 'Push' },
  { channel: 'email', label: 'Email' },
];

/** The profile's notification matrix, or null when there is nothing to
 * render. Web and backend deploy on separate pipelines, so a web build can
 * meet a backend that does not send `notification_preferences` yet (or sends
 * something that is not an object); indexing into it would crash the whole
 * page, so the section treats that as a load failure instead. */
function notificationMatrix(profile: ForumMyProfile | null): NotificationPreferences | null {
  // Typed optional, but a skewed backend could also send null — check at runtime.
  const matrix: unknown = profile?.notification_preferences;
  return matrix !== null && typeof matrix === 'object' ? (matrix as NotificationPreferences) : null;
}

/** One cell of the matrix — `undefined` when the backend sent no such cell,
 * i.e. the channel has no delivery path for that event (email exists for
 * `reply` alone today; a PATCH for a missing cell is a 400). The KEYS of the
 * object, not `NOTIFICATION_VERBS`, decide what exists, so a missing row or a
 * non-boolean value reads as "not available" too rather than throwing. */
function notificationCell(
  matrix: NotificationPreferences,
  verb: NotificationVerb,
  channel: NotificationChannel
): boolean | undefined {
  const row: Partial<Record<NotificationChannel, boolean>> | undefined = matrix[verb];
  const value = row?.[channel];
  return typeof value === 'boolean' ? value : undefined;
}

/** A copy of `profile` with ONE notification cell set. The matrix is
 * replaced, never mutated, so the optimistic flip and the revert on failure
 * each hand React a fresh reference. A profile without a matrix has no cell
 * to flip and comes back unchanged. */
function withNotificationPreference(
  profile: ForumMyProfile,
  verb: NotificationVerb,
  channel: NotificationChannel,
  value: boolean
): ForumMyProfile {
  const matrix = profile.notification_preferences;
  if (!matrix) return profile;
  return {
    ...profile,
    notification_preferences: {
      ...matrix,
      [verb]: { ...matrix[verb], [channel]: value },
    },
  };
}

export function NotificationPreferencesSection() {
  // The caller's own profile again (todo 343), fetched separately from
  // EmailDigestSection on purpose: each section owns its load/retry/save
  // state exactly as the digest section does, the PATCH is partial (only the
  // toggled cell), and every response carries the full profile, so the two
  // copies cannot disagree on anything either one renders. Every cell is
  // disabled while one save is in flight (`disabled={saving}`, the documented
  // pattern) — at 4 × 2 a per-cell pending map (BlockedUsersSection's shape)
  // would buy nothing, but it is the upgrade path for a larger grid.
  const [profile, setProfile] = useState<ForumMyProfile | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Bumped by Retry so the load effect re-runs.
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [saving, setSaving] = useState(false);
  // The cell toggled last. Disabling every cell while a save is in flight
  // blurs a keyboard user to <body>; the effect refocuses that cell once
  // React has re-enabled it (the digest section's pattern) — but only when
  // focus is still on <body> or somewhere in this section. A user who moved
  // on while the save was in flight keeps their place.
  const sectionRef = useRef<HTMLElement>(null);
  const lastToggledRef = useRef<HTMLInputElement | null>(null);
  const [refocusRequest, setRefocusRequest] = useState(0);
  useEffect(() => {
    if (refocusRequest === 0) return;
    const active = document.activeElement;
    const strayed =
      active !== null && active !== document.body && !sectionRef.current?.contains(active);
    if (!strayed) lastToggledRef.current?.focus();
  }, [refocusRequest]);
  // Outcome of the last save — "Saved" or the error — rendered in ONE
  // always-mounted live region below.
  const [notice, setNotice] = useState<{ text: string; tone: 'saved' | 'error' } | null>(null);

  useEffect(() => {
    let ignore = false;
    fetchMyForumProfile()
      .then((data) => {
        if (!ignore) setProfile(data);
      })
      .catch((err) => {
        if (!ignore) {
          setLoadError(
            err instanceof Error ? err.message : 'Failed to load notification preferences'
          );
        }
      });
    return () => {
      ignore = true;
    };
  }, [loadAttempt]);

  const retry = () => {
    setLoadError(null);
    setProfile(null); // back to "Loading…" — also drops a matrix-less profile
    setLoadAttempt((n) => n + 1);
  };

  const handleToggle = async (
    event: ChangeEvent<HTMLInputElement>,
    verb: NotificationVerb,
    channel: NotificationChannel
  ) => {
    if (saving) return; // every cell is disabled meanwhile; the handler guards too
    const matrix = notificationMatrix(profile);
    if (!matrix) return;
    const previous = notificationCell(matrix, verb, channel);
    if (previous === undefined) return; // no such cell is ever rendered, so nothing to save
    lastToggledRef.current = event.currentTarget;
    const next = !previous;
    setNotice(null);
    setSaving(true);
    // Optimistic: the cell shows its new state while the save is in flight.
    // Functional form, like the revert below, so the flip applies to whatever
    // profile is current rather than the render this handler closed over…
    setProfile((cur) => cur && withNotificationPreference(cur, verb, channel, next));
    try {
      // Only the toggled cell goes over the wire — the server merges it into
      // the stored overrides and answers with the full resolved matrix.
      const updated = await updateMyForumProfile({
        notification_preferences: { [verb]: { [channel]: next } },
      });
      setProfile(updated);
      setNotice({ text: 'Saved', tone: 'saved' });
    } catch (err) {
      logger.error('Error updating notification preference', {
        component: 'SettingsPage',
        error: err,
        context: { verb, channel, value: next },
      });
      // …and reverts to the last SAVED value when it fails.
      setProfile((cur) => cur && withNotificationPreference(cur, verb, channel, previous));
      setNotice({
        text: err instanceof Error ? err.message : 'Failed to save notification preferences',
        tone: 'error',
      });
    } finally {
      setSaving(false);
      setRefocusRequest((n) => n + 1);
    }
  };

  const matrix = notificationMatrix(profile);
  // A loaded profile with no renderable matrix is a load failure from this
  // section's point of view (deploy skew — see notificationMatrix): the same
  // message-plus-Retry branch as a failed request, never an empty grid.
  const problem =
    loadError ??
    (profile !== null && matrix === null
      ? 'Notification preferences are not available yet.'
      : null);

  return (
    <section ref={sectionRef} className="p-screen">
      <Eyebrow>Notifications</Eyebrow>
      <p className="mt-1 text-sm text-ink-3">
        In-app notifications are always on. Choose which events also reach you by push or email.
      </p>
      {matrix === null ? (
        problem ? (
          <div className="mt-2">
            <p className="text-sm text-error">{problem}</p>
            <button
              type="button"
              onClick={retry}
              className="mt-1 min-h-11 px-3 py-1 text-sm text-primary hover:bg-primary/10 rounded-pill"
            >
              Retry
            </button>
          </div>
        ) : (
          <p className="mt-2 text-sm text-ink-3">Loading…</p>
        )
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Notification channels by event</caption>
            <thead>
              <tr className="border-b border-line">
                <th scope="col" className="py-2 pr-4 text-left font-medium text-ink-2">
                  Event
                </th>
                {NOTIFICATION_CHANNELS.map((c) => (
                  <th
                    key={c.channel}
                    scope="col"
                    className="w-20 py-2 text-center font-medium text-ink-2"
                  >
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {NOTIFICATION_VERBS.map((v) => (
                <tr key={v.verb}>
                  <th scope="row" className="py-2 pr-4 text-left font-normal text-ink">
                    {v.label}
                  </th>
                  {NOTIFICATION_CHANNELS.map((c) => {
                    const value = notificationCell(matrix, v.verb, c.channel);
                    return (
                      <td key={c.channel} className="py-1 text-center">
                        {value === undefined ? (
                          // The API sent no such cell: this channel has no
                          // delivery path for the event, so there is nothing
                          // to switch (and a PATCH for it would be a 400).
                          <>
                            <span aria-hidden="true" className="text-ink-3">
                              —
                            </span>
                            <span className="sr-only">Not available</span>
                          </>
                        ) : (
                          /* The label only enlarges the hit target to 44px;
                             the input's own aria-label is its accessible name. */
                          <label className="inline-flex min-h-11 min-w-11 items-center justify-center">
                            <input
                              type="checkbox"
                              checked={value}
                              onChange={(event) => handleToggle(event, v.verb, c.channel)}
                              disabled={saving}
                              aria-busy={saving || undefined}
                              aria-label={`${c.label} for ${v.label}`}
                              aria-describedby="notification-preferences-status"
                              className="h-5 w-5 accent-primary focus:ring-2 focus:ring-secondary focus:outline-none disabled:opacity-50"
                            />
                          </label>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {/* Save outcome — ALWAYS mounted, only the text swaps; `sr-only` while
          empty. Outside the load/loaded conditional above on purpose: a live
          region under a conditionally rendered ancestor is recreated with its
          content and announces nothing (docs/rules/react.md). */}
      <p
        id="notification-preferences-status"
        aria-live="polite"
        aria-atomic="true"
        className={
          notice
            ? `mt-2 text-sm ${notice.tone === 'error' ? 'text-error' : 'text-ink-3'}`
            : 'sr-only'
        }
      >
        {notice?.text}
      </p>
    </section>
  );
}

function BlockedUsersSection() {
  const [blocked, setBlocked] = useState<BlockedUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Per-row pending state (username -> in flight) so unblocking one row
  // doesn't disable every other row's button.
  const [pending, setPending] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let active = true;
    fetchBlockedUsers()
      .then((data) => {
        if (active) setBlocked(data);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : 'Failed to load blocked users');
      });
    return () => {
      active = false;
    };
  }, []);

  const handleUnblock = async (username: string) => {
    setPending((prev) => ({ ...prev, [username]: true }));
    try {
      await unblockUser(username);
      // Removed from the list on success — no refetch needed, matches the
      // low-cardinality, unpaginated shape of GET /me/blocks/.
      setBlocked((prev) => (prev ? prev.filter((u) => u.username !== username) : prev));
    } catch (err) {
      logger.error('Error unblocking user', {
        component: 'SettingsPage',
        error: err,
        context: { username },
      });
      setError(err instanceof Error ? err.message : 'Failed to unblock user');
    } finally {
      setPending((prev) => {
        const next = { ...prev };
        delete next[username];
        return next;
      });
    }
  };

  return (
    <section className="p-screen">
      <Eyebrow>Blocked users</Eyebrow>
      {error && <p className="mt-2 text-sm text-error">{error}</p>}
      {blocked === null ? (
        <p className="mt-2 text-sm text-ink-3">Loading…</p>
      ) : blocked.length === 0 ? (
        <p className="mt-2 text-sm text-ink-3">You haven't blocked anyone.</p>
      ) : (
        <ul className="mt-2 divide-y divide-line">
          {blocked.map((u) => (
            <li key={u.username} className="flex items-center justify-between gap-3 py-3">
              <div className="flex items-center gap-3 min-w-0">
                <Avatar src={u.avatar || specimenAvatar(u.username)} alt="" size="md" />
                <span className="truncate text-ink">{u.display_name || u.username}</span>
              </div>
              <button
                type="button"
                onClick={() => handleUnblock(u.username)}
                disabled={!!pending[u.username]}
                className="min-h-11 shrink-0 px-3 py-1 text-sm text-primary hover:bg-primary/10 rounded-pill disabled:opacity-50"
              >
                Unblock
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function MutedUsersSection() {
  // Mirror of BlockedUsersSection (todo 347): same per-row pending state,
  // same local removal without a refetch.
  const [muted, setMuted] = useState<MutedUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let active = true;
    fetchMutedUsers()
      .then((data) => {
        if (active) setMuted(data);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : 'Failed to load muted users');
      });
    return () => {
      active = false;
    };
  }, []);

  const handleUnmute = async (username: string) => {
    setPending((prev) => ({ ...prev, [username]: true }));
    try {
      await unmuteUser(username);
      setMuted((prev) => (prev ? prev.filter((u) => u.username !== username) : prev));
    } catch (err) {
      logger.error('Error unmuting user', {
        component: 'SettingsPage',
        error: err,
        context: { username },
      });
      setError(err instanceof Error ? err.message : 'Failed to unmute user');
    } finally {
      setPending((prev) => {
        const next = { ...prev };
        delete next[username];
        return next;
      });
    }
  };

  return (
    <section className="p-screen">
      <Eyebrow>Muted users</Eyebrow>
      <p className="mt-1 text-sm text-ink-3">
        Muting hides a member's posts and notifications from you only — they can still see and
        message you. Block for the stronger, two-way version.
      </p>
      {error && <p className="mt-2 text-sm text-error">{error}</p>}
      {muted === null ? (
        <p className="mt-2 text-sm text-ink-3">Loading…</p>
      ) : muted.length === 0 ? (
        <p className="mt-2 text-sm text-ink-3">You haven't muted anyone.</p>
      ) : (
        <ul className="mt-2 divide-y divide-line">
          {muted.map((u) => (
            <li key={u.username} className="flex items-center justify-between gap-3 py-3">
              <div className="flex items-center gap-3 min-w-0">
                <Avatar src={u.avatar || specimenAvatar(u.username)} alt="" size="md" />
                <span className="truncate text-ink">{u.display_name || u.username}</span>
              </div>
              <button
                type="button"
                onClick={() => handleUnmute(u.username)}
                disabled={!!pending[u.username]}
                className="min-h-11 shrink-0 px-3 py-1 text-sm text-primary hover:bg-primary/10 rounded-pill disabled:opacity-50"
              >
                Unmute
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function SettingsPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-ink">Settings</h1>
        <p className="mt-2 text-ink-3">Manage your application preferences and account settings</p>
      </div>

      {/* Theme Controls */}
      <ThemeControls />

      {/* Email digest (todo 340) */}
      <EmailDigestSection />

      {/* Notification preferences (todo 343) */}
      <NotificationPreferencesSection />

      {/* Blocked users (todo 284/M9) */}
      <BlockedUsersSection />

      {/* Muted users (todo 347) */}
      <MutedUsersSection />
    </div>
  );
}
