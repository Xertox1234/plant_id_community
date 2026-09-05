import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchConversations } from '../../services/messageService';
import { useAuth } from '../../contexts/AuthContext';
import { specimenAvatar } from '../../utils/forumAvatars';
import { conversationPath } from '../../utils/forumUrls';
import { logger } from '../../utils/logger';
import Avatar from '../../components/ui/Avatar';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import CountBadge from '../../components/ui/CountBadge';
import Timestamp from '../../components/ui/Timestamp';
import { AVATAR_BOX } from '../../components/ui/dimensions';
import ForumErrorState from '../../components/forum/ForumErrorState';
import { SkeletonBlock, SkeletonStatus } from '../../components/forum/ForumSkeleton';
import type { Conversation } from '../../types/forum';

const SKELETON_ROWS = 4;

function InboxSkeleton() {
  return (
    <SkeletonStatus label="Loading messages…">
      <Card className="divide-y divide-line">
        {Array.from({ length: SKELETON_ROWS }, (_, i) => (
          <div key={i} className="flex items-center gap-4 px-5 py-4">
            <SkeletonBlock rounded="avatar-md" className={`${AVATAR_BOX.md} flex-none`} />
            <div className="min-w-0 flex-1">
              <SkeletonBlock className="h-4 w-1/3" />
              <SkeletonBlock className="mt-2 h-3 w-3/4" />
            </div>
          </div>
        ))}
      </Card>
    </SkeletonStatus>
  );
}

/**
 * The direct-message inbox (todo 339): one row per conversation, most recent
 * activity first. Routed under ProtectedLayout, so an anonymous visitor is
 * bounced to /login before this renders — the same treatment as every other
 * auth-only page.
 */
export default function MessagesPage() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  // Monotonic request epoch: a page that resolves after a newer initial load
  // (retry, identity change) must not append onto the fresher list.
  const requestEpochRef = useRef(0);

  const load = useCallback(async () => {
    const epoch = ++requestEpochRef.current;
    setLoading(true);
    setError(null);
    setLoadMoreError(null);
    // A load-more still in flight for the previous identity never reaches
    // its guarded `finally` once this epoch bump lands — clear its flag here
    // or "Load more" stays disabled for the new account.
    setLoadingMore(false);
    try {
      const page = await fetchConversations();
      if (epoch !== requestEpochRef.current) return;
      setConversations(page.results);
      setNextCursor(page.next);
    } catch (err) {
      if (epoch !== requestEpochRef.current) return;
      logger.error('Error loading conversations', { component: 'MessagesPage', error: err });
      setError(err instanceof Error ? err.message : 'Failed to load messages');
    } finally {
      if (epoch === requestEpochRef.current) setLoading(false);
    }
  }, []);

  // `user?.id` in the deps, not just a mount-once effect: `isAuthenticated` is
  // `!!user`, so an account swap on tab focus (todo 297) never remounts this
  // page — the inbox would keep showing the previous account's threads.
  const userId = user?.id;
  useEffect(() => {
    void load();
  }, [load, userId]);

  const loadMore = async () => {
    if (!nextCursor || loadingMore) return;
    const epoch = requestEpochRef.current;
    setLoadingMore(true);
    setLoadMoreError(null);
    try {
      const page = await fetchConversations(nextCursor);
      if (epoch !== requestEpochRef.current) return;
      setConversations((prev) => [...prev, ...page.results]);
      setNextCursor(page.next);
    } catch (err) {
      if (epoch !== requestEpochRef.current) return;
      logger.error('Error loading more conversations', { component: 'MessagesPage', error: err });
      setLoadMoreError(err instanceof Error ? err.message : 'Failed to load more messages');
    } finally {
      if (epoch === requestEpochRef.current) setLoadingMore(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-6">
      <title>Messages · Houseplant MD</title>
      <header className="mb-6">
        <p className="gt-label mb-1">Inbox</p>
        <h1 className="gt-h1 text-ink">Messages</h1>
      </header>

      {loading && <InboxSkeleton />}

      {!loading && error && (
        <ForumErrorState title="Error loading messages" message={error} onRetry={load} />
      )}

      {!loading && !error && conversations.length === 0 && (
        <Card className="px-6 py-10 text-center">
          <p className="text-ink font-medium">No messages yet.</p>
          <p className="mt-1 text-sm text-ink-3">
            Open a member's profile and press Message to start a conversation.
          </p>
        </Card>
      )}

      {!loading && !error && conversations.length > 0 && (
        <>
          <Card>
            <ul aria-label="Conversations" className="divide-y divide-line">
              {conversations.map((conversation) => {
                const { other_participant: other, last_message: last } = conversation;
                const name = other.display_name || other.username;
                const unread = conversation.unread_count > 0;
                const preview = last ? `${last.is_mine ? 'You: ' : ''}${last.body}` : '';
                return (
                  <li key={conversation.id}>
                    <Link
                      to={conversationPath(other.username)}
                      aria-label={`${name}${unread ? ` (${conversation.unread_count} unread)` : ''}`}
                      className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-surface-2/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
                      data-unread={unread || undefined}
                    >
                      <Avatar src={other.avatar || specimenAvatar(other.username)} alt="" />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline justify-between gap-3">
                          <span
                            className={`truncate ${unread ? 'font-semibold text-ink' : 'font-medium text-ink-2'}`}
                          >
                            {name}
                          </span>
                          <span className="gt-label shrink-0 normal-case tracking-normal">
                            <Timestamp iso={conversation.last_message_at} />
                          </span>
                        </div>
                        <p
                          className={`mt-0.5 truncate text-sm ${unread ? 'text-ink' : 'text-ink-3'}`}
                        >
                          {preview}
                        </p>
                      </div>
                      {unread && (
                        <span className="shrink-0" aria-hidden="true">
                          <CountBadge count={conversation.unread_count} />
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </Card>

          {/* Persistent live region for the load-more failure (never a
              conditionally-mounted alert — see docs/rules/react.md). */}
          <p aria-live="polite" className={loadMoreError ? 'mt-3 text-sm text-error' : 'sr-only'}>
            {loadMoreError}
          </p>

          {nextCursor && (
            <div className="mt-4 flex justify-center">
              <Button
                variant="outline"
                onClick={loadMore}
                loading={loadingMore}
                loadingText="Loading…"
                className="min-h-11"
              >
                Load more
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
