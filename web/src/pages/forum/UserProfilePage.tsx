import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { fetchUserProfile } from '../../services/forumService';
import { specimenAvatar } from '../../utils/forumAvatars';
import { threadPath, postAnchor } from '../../utils/forumUrls';
import { TRUST_LEVEL_LABELS } from '../../utils/forumAuthor';
import Avatar from '../../components/ui/Avatar';
import Card from '../../components/ui/Card';
import type { ForumUserProfile } from '../../types/forum';

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

  // Reset synchronously when the :username param changes (e.g. clicking another
  // author while already on a profile page) so the previous user's profile
  // doesn't flash under the new URL for a frame before the effect refetches.
  const [renderedFor, setRenderedFor] = useState(username);
  if (renderedFor !== username) {
    setRenderedFor(username);
    setProfile(null);
    setLoading(true);
    setError(null);
  }

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
        <title>Profile not found · Houseplant MD</title>
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
      <title>{`${name} · Houseplant MD`}</title>

      {/* Header — identity card: specimen avatar beside the collector's label lines. */}
      <Card className="mb-8 p-6">
        <p className="gt-label mb-3">Member profile</p>
        <div className="flex items-center gap-5">
          <Avatar src={profile.avatar || specimenAvatar(profile.username)} alt="" size="lg" />
          <div className="min-w-0">
            <div className="flex items-baseline gap-2 flex-wrap">
              <h1 className="gt-h1 text-ink">{name}</h1>
              {typeof profile.trust_level === 'number' && profile.trust_level >= 1 && (
                <span className="gt-label rounded-pill border border-sky/40 px-2 py-0.5 text-sky">
                  {TRUST_LEVEL_LABELS[profile.trust_level] ?? `Level ${profile.trust_level}`}
                </span>
              )}
            </div>
            <p className="gt-label mt-1.5 normal-case tracking-normal">
              @{profile.username} · {profile.post_count} posts
              {profile.joined_at && <> · joined {relative(profile.joined_at)}</>}
            </p>
          </div>
        </div>
      </Card>

      {profile.bio && <p className="mb-2 text-ink break-words leading-relaxed">{profile.bio}</p>}
      {profile.signature && (
        <p className="mb-6 text-sm text-ink-3 italic break-words">{profile.signature}</p>
      )}

      {/* Recent topics */}
      <section className="mb-8">
        <h2 className="gt-h3 text-ink mb-2">Recent topics</h2>
        {profile.recent_topics.length === 0 ? (
          <p className="text-sm text-ink-3">No topics yet.</p>
        ) : (
          <ul className="divide-y divide-line">
            {profile.recent_topics.map((t) => (
              <li key={t.id} className="flex flex-wrap items-baseline gap-x-2 px-1 py-2.5">
                <Link
                  to={threadPath(
                    { id: String(t.board_id), slug: t.board_slug, name: '' },
                    { id: String(t.id), slug: t.slug, title: t.title }
                  )}
                  className="text-ink font-medium hover:text-primary hover:underline"
                >
                  {t.title}
                </Link>
                <span className="gt-label">{relative(t.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Recent replies */}
      <section>
        <h2 className="gt-h3 text-ink mb-2">Recent replies</h2>
        {profile.recent_posts.length === 0 ? (
          <p className="text-sm text-ink-3">No replies yet.</p>
        ) : (
          <ul className="divide-y divide-line">
            {profile.recent_posts.map((p) => (
              <li key={p.id} className="flex flex-wrap items-baseline gap-x-2 px-1 py-2.5">
                <Link
                  to={`${threadPath(
                    { id: String(p.board_id), slug: p.board_slug, name: '' },
                    { id: String(p.topic_id), slug: p.topic_slug, title: p.topic_title }
                  )}${postAnchor(p.id)}`}
                  className="text-ink font-medium hover:text-primary hover:underline"
                >
                  {p.topic_title}
                </Link>
                <span className="gt-label">{relative(p.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
