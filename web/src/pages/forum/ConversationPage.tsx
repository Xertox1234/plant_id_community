import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Flag } from 'lucide-react';
import {
  addParticipant,
  fetchConversation,
  fetchConversationWith,
  fetchMessages,
  removeParticipant,
  reportMessage,
  sendConversationMessage,
  sendMessage,
  GROUP_MAX_PARTICIPANTS,
  MESSAGE_MAX_LENGTH,
} from '../../services/messageService';
import { ForumApiError } from '../../services/forumService';
import { useAuth } from '../../contexts/AuthContext';
import { useAnnounce } from '../../contexts/AnnouncerContext';
import { useUnreadNotifications } from '../../contexts/UnreadNotificationsContext';
import { authorName } from '../../utils/forumAuthor';
import { specimenAvatar } from '../../utils/forumAvatars';
import { parseLeadingId, userProfilePath } from '../../utils/forumUrls';
import { logger } from '../../utils/logger';
import Avatar from '../../components/ui/Avatar';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import Timestamp from '../../components/ui/Timestamp';
import { AVATAR_BOX } from '../../components/ui/dimensions';
import ForumErrorState from '../../components/forum/ForumErrorState';
import { SkeletonBlock, SkeletonStatus } from '../../components/forum/ForumSkeleton';
import { REPORT_REASONS } from '../../components/forum/reportReasons';
import type { Conversation, DirectMessage } from '../../types/forum';

/** Shown for a 403 on send — either side has blocked the other. */
const BLOCKED_NOTICE = "You can't message this member.";
/** Shown for a 403 on a group send — a member is block-paired with the viewer, or they were removed. */
const GROUP_BLOCKED_NOTICE = "You can't message this group.";
/** The id resolves to no inbox row (404): never a member, removed, or not a group id at all. */
const GROUP_UNAVAILABLE =
  "This group isn't available — it may have been closed, or you're no longer a member.";

function newestFirstToOldestFirst(page: DirectMessage[]): DirectMessage[] {
  return [...page].reverse();
}

function ConversationSkeleton() {
  return (
    <SkeletonStatus label="Loading conversation…">
      <div className="mb-6 flex items-center gap-4">
        <SkeletonBlock rounded="avatar-md" className={`${AVATAR_BOX.md} flex-none`} />
        <SkeletonBlock className="h-6 w-40" />
      </div>
      <div className="flex flex-col gap-3">
        {Array.from({ length: 3 }, (_, i) => (
          <div key={i} className={`flex ${i % 2 ? 'justify-end' : 'justify-start'}`}>
            <SkeletonBlock rounded="md" className="h-12 w-2/3" />
          </div>
        ))}
      </div>
    </SkeletonStatus>
  );
}

interface MessageReportFormProps {
  messageId: number;
  onSubmitted: () => void;
  onCancel: () => void;
  onError: (message: string) => void;
  /** Reads the page's request epoch; captured at submit, re-checked after
   * the await so a late result never lands in another member's thread. */
  getEpoch: () => number;
}

/** Inline report picker for one message — the same reasons as a post report. */
function MessageReportForm({
  messageId,
  getEpoch,
  onSubmitted,
  onCancel,
  onError,
}: MessageReportFormProps) {
  const [reason, setReason] = useState<string>(REPORT_REASONS[0].value);
  const [detail, setDetail] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    const epoch = getEpoch();
    setSubmitting(true);
    try {
      await reportMessage(messageId, reason, detail.trim() || undefined);
      if (epoch !== getEpoch()) return;
      onSubmitted();
    } catch (err) {
      logger.error('Error reporting message', {
        component: 'ConversationPage',
        error: err,
        context: { messageId, reason },
      });
      if (epoch !== getEpoch()) return;
      onError(err instanceof Error ? err.message : 'Failed to report message');
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
      className="mt-2 flex flex-wrap items-center gap-2"
    >
      <label htmlFor={`report-reason-${messageId}`} className="sr-only">
        Report reason
      </label>
      <select
        id={`report-reason-${messageId}`}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        disabled={submitting}
        className="text-sm border border-line rounded-sm px-2 py-1 bg-surface text-ink"
      >
        {REPORT_REASONS.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
      <label htmlFor={`report-detail-${messageId}`} className="sr-only">
        Details (optional)
      </label>
      <input
        id={`report-detail-${messageId}`}
        type="text"
        value={detail}
        onChange={(e) => setDetail(e.target.value)}
        disabled={submitting}
        maxLength={500}
        placeholder="Details (optional)"
        className="min-w-0 flex-1 text-sm border border-line rounded-sm px-2 py-1 bg-surface text-ink placeholder:text-ink-3"
      />
      <button
        type="submit"
        disabled={submitting}
        className="min-h-11 px-3 py-1 text-sm text-error hover:bg-error/10 rounded-pill disabled:opacity-50"
      >
        Submit
      </button>
      <button
        type="button"
        onClick={onCancel}
        disabled={submitting}
        className="min-h-11 px-3 py-1 text-sm text-ink-3 hover:bg-surface-2 rounded-pill disabled:opacity-50"
      >
        Cancel
      </button>
    </form>
  );
}

/**
 * One message thread: `/messages/:username` (direct, todo 339) or
 * `/messages/group/:id` (group, todo 350) — one page, two resolvers.
 *
 * Direct: resolved by the other member's username; a 404 (no thread yet) is
 * an EMPTY thread with the composer live, not an error — the first send
 * creates it. Group: resolved by id through the single-row GET
 * (`conversations/<id>/`); its 404 means the group is not available to the
 * viewer — a group cannot be "not yet". Messages arrive newest-first per
 * page and are rendered oldest→newest, so "Load older" prepends. Membership
 * changes keep local state from the responses (add returns the row, remove
 * is a 204). Routed under ProtectedLayout.
 */
export default function ConversationPage() {
  const { username = '', id: groupParam } = useParams<{ username: string; id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const announce = useAnnounce();
  const { refresh: refreshUnread } = useUnreadNotifications();
  const isGroupRoute = groupParam !== undefined;
  const groupId = isGroupRoute ? parseLeadingId(groupParam) : null;
  // One key for both routes so the reset below fires on ANY thread change,
  // including direct → group under the same component instance.
  const routeKey = isGroupRoute ? `group:${groupParam}` : `member:${username}`;
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<DirectMessage[]>([]);
  const [olderCursor, setOlderCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  // Write-path notice (send/report/load-older/membership failures).
  // Persistent live region below, same shape as ThreadDetailPage's.
  const [notice, setNotice] = useState<string | null>(null);
  const [reportingId, setReportingId] = useState<number | null>(null);
  const [reportedIds, setReportedIds] = useState<ReadonlySet<number>>(() => new Set());
  // Group membership panel (todo 350). One in-flight gate for every
  // membership action — add, remove, leave — so two cannot race each other's
  // local state (the block/mute lesson, docs/rules/react.md).
  const [membersOpen, setMembersOpen] = useState(false);
  const [memberDraft, setMemberDraft] = useState('');
  const [memberAction, setMemberAction] = useState<string | null>(null);
  const [leaveConfirmOpen, setLeaveConfirmOpen] = useState(false);
  const membersPanelId = useId();
  const memberHintId = useId();
  // Monotonic request epoch: a response only lands if no navigation to
  // another thread (or newer load) happened after it started.
  const requestEpochRef = useRef(0);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  // Bumped after a successful send; the effect below focuses the composer
  // once React has re-enabled it (focusing while `sending` still disables
  // the textarea is a no-op).
  const [focusRequest, setFocusRequest] = useState(0);
  useEffect(() => {
    if (focusRequest > 0) composerRef.current?.focus();
  }, [focusRequest]);

  // Reset synchronously when the route changes so the previous thread never
  // flashes under the new URL (same shape as UserProfilePage).
  const [renderedFor, setRenderedFor] = useState(routeKey);
  if (renderedFor !== routeKey) {
    setRenderedFor(routeKey);
    setConversation(null);
    setMessages([]);
    setOlderCursor(null);
    setLoading(true);
    setError(null);
    setNotice(null);
    setDraft('');
    setReportingId(null);
    setMembersOpen(false);
    setMemberDraft('');
    setLeaveConfirmOpen(false);
    // In-flight flags too: load() below bumps the epoch, so a send / load-older
    // / membership call still running for the previous thread never reaches
    // its `finally` — left alone they would pin the new thread's controls
    // disabled forever.
    setSending(false);
    setLoadingOlder(false);
    setMemberAction(null);
  }

  // Merge by id: a "Load older" page can overlap what is already on screen
  // (the echo of a just-sent message, a cursor boundary), and React keys
  // are message ids — never spread pages together raw.
  const mergeMessages = (
    existing: DirectMessage[],
    incoming: DirectMessage[],
    where: 'start' | 'end'
  ) => {
    const known = new Set(existing.map((m) => m.id));
    const fresh = incoming.filter((m) => !known.has(m.id));
    return where === 'start' ? [...fresh, ...existing] : [...existing, ...fresh];
  };

  const load = useCallback(async () => {
    const epoch = ++requestEpochRef.current;
    setLoading(true);
    setError(null);
    try {
      const resolved = isGroupRoute
        ? groupId === null
          ? null
          : await fetchConversation(groupId)
        : await fetchConversationWith(username);
      if (epoch !== requestEpochRef.current) return;
      if (isGroupRoute && !resolved) {
        // Unlike a direct thread, a group cannot be "not yet" — no row means
        // the viewer cannot see it.
        setError(GROUP_UNAVAILABLE);
        return;
      }
      setConversation(resolved);
      if (resolved) {
        const page = await fetchMessages(resolved.id);
        if (epoch !== requestEpochRef.current) return;
        setMessages(newestFirstToOldestFirst(page.results));
        setOlderCursor(page.next);
        // Reading the page marked the thread read server-side — pull the
        // badge in line now rather than on the next poll tick.
        refreshUnread();
      } else {
        setMessages([]);
        setOlderCursor(null);
      }
    } catch (err) {
      if (epoch !== requestEpochRef.current) return;
      logger.error('Error loading conversation', {
        component: 'ConversationPage',
        error: err,
        context: { username, groupId },
      });
      setError(err instanceof Error ? err.message : 'Failed to load messages');
    } finally {
      if (epoch === requestEpochRef.current) setLoading(false);
    }
  }, [isGroupRoute, groupId, username, refreshUnread]);

  // `user?.id` in the deps: `isAuthenticated` is `!!user`, so an account swap
  // on tab focus never remounts this page (docs/rules/react.md, todo 315).
  const userId = user?.id;
  useEffect(() => {
    void load();
  }, [load, userId]);

  const loadOlder = async () => {
    if (!conversation || !olderCursor || loadingOlder) return;
    const epoch = requestEpochRef.current;
    setLoadingOlder(true);
    setNotice(null);
    try {
      const page = await fetchMessages(conversation.id, olderCursor);
      if (epoch !== requestEpochRef.current) return;
      setMessages((prev) => mergeMessages(prev, newestFirstToOldestFirst(page.results), 'start'));
      setOlderCursor(page.next);
    } catch (err) {
      if (epoch !== requestEpochRef.current) return;
      logger.error('Error loading older messages', {
        component: 'ConversationPage',
        error: err,
        context: { username, groupId },
      });
      setNotice(err instanceof Error ? err.message : 'Failed to load older messages');
    } finally {
      if (epoch === requestEpochRef.current) setLoadingOlder(false);
    }
  };

  const handleSend = async () => {
    const body = draft.trim();
    if (!body || sending) return;
    const epoch = requestEpochRef.current;
    const requestUsername = username;
    // A group is only ever sent to by id; a direct thread keeps the
    // username endpoint, which also creates the thread on first send.
    const groupTarget = conversation?.kind === 'group' ? conversation : null;
    setSending(true);
    setNotice(null);
    try {
      const sent = groupTarget
        ? await sendConversationMessage(groupTarget.id, body)
        : await sendMessage(requestUsername, body);
      if (epoch !== requestEpochRef.current) return;
      setMessages((prev) => mergeMessages(prev, [sent], 'end'));
      setDraft('');
      announce('Message sent.', 'polite');
      // The Send button disables itself on the now-empty draft, which would
      // drop keyboard focus to <body>; keep the author in the composer.
      setFocusRequest((n) => n + 1);
      if (!conversation) {
        // First send created the thread — re-resolve for its id (Load older)
        // and the other member's display identity. Best-effort: the message
        // is already on screen, so a failure here is not worth a notice.
        try {
          const created = await fetchConversationWith(requestUsername);
          if (epoch === requestEpochRef.current) setConversation(created);
        } catch (err) {
          logger.error('Error resolving new conversation', {
            component: 'ConversationPage',
            error: err,
            context: { username: requestUsername },
          });
        }
      }
    } catch (err) {
      if (epoch !== requestEpochRef.current) return;
      logger.error('Error sending message', {
        component: 'ConversationPage',
        error: err,
        context: { username: requestUsername, groupId },
      });
      // Branch on the STATUS, never the text: a 403 arrives as DRF's default
      // detail, which mentions neither "403" nor "forbidden".
      if (err instanceof ForumApiError && err.status === 403) {
        setNotice(groupTarget ? GROUP_BLOCKED_NOTICE : BLOCKED_NOTICE);
      } else {
        setNotice(err instanceof Error ? err.message : 'Failed to send message');
      }
    } finally {
      if (epoch === requestEpochRef.current) setSending(false);
    }
  };

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      void handleSend();
    }
  };

  // --- Group membership (todo 350) -------------------------------------
  const viewerUsername = user?.username;
  const isGroup = conversation?.kind === 'group';
  const canManage = isGroup && conversation.can_manage;
  const atCap = isGroup && conversation.participant_count >= GROUP_MAX_PARTICIPANTS;

  const handleAddMember = async () => {
    const target = memberDraft.trim().replace(/^@/, '');
    if (!conversation || !target || memberAction || atCap) return;
    const epoch = requestEpochRef.current;
    setMemberAction('add');
    setNotice(null);
    try {
      const updated = await addParticipant(conversation.id, target);
      if (epoch !== requestEpochRef.current) return;
      setConversation(updated);
      setMemberDraft('');
      announce(`Added ${target} to the group.`, 'polite');
    } catch (err) {
      if (epoch !== requestEpochRef.current) return;
      logger.error('Error adding group member', {
        component: 'ConversationPage',
        error: err,
        context: { groupId },
      });
      setNotice(err instanceof Error ? err.message : 'Failed to add member');
    } finally {
      if (epoch === requestEpochRef.current) setMemberAction(null);
    }
  };

  const handleRemoveMember = async (target: string) => {
    if (!conversation || memberAction) return;
    const conversationId = conversation.id;
    const epoch = requestEpochRef.current;
    setMemberAction(target);
    setNotice(null);
    try {
      await removeParticipant(conversationId, target);
      if (epoch !== requestEpochRef.current) return;
      // 204 carries no row: drop the member locally. Functional form, and
      // guarded on the id, so a late result never edits another thread; the
      // count only moves by what the filter actually removed, so a member
      // already gone from the local row cannot drive it below the truth.
      setConversation((cur) => {
        if (!cur || cur.id !== conversationId) return cur;
        const participants = cur.participants.filter((p) => p.username !== target);
        const removed = cur.participants.length - participants.length;
        if (removed === 0) return cur;
        return {
          ...cur,
          participants,
          participant_count: Math.max(0, cur.participant_count - removed),
        };
      });
      announce(`Removed ${target} from the group.`, 'polite');
    } catch (err) {
      if (epoch !== requestEpochRef.current) return;
      logger.error('Error removing group member', {
        component: 'ConversationPage',
        error: err,
        context: { groupId },
      });
      setNotice(err instanceof Error ? err.message : 'Failed to remove member');
    } finally {
      if (epoch === requestEpochRef.current) setMemberAction(null);
    }
  };

  const closeLeaveConfirm = useCallback(() => setLeaveConfirmOpen(false), []);

  const handleLeave = async () => {
    setLeaveConfirmOpen(false);
    if (!conversation || !viewerUsername || memberAction) return;
    const title = conversation.title;
    const epoch = requestEpochRef.current;
    setMemberAction(viewerUsername);
    setNotice(null);
    try {
      await removeParticipant(conversation.id, viewerUsername);
      if (epoch !== requestEpochRef.current) return;
      // The app-wide announcer outlives this page, so the confirmation is
      // still read after the navigation.
      announce(`You left ${title}.`, 'polite');
      navigate('/messages');
    } catch (err) {
      if (epoch !== requestEpochRef.current) return;
      logger.error('Error leaving group', {
        component: 'ConversationPage',
        error: err,
        context: { groupId },
      });
      setNotice(err instanceof Error ? err.message : 'Failed to leave the group');
    } finally {
      if (epoch === requestEpochRef.current) setMemberAction(null);
    }
  };

  const other = conversation?.other_participant ?? null;
  const otherUsername = other?.username ?? username;
  const name = isGroup ? conversation.title : other?.display_name || otherUsername;

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <ConversationSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <title>Messages · Houseplant MD</title>
        <ForumErrorState title="Error loading conversation" message={error} onRetry={load} />
        <Link to="/messages" className="mt-4 inline-block text-primary hover:underline">
          ← Back to messages
        </Link>
      </div>
    );
  }

  const membershipBusy = memberAction !== null;

  return (
    <div className="max-w-3xl mx-auto p-6">
      <title>{`${name} · Messages · Houseplant MD`}</title>

      <Link to="/messages" className="gt-label mb-4 inline-block hover:text-primary">
        ← Messages
      </Link>

      {isGroup ? (
        <header className="mb-6">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="gt-label mb-1">Group</p>
              <h1 className="gt-h2 text-ink truncate">{conversation.title}</h1>
            </div>
            <button
              type="button"
              aria-expanded={membersOpen}
              aria-controls={membersPanelId}
              onClick={() => setMembersOpen((open) => !open)}
              className="min-h-11 shrink-0 rounded-pill border border-line px-4 py-2 text-body-sm font-medium text-ink-2 hover:bg-surface-2 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
            >
              {`Members (${conversation.participant_count})`}
            </button>
          </div>
          {/* Members row: avatars + names in joined order, the creator marked. */}
          <ul aria-label="Members" className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            {conversation.participants.map((p) => {
              const isCreator = conversation.created_by?.username === p.username;
              const isMe = viewerUsername !== undefined && p.username === viewerUsername;
              return (
                <li key={p.username} className="flex items-center gap-2 text-body-sm text-ink-2">
                  <Avatar size="sm" src={p.avatar || specimenAvatar(p.username)} alt="" />
                  <span>
                    {isMe ? 'You' : authorName(p)}
                    {isCreator && <span className="gt-label ml-1.5">creator</span>}
                  </span>
                </li>
              );
            })}
          </ul>

          {membersOpen && (
            <Card id={membersPanelId} className="mt-4 p-5">
              <h2 className="gt-h3 text-ink mb-3">Members</h2>
              <ul aria-label="Manage members" className="divide-y divide-line">
                {conversation.participants.map((p) => {
                  const isCreator = conversation.created_by?.username === p.username;
                  const isMe = viewerUsername !== undefined && p.username === viewerUsername;
                  const display = authorName(p);
                  return (
                    <li key={p.username} className="flex items-center gap-3 py-2">
                      <Avatar size="sm" src={p.avatar || specimenAvatar(p.username)} alt="" />
                      <div className="min-w-0 flex-1">
                        <Link
                          to={userProfilePath(p.username)}
                          className="font-medium text-ink hover:text-primary hover:underline"
                        >
                          {isMe ? 'You' : display}
                        </Link>
                        {isCreator && <span className="gt-label ml-2">creator</span>}
                        <span className="block truncate text-meta text-ink-3">@{p.username}</span>
                      </div>
                      {/* Remove: creator only, never for yourself (leaving is below). */}
                      {canManage && !isMe && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => void handleRemoveMember(p.username)}
                          disabled={membershipBusy}
                          loading={memberAction === p.username}
                          loadingText="Removing…"
                          aria-label={`Remove ${display}`}
                          className="min-h-11"
                        >
                          Remove
                        </Button>
                      )}
                    </li>
                  );
                })}
              </ul>

              {canManage && (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleAddMember();
                  }}
                  className="mt-4"
                >
                  <label htmlFor="add-member" className="block text-sm font-medium text-ink-2 mb-1">
                    Add member
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      id="add-member"
                      type="text"
                      value={memberDraft}
                      onChange={(event) => setMemberDraft(event.target.value)}
                      // At the cap the field stays mounted and focusable
                      // (`aria-disabled` + readOnly, not `disabled`) and the
                      // hint says why; the handler is a no-op.
                      readOnly={atCap}
                      aria-disabled={atCap || undefined}
                      aria-describedby={memberHintId}
                      autoComplete="off"
                      autoCapitalize="off"
                      spellCheck={false}
                      placeholder={atCap ? '' : 'Username'}
                      className="min-w-0 flex-1 rounded-lg border border-line-2 bg-surface px-3 py-2 text-ink placeholder-ink-3 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                    <Button
                      type="submit"
                      size="sm"
                      aria-disabled={atCap || undefined}
                      disabled={membershipBusy}
                      loading={memberAction === 'add'}
                      loadingText="Adding…"
                      className="min-h-11"
                    >
                      Add
                    </Button>
                  </div>
                  <p id={memberHintId} className="mt-1 text-meta text-ink-3">
                    {atCap
                      ? `This group is full (${GROUP_MAX_PARTICIPANTS} members).`
                      : `Up to ${GROUP_MAX_PARTICIPANTS} members, including you.`}
                  </p>
                </form>
              )}

              {/* Leave: any member except the creator (who cannot leave while
                  others remain — v1 has no transfer). */}
              {!canManage && viewerUsername && (
                <div className="mt-4 flex justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setLeaveConfirmOpen(true)}
                    disabled={membershipBusy}
                    loading={memberAction === viewerUsername}
                    loadingText="Leaving…"
                    className="min-h-11 text-error"
                  >
                    Leave group
                  </Button>
                </div>
              )}
            </Card>
          )}
        </header>
      ) : (
        <header className="mb-6 flex items-center gap-4">
          <Avatar src={other?.avatar || specimenAvatar(otherUsername)} alt="" />
          <div className="min-w-0">
            <h1 className="gt-h2 text-ink truncate">
              <Link
                to={userProfilePath(otherUsername)}
                className="hover:text-primary hover:underline"
              >
                {name}
              </Link>
            </h1>
            <p className="gt-label mt-0.5 normal-case tracking-normal">@{otherUsername}</p>
          </div>
        </header>
      )}

      {messages.length === 0 ? (
        <Card className="mb-6 px-6 py-10 text-center">
          <p className="text-ink font-medium">No messages yet — say hello.</p>
        </Card>
      ) : (
        <>
          {olderCursor && (
            <div className="mb-4 flex justify-center">
              <Button
                variant="outline"
                size="sm"
                onClick={loadOlder}
                loading={loadingOlder}
                loadingText="Loading…"
                className="min-h-11"
              >
                Load older
              </Button>
            </div>
          )}
          <ol aria-label="Messages" className="mb-6 flex flex-col gap-3">
            {messages.map((message, index) => {
              // Ownership is the VIEWER's identity, not "whoever isn't the
              // other member" — a two-party shortcut a group thread breaks.
              // `username` is optional on the auth user; fall back to the
              // two-party rule only for a direct thread when it is absent.
              const mine = user?.username
                ? message.sender.username === user.username
                : !isGroup && message.sender.username !== otherUsername;
              const senderName = authorName(message.sender);
              // In a group, a run of messages from one member carries the
              // sender header once, on the first of the run.
              const previous = index > 0 ? messages[index - 1] : null;
              const showSender =
                isGroup && !mine && previous?.sender.username !== message.sender.username;
              const reported = reportedIds.has(message.id);
              return (
                <li
                  key={message.id}
                  className={`flex ${mine ? 'justify-end' : 'justify-start'}`}
                  data-mine={mine || undefined}
                >
                  <div className="max-w-[85%]">
                    {showSender && (
                      <div className="mb-1 flex items-center gap-2">
                        <Avatar
                          size="sm"
                          src={message.sender.avatar || specimenAvatar(message.sender.username)}
                          alt=""
                        />
                        <Link
                          to={userProfilePath(message.sender.username)}
                          className="text-body-sm font-medium text-ink-2 hover:text-primary hover:underline"
                        >
                          {senderName}
                        </Link>
                      </div>
                    )}
                    <div
                      className={`rounded-lg border px-4 py-2.5 ${
                        mine
                          ? 'border-primary/30 bg-primary/10 text-ink'
                          : 'border-line bg-surface-2 text-ink'
                      }`}
                    >
                      <span className="sr-only">{mine ? 'You:' : `${senderName}:`} </span>
                      {/* Plain text by contract — React escapes it; pre-wrap keeps
                          the author's line breaks. Never HTML here. */}
                      <p className="whitespace-pre-wrap break-words text-body-lg leading-relaxed">
                        {message.body}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center justify-between gap-x-3">
                        <span className="gt-label normal-case tracking-normal">
                          <Timestamp iso={message.created_at} prefix="Sent" />
                        </span>
                        {!mine &&
                          (reported ? (
                            <span className="gt-label italic">Reported</span>
                          ) : reportingId !== message.id ? (
                            <button
                              type="button"
                              onClick={() => setReportingId(message.id)}
                              className="min-h-11 px-2 py-1 text-xs text-ink-3 hover:text-error hover:bg-error/10 rounded-pill inline-flex items-center gap-1"
                              title="Report message"
                            >
                              <Flag className="h-3 w-3" aria-hidden="true" /> Report
                            </button>
                          ) : null)}
                      </div>
                      {!mine && !reported && reportingId === message.id && (
                        <MessageReportForm
                          messageId={message.id}
                          // Guard on the thread the report was issued for: a
                          // late failure must not land in another thread's
                          // notice region (same epoch rule as send/load).
                          getEpoch={() => requestEpochRef.current}
                          onSubmitted={() => {
                            setReportedIds((prev) => new Set(prev).add(message.id));
                            setReportingId(null);
                          }}
                          onCancel={() => setReportingId(null)}
                          onError={setNotice}
                        />
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        </>
      )}

      {/* Write-path notice. Persistent live region: always mounted so a text
          swap is announced; visually collapsed when empty. */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className={
          notice
            ? 'mb-4 rounded-md border border-line bg-surface-2 px-4 py-3 text-ink-2'
            : 'sr-only'
        }
      >
        {notice}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void handleSend();
        }}
        className="flex flex-col gap-2"
      >
        <label htmlFor="dm-composer" className="sr-only">
          Message
        </label>
        <textarea
          id="dm-composer"
          ref={composerRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleComposerKeyDown}
          maxLength={MESSAGE_MAX_LENGTH}
          rows={3}
          disabled={sending}
          placeholder={`Message ${name}…`}
          className="w-full rounded-md border border-line bg-surface-2/60 px-3 py-2 text-ink placeholder:text-ink-3 focus:border-transparent focus:ring-2 focus:ring-secondary focus:outline-none disabled:opacity-60"
        />
        <div className="flex items-center justify-between gap-3">
          <span className="font-mono text-micro text-ink-3">
            {`${draft.length}/${MESSAGE_MAX_LENGTH}`}
            <span className="hidden sm:inline"> · ⌘/Ctrl + Enter to send</span>
          </span>
          <Button
            type="submit"
            size="sm"
            loading={sending}
            loadingText="Sending…"
            disabled={sending || !draft.trim()}
          >
            Send
          </Button>
        </div>
      </form>

      {isGroup && (
        <ConfirmDialog
          open={leaveConfirmOpen}
          title="Leave this group?"
          message={`You'll no longer see ${conversation.title} or its messages. The creator can add you back.`}
          confirmLabel="Leave"
          onConfirm={() => void handleLeave()}
          onCancel={closeLeaveConfirm}
        />
      )}
    </div>
  );
}
