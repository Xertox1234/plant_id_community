import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchUserProfile, blockUser, unblockUser } from '../../services/forumService';
import { useAuth } from '../../contexts/AuthContext';
import { specimenAvatar } from '../../utils/forumAvatars';
import { threadPath, postAnchor } from '../../utils/forumUrls';
import { TRUST_LEVEL_LABELS } from '../../utils/forumAuthor';
import { logger } from '../../utils/logger';
import { UserCheck, UserX } from 'lucide-react';
import { UserProfileSkeleton } from '../../components/forum/ForumSkeleton';
import Avatar from '../../components/ui/Avatar';
import Card from '../../components/ui/Card';
import Timestamp from '../../components/ui/Timestamp';
import type { ForumUserProfile } from '../../types/forum';

/**
 * Public forum profile page (todo 257 H7): identity + trust + recent activity.
 * Read-only; the endpoint is public (no auth required).
 */
export default function UserProfilePage() {
  const { username = '' } = useParams<{ username: string }>();
  const { isAuthenticated } = useAuth();
  const [profile, setProfile] = useState<ForumUserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isBlockActionPending, setIsBlockActionPending] = useState(false);
  const [blockActionError, setBlockActionError] = useState<string | null>(null);
  // Guards a late block/unblock response from writing onto a DIFFERENT
  // profile the user has since navigated to (same rationale as
  // ThreadDetailPage's currentTopicIdRef).
  const currentUsernameRef = useRef(username);

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
    currentUsernameRef.current = username;
    setLoading(true);
    setError(null);
    setBlockActionError(null);
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

  // Optimistic flag flip for instant feedback, THEN a refetch on success —
  // unlike a plain toggle (e.g. subscription), is_blocked and
  // recent_topics/recent_posts are coupled server-side: PublicProfileView
  // skips those queries entirely and returns [] once blocked. A local flip
  // can't predict either direction's real list (blocking must clear them;
  // unblocking must restore real content the client never received while
  // blocked), so the refetch is required for correctness, not just polish.
  // Rollback on failure only touches the flag — the lists were never
  // optimistically touched, so there's nothing to restore there.
  const handleToggleBlock = async () => {
    if (!profile) return;
    const requestUsername = username;
    const wasBlocked = profile.is_blocked ?? false;
    setIsBlockActionPending(true);
    setBlockActionError(null);
    setProfile((prev) => (prev ? { ...prev, is_blocked: !wasBlocked } : prev));
    try {
      if (wasBlocked) {
        await unblockUser(requestUsername);
      } else {
        await blockUser(requestUsername);
      }
      const fresh = await fetchUserProfile(requestUsername);
      if (currentUsernameRef.current === requestUsername) {
        setProfile(fresh);
      }
    } catch (err) {
      logger.error('Error toggling user block', {
        component: 'UserProfilePage',
        error: err,
        context: { username: requestUsername },
      });
      if (currentUsernameRef.current === requestUsername) {
        setProfile((prev) => (prev ? { ...prev, is_blocked: wasBlocked } : prev));
        setBlockActionError(err instanceof Error ? err.message : 'Failed to update block');
      }
    } finally {
      if (currentUsernameRef.current === requestUsername) {
        setIsBlockActionPending(false);
      }
    }
  };

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <UserProfileSkeleton />
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
        <div className="flex items-start justify-between gap-5 flex-wrap">
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
                {/* No `prefix`: Timestamp's aria-label replaces its content, and the
                  literal "joined" before it already labels the date. */}
                {profile.joined_at && (
                  <>
                    {' '}
                    · joined <Timestamp iso={profile.joined_at} />
                  </>
                )}
              </p>
            </div>
          </div>

          {/* Block/unblock — never shown for the viewer's own profile or to
              an anonymous viewer (profile.can_block is the backend authority,
              same discipline as PostCard's can_edit/can_delete/can_report). */}
          {isAuthenticated && profile.can_block && (
            <div className="flex flex-col items-end gap-1">
              <button
                type="button"
                onClick={handleToggleBlock}
                disabled={isBlockActionPending}
                className={`min-h-11 px-3 py-1.5 text-sm rounded-pill inline-flex items-center gap-1.5 disabled:opacity-50 ${
                  profile.is_blocked
                    ? 'text-ink-3 hover:bg-surface-3'
                    : 'text-ink-3 hover:text-error hover:bg-error/10'
                }`}
              >
                {profile.is_blocked ? (
                  <>
                    <UserCheck className="h-3.5 w-3.5" aria-hidden="true" /> Unblock
                  </>
                ) : (
                  <>
                    <UserX className="h-3.5 w-3.5" aria-hidden="true" /> Block
                  </>
                )}
              </button>
              {blockActionError && (
                <p className="text-xs text-error text-right">{blockActionError}</p>
              )}
            </div>
          )}
        </div>
      </Card>

      {profile.is_blocked && (
        <p className="mb-6 text-sm text-ink-3">
          You've blocked this member — their recent activity is hidden.
        </p>
      )}

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
                <span className="gt-label">
                  <Timestamp iso={t.created_at} prefix="Posted" />
                </span>
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
                <span className="gt-label">
                  <Timestamp iso={p.created_at} prefix="Posted" />
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
