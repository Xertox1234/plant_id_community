import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Flag } from 'lucide-react';
import {
  fetchConversationWith,
  fetchMessages,
  reportMessage,
  sendMessage,
  MESSAGE_MAX_LENGTH,
} from '../../services/messageService';
import { ForumApiError } from '../../services/forumService';
import { useAuth } from '../../contexts/AuthContext';
import { useAnnounce } from '../../contexts/AnnouncerContext';
import { useUnreadNotifications } from '../../contexts/UnreadNotificationsContext';
import { specimenAvatar } from '../../utils/forumAvatars';
import { userProfilePath } from '../../utils/forumUrls';
import { logger } from '../../utils/logger';
import Avatar from '../../components/ui/Avatar';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import Timestamp from '../../components/ui/Timestamp';
import { AVATAR_BOX } from '../../components/ui/dimensions';
import ForumErrorState from '../../components/forum/ForumErrorState';
import { SkeletonBlock, SkeletonStatus } from '../../components/forum/ForumSkeleton';
import { REPORT_REASONS } from '../../components/forum/reportReasons';
import type { Conversation, DirectMessage } from '../../types/forum';

/** Shown for a 403 on send — either side has blocked the other. */
const BLOCKED_NOTICE = "You can't message this member.";

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
 * One direct-message thread (todo 339): `/messages/:username`.
 *
 * Resolves the conversation by the other member's username; a 404 (no thread
 * yet) is an EMPTY thread with the composer live, not an error — the first
 * send creates it. Messages arrive newest-first per page and are rendered
 * oldest→newest, so "Load older" prepends. Routed under ProtectedLayout.
 */
export default function ConversationPage() {
  const { username = '' } = useParams<{ username: string }>();
  const { user } = useAuth();
  const announce = useAnnounce();
  const { refresh: refreshUnread } = useUnreadNotifications();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<DirectMessage[]>([]);
  const [olderCursor, setOlderCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  // Write-path notice (send/report/load-older failures). Persistent live
  // region below, same shape as ThreadDetailPage's.
  const [notice, setNotice] = useState<string | null>(null);
  const [reportingId, setReportingId] = useState<number | null>(null);
  const [reportedIds, setReportedIds] = useState<ReadonlySet<number>>(() => new Set());
  // Monotonic request epoch: a response only lands if no navigation to
  // another member (or newer load) happened after it started.
  const requestEpochRef = useRef(0);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  // Bumped after a successful send; the effect below focuses the composer
  // once React has re-enabled it (focusing while `sending` still disables
  // the textarea is a no-op).
  const [focusRequest, setFocusRequest] = useState(0);
  useEffect(() => {
    if (focusRequest > 0) composerRef.current?.focus();
  }, [focusRequest]);

  // Reset synchronously when :username changes so the previous member's
  // thread never flashes under the new URL (same shape as UserProfilePage).
  const [renderedFor, setRenderedFor] = useState(username);
  if (renderedFor !== username) {
    setRenderedFor(username);
    setConversation(null);
    setMessages([]);
    setOlderCursor(null);
    setLoading(true);
    setError(null);
    setNotice(null);
    setDraft('');
    setReportingId(null);
    // In-flight flags too: load() below bumps the epoch, so a send / load-older
    // still running for the previous member never reaches its `finally` —
    // left alone they would pin the new thread's composer disabled forever.
    setSending(false);
    setLoadingOlder(false);
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
      const resolved = await fetchConversationWith(username);
      if (epoch !== requestEpochRef.current) return;
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
        context: { username },
      });
      setError(err instanceof Error ? err.message : 'Failed to load messages');
    } finally {
      if (epoch === requestEpochRef.current) setLoading(false);
    }
  }, [username, refreshUnread]);

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
        context: { username },
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
    setSending(true);
    setNotice(null);
    try {
      const sent = await sendMessage(requestUsername, body);
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
        context: { username: requestUsername },
      });
      // Branch on the STATUS, never the text: a 403 arrives as DRF's default
      // detail, which mentions neither "403" nor "forbidden".
      if (err instanceof ForumApiError && err.status === 403) {
        setNotice(BLOCKED_NOTICE);
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

  const other = conversation?.other_participant ?? null;
  const otherUsername = other?.username ?? username;
  const name = other?.display_name || otherUsername;

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

  return (
    <div className="max-w-3xl mx-auto p-6">
      <title>{`${name} · Messages · Houseplant MD`}</title>

      <Link to="/messages" className="gt-label mb-4 inline-block hover:text-primary">
        ← Messages
      </Link>

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
            {messages.map((message) => {
              // Ownership is the VIEWER's identity, not "whoever isn't the
              // other member" — a two-party shortcut that group threads
              // (todo 350) would break. `username` is optional on the auth
              // user; fall back to the two-party rule only when it is absent.
              const mine = user?.username
                ? message.sender.username === user.username
                : message.sender.username !== otherUsername;
              const reported = reportedIds.has(message.id);
              return (
                <li
                  key={message.id}
                  className={`flex ${mine ? 'justify-end' : 'justify-start'}`}
                  data-mine={mine || undefined}
                >
                  <div
                    className={`max-w-[85%] rounded-lg border px-4 py-2.5 ${
                      mine
                        ? 'border-primary/30 bg-primary/10 text-ink'
                        : 'border-line bg-surface-2 text-ink'
                    }`}
                  >
                    <span className="sr-only">{mine ? 'You:' : `${name}:`} </span>
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
                        // late failure must not land in another member's
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
    </div>
  );
}
