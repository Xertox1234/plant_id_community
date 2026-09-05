/**
 * SettingsPage Component
 *
 * Application settings page — theme controls (density, dark mode).
 * Allows users to configure app preferences and notifications.
 *
 * Features (planned):
 * - Email notifications preferences ← PARTIALLY LIVE: weekly digest opt-in only (todo 340)
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
import type { BlockedUser, MutedUser, DigestFrequency, ForumMyProfile } from '../types/forum';

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

function EmailDigestSection() {
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
    if (refocusRequest > 0) selectRef.current?.focus();
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

      {/* Blocked users (todo 284/M9) */}
      <BlockedUsersSection />

      {/* Muted users (todo 347) */}
      <MutedUsersSection />
    </div>
  );
}
