import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { fetchUserProfile } from '../../services/forumService';
import { threadPath, postAnchor } from '../../utils/forumUrls';
import type { ForumUserProfile } from '../../types/forum';

// Mirrors the backend ForumProfile.TrustLevel enum (0–4); shared shape with PostCard.
const TRUST_LEVEL_LABELS: Record<number, string> = {
  0: 'New',
  1: 'Basic',
  2: 'Member',
  3: 'Regular',
  4: 'Leader',
};

function relative(iso: string): string {
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true });
  } catch {
    return 'recently';
  }
}

/**
 * Public forum profile page (todo 257 H7): identity + trust + recent activity.
 * Read-only; the endpoint is public (no auth required).
 */
export default function UserProfilePage() {
  const { username = '' } = useParams<{ username: string }>();
  const [profile, setProfile] = useState<ForumUserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fetchUserProfile(username)
      .then((data) => {
        if (active) setProfile(data);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : 'Profile not found');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [username]);

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto p-6" role="status" aria-label="Loading profile">
        <div className="h-24 bg-surface-2 rounded-lg animate-pulse" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <title>Profile not found — Forum</title>
        <p className="text-ink-3">{error || 'Profile not found.'}</p>
        <Link to="/forum" className="text-primary hover:underline">
          ← Back to the forum
        </Link>
      </div>
    );
  }

  const name = profile.display_name || profile.username;

  return (
    <div className="max-w-3xl mx-auto p-6">
      <title>{`${name} — Forum profile`}</title>

      {/* Header */}
      <header className="flex items-center gap-4 mb-6">
        <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center overflow-hidden shrink-0">
          {profile.avatar ? (
            <img src={profile.avatar} alt="" className="w-full h-full object-cover" />
          ) : (
            <span className="text-3xl font-bold text-leaf">{name[0]}</span>
          )}
        </div>
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-bold text-ink">{name}</h1>
            {typeof profile.trust_level === 'number' && profile.trust_level >= 1 && (
              <span className="px-2 py-0.5 bg-sky/10 text-ink text-xs rounded">
                {TRUST_LEVEL_LABELS[profile.trust_level] ?? `Level ${profile.trust_level}`}
              </span>
            )}
          </div>
          <p className="text-sm text-ink-3">
            @{profile.username} · {profile.post_count} posts
            {profile.joined_at && <> · joined {relative(profile.joined_at)}</>}
          </p>
        </div>
      </header>

      {profile.bio && <p className="mb-6 text-ink break-words">{profile.bio}</p>}

      {/* Recent topics */}
      <section className="mb-6">
        <h2 className="text-lg font-semibold text-ink mb-2">Recent topics</h2>
        {profile.recent_topics.length === 0 ? (
          <p className="text-sm text-ink-3">No topics yet.</p>
        ) : (
          <ul className="space-y-1">
            {profile.recent_topics.map((t) => (
              <li key={t.id}>
                <Link
                  to={threadPath(
                    { id: String(t.board_id), slug: t.board_slug, name: '' },
                    { id: String(t.id), slug: t.slug, title: t.title }
                  )}
                  className="text-primary hover:underline"
                >
                  {t.title}
                </Link>
                <span className="text-sm text-ink-3"> · {relative(t.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Recent replies */}
      <section>
        <h2 className="text-lg font-semibold text-ink mb-2">Recent replies</h2>
        {profile.recent_posts.length === 0 ? (
          <p className="text-sm text-ink-3">No replies yet.</p>
        ) : (
          <ul className="space-y-1">
            {profile.recent_posts.map((p) => (
              <li key={p.id}>
                <Link
                  to={`${threadPath(
                    { id: String(p.board_id), slug: p.board_slug, name: '' },
                    { id: String(p.topic_id), slug: p.topic_slug, title: p.topic_title }
                  )}${postAnchor(p.id)}`}
                  className="text-primary hover:underline"
                >
                  {p.topic_title}
                </Link>
                <span className="text-sm text-ink-3"> · {relative(p.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
