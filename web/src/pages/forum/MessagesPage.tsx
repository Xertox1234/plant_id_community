import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchConversations } from '../../services/messageService';
import { useAuth } from '../../contexts/AuthContext';
import { specimenAvatar } from '../../utils/forumAvatars';
import { conversationPath, groupConversationPath } from '../../utils/forumUrls';
import { logger } from '../../utils/logger';
import Avatar from '../../components/ui/Avatar';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import CountBadge from '../../components/ui/CountBadge';
import Timestamp from '../../components/ui/Timestamp';
import { AVATAR_BOX, AVATAR_RADIUS } from '../../components/ui/dimensions';
import ForumErrorState from '../../components/forum/ForumErrorState';
import { SkeletonBlock, SkeletonStatus } from '../../components/forum/ForumSkeleton';
import NewGroupConversationForm from '../../components/forum/NewGroupConversationForm';
import type { Conversation, ForumAuthor } from '../../types/forum';

const SKELETON_ROWS = 4;
/** How many member avatars a group row shows before folding the rest into "+N". */
const STACK_LIMIT = 3;

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

function authorName(author: ForumAuthor): string {
  return author.display_name || author.username;
}

interface ParticipantStackProps {
  participants: ForumAuthor[];
  viewerUsername: string | undefined;
}

/**
 * Overlapping trio of member avatars for a group row, the viewer left out
 * (they know what they look like) and everyone past the third folded into a
 * "+N" tile of the same box. Decorative: the row's accessible name carries
 * the title and the member count.
 */
function ParticipantStack({ participants, viewerUsername }: ParticipantStackProps) {
  const others = viewerUsername
    ? participants.filter((p) => p.username !== viewerUsername)
    : participants;
  const shown = others.slice(0, STACK_LIMIT);
  const extra = others.length - shown.length;
  return (
    <span className="flex flex-none -space-x-2" aria-hidden="true">
      {shown.map((p) => (
        <Avatar key={p.username} size="sm" src={p.avatar || specimenAvatar(p.username)} alt="" />
      ))}
      {extra > 0 && (
        <span
          className={`inline-grid place-items-center border border-line bg-surface-2 font-mono text-micro font-semibold text-ink-2 ${AVATAR_BOX.sm} ${AVATAR_RADIUS.sm}`}
        >
          +{extra}
        </span>
      )}
    </span>
  );
}

interface InboxRowProps {
  conversation: Conversation;
  viewerUsername: string | undefined;
}

/**
 * One inbox row. A direct row is the other member's avatar and name; a group
 * row (todo 350) is its title over a stack of member avatars, and its preview
 * is prefixed with who sent it ("Ada: …", "You: …") — in a group the sender
 * is not implied by the row the way it is for a two-party thread.
 */
function InboxRow({ conversation, viewerUsername }: InboxRowProps) {
  const { last_message: last } = conversation;
  const unread = conversation.unread_count > 0;
  const isGroup = conversation.kind === 'group';
  const other = conversation.other_participant;

  // A direct row without the other side cannot be opened: the backend never
  // sends one, but a null here must degrade on its OWN terms rather than
  // borrow the group layout and link to a group path (react review).
  const unavailable = !isGroup && !other;

  let name: string;
  let href: string;
  let preview: string;
  let label: string;
  if (isGroup) {
    name = conversation.title;
    href = groupConversationPath(conversation.id);
    // `sender` is null once that member left the group — keep the text and
    // attribute it neutrally instead of reading through null (react review).
    const who = last?.is_mine ? 'You' : last?.sender ? authorName(last.sender) : 'Former member';
    preview = last ? `${who}: ${last.body}` : '';
    label = `${name} (group of ${conversation.participant_count}${
      unread ? `, ${conversation.unread_count} unread` : ''
    })`;
  } else if (unavailable) {
    name = 'Unavailable conversation';
    href = '';
    preview = last ? last.body : '';
    label = name;
  } else {
    name = authorName(other);
    href = conversationPath(other.username);
    preview = last ? `${last.is_mine ? 'You: ' : ''}${last.body}` : '';
    label = `${name}${unread ? ` (${conversation.unread_count} unread)` : ''}`;
  }

  const rowClass =
    'flex items-center gap-4 px-5 py-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary';
  const body = (
    <>
      {isGroup ? (
        <ParticipantStack
          participants={conversation.participants}
          viewerUsername={viewerUsername}
        />
      ) : other ? (
        <Avatar src={other.avatar || specimenAvatar(other.username)} alt="" />
      ) : (
        <Avatar src={specimenAvatar(String(conversation.id))} alt="" />
      )}
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
        <p className={`mt-0.5 truncate text-sm ${unread ? 'text-ink' : 'text-ink-3'}`}>{preview}</p>
      </div>
      {unread && (
        <span className="shrink-0" aria-hidden="true">
          <CountBadge count={conversation.unread_count} />
        </span>
      )}
    </>
  );

  return (
    <li>
      {unavailable ? (
        <div aria-label={label} className={`${rowClass} opacity-70`} data-kind={conversation.kind}>
          {body}
        </div>
      ) : (
        <Link
          to={href}
          aria-label={label}
          className={`${rowClass} hover:bg-surface-2/60`}
          data-unread={unread || undefined}
          data-kind={conversation.kind}
        >
          {body}
        </Link>
      )}
    </li>
  );
}

/**
 * The message inbox (todo 339): one row per conversation, most recent
 * activity first — direct threads and groups (todo 350) interleaved. Routed
 * under ProtectedLayout, so an anonymous visitor is bounced to /login before
 * this renders — the same treatment as every other auth-only page.
 */
export default function MessagesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  const [composingGroup, setComposingGroup] = useState(false);
  const groupToggleId = useId();
  const groupFormId = useId();
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
      <header className="mb-6 flex items-end justify-between gap-4">
        <div>
          <p className="gt-label mb-1">Inbox</p>
          <h1 className="gt-h1 text-ink">Messages</h1>
        </div>
        {user && (
          <Button
            id={groupToggleId}
            variant="outline"
            size="sm"
            aria-expanded={composingGroup}
            aria-controls={groupFormId}
            onClick={() => setComposingGroup((open) => !open)}
            className="min-h-11"
          >
            New group
          </Button>
        )}
      </header>

      {composingGroup && (
        <Card id={groupFormId} className="mb-6 p-5">
          <h2 className="gt-h3 text-ink mb-4">New group</h2>
          <NewGroupConversationForm
            onCreated={(created) => navigate(groupConversationPath(created.id))}
            onCancel={() => {
              setComposingGroup(false);
              // A disclosure that closes must hand focus back to its toggle,
              // or a keyboard user lands on <body> (react review).
              document.getElementById(groupToggleId)?.focus();
            }}
          />
        </Card>
      )}

      {loading && <InboxSkeleton />}

      {!loading && error && (
        <ForumErrorState title="Error loading messages" message={error} onRetry={load} />
      )}

      {!loading && !error && conversations.length === 0 && (
        <Card className="px-6 py-10 text-center">
          <p className="text-ink font-medium">No messages yet.</p>
          <p className="mt-1 text-sm text-ink-3">
            Open a member's profile and press Message to start a conversation, or start a group.
          </p>
        </Card>
      )}

      {!loading && !error && conversations.length > 0 && (
        <>
          <Card>
            <ul aria-label="Conversations" className="divide-y divide-line">
              {conversations.map((conversation) => (
                <InboxRow
                  key={conversation.id}
                  conversation={conversation}
                  viewerUsername={user?.username}
                />
              ))}
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
