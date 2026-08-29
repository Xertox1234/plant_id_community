/**
 * SettingsPage Component
 *
 * Application settings page — theme controls (density, dark mode).
 * Allows users to configure app preferences and notifications.
 *
 * Features (planned):
 * - Email notifications preferences
 * - Privacy settings — blocked users ← LIVE (todo 284/M9)
 * - Theme preferences (density / dark mode) ← LIVE in Phase A
 * - Language selection
 * - Account deletion
 */
import { useEffect, useState } from 'react';
import { useTheme, type Density } from '../contexts/ThemeContext';
import { fetchBlockedUsers, unblockUser } from '../services/forumService';
import { specimenAvatar } from '../utils/forumAvatars';
import { logger } from '../utils/logger';
import Eyebrow from '../components/ui/Eyebrow';
import Avatar from '../components/ui/Avatar';
import type { BlockedUser } from '../types/forum';

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

      {/* Blocked users (todo 284/M9) */}
      <BlockedUsersSection />
    </div>
  );
}
