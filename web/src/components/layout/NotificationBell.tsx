import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import {
  fetchNotifications,
  fetchUnreadCount,
  markNotificationsRead,
} from '../../services/notificationService';
import { threadPath } from '../../utils/forumUrls';
import type { ForumNotification } from '../../types/notifications';

// Generous relative to the backend's 120/m rate limit on this endpoint — this
// exists to keep the bell feeling live, not to approach the abuse boundary.
const UNREAD_POLL_INTERVAL_MS = 30_000;

function notificationLabel(notification: ForumNotification): string {
  const actorName = notification.actor?.display_name || notification.actor?.username || 'Someone';
  const topicTitle = notification.topic?.title || 'your topic';
  switch (notification.verb) {
    case 'mention':
      return `${actorName} mentioned you in "${topicTitle}"`;
    case 'reply':
    default:
      return `${actorName} replied to "${topicTitle}"`;
  }
}

/**
 * Bell with unread-notification count and a dropdown list (todo 253 slice 1,
 * audit C2). Only ever mounted while authenticated — Header.tsx conditionally
 * renders it, so mount/unmount naturally starts/stops polling.
 */
export default function NotificationBell() {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<ForumNotification[]>([]);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [listError, setListError] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshUnreadCount = useCallback(() => {
    fetchUnreadCount()
      .then(setUnreadCount)
      .catch(() => {
        /* transient poll failure — next tick retries; nothing user-actionable */
      });
  }, []);

  // Poll unread count on an interval — useRef for the timer id, not useState
  // (CLAUDE.md gotcha: useState re-renders + recreates the callback + leaks
  // the timer on unmount).
  useEffect(() => {
    refreshUnreadCount();
    pollTimerRef.current = setInterval(refreshUnreadCount, UNREAD_POLL_INTERVAL_MS);
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [refreshUnreadCount]);

  // Lazy-load the list only when the dropdown is actually opened. Guarded by
  // a cancelled flag: rapidly closing/reopening the dropdown must not let a
  // stale in-flight response overwrite a fresher one.
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setIsLoadingList(true);
    setListError(false);
    fetchNotifications()
      .then((data) => {
        if (!cancelled) setNotifications(data.results);
      })
      .catch(() => {
        if (!cancelled) {
          setNotifications([]);
          setListError(true);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingList(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (bellRef.current && !bellRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsOpen(false);
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleEscape);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
        document.removeEventListener('keydown', handleEscape);
      };
    }
  }, [isOpen]);

  const handleMarkAllRead = async () => {
    const updated = await markNotificationsRead().catch(() => 0);
    if (updated > 0) {
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, read_at: n.read_at || new Date().toISOString() }))
      );
      setUnreadCount(0);
    }
  };

  const handleSelectNotification = async (notification: ForumNotification) => {
    setIsOpen(false);
    if (!notification.read_at) {
      markNotificationsRead([notification.id]).catch(() => {
        /* best-effort — a missed mark-read just leaves it unread for next poll */
      });
      setUnreadCount((prev) => Math.max(0, prev - 1));
    }
    if (notification.topic) {
      const { topic } = notification;
      navigate(
        threadPath(
          { id: String(topic.board_id), slug: topic.board_slug, name: topic.board_slug },
          { id: String(topic.id), slug: topic.slug, title: topic.title }
        )
      );
    }
  };

  const badgeText = unreadCount > 9 ? '9+' : String(unreadCount);

  return (
    <div className="relative" ref={bellRef}>
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-label={unreadCount > 0 ? `Notifications (${unreadCount} unread)` : 'Notifications'}
        aria-expanded={isOpen}
        aria-haspopup="true"
        className="relative p-2 rounded-lg text-ink-2 hover:text-primary hover:bg-surface transition-colors"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span
            className="absolute top-0 right-0 flex items-center justify-center min-w-[1.1rem] h-[1.1rem] px-1 rounded-full bg-error text-on-error text-[0.65rem] font-medium leading-none"
            data-testid="notification-badge"
          >
            {badgeText}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          role="region"
          aria-label="Notifications"
          className="absolute right-0 mt-2 w-80 max-w-[calc(100vw-2rem)] bg-surface-2 rounded-lg shadow-lg border border-line py-2 z-50"
        >
          <div className="flex items-center justify-between px-4 py-2 border-b border-line">
            <p className="text-sm font-medium text-ink">Notifications</p>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAllRead}
                className="min-h-[44px] min-w-[44px] px-2 text-xs text-primary hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {isLoadingList && <p className="px-4 py-3 text-sm text-ink-3">Loading…</p>}
            {!isLoadingList && listError && (
              <p className="px-4 py-3 text-sm text-error">Couldn't load notifications.</p>
            )}
            {!isLoadingList && !listError && notifications.length === 0 && (
              <p className="px-4 py-3 text-sm text-ink-3">No notifications yet.</p>
            )}
            {!isLoadingList &&
              !listError &&
              notifications.map((notification) => (
                <button
                  key={notification.id}
                  type="button"
                  onClick={() => handleSelectNotification(notification)}
                  className={`block w-full text-left px-4 py-3 text-sm hover:bg-surface transition-colors ${
                    notification.read_at ? 'text-ink-3' : 'text-ink font-medium'
                  }`}
                >
                  <p>{notificationLabel(notification)}</p>
                  <p className="text-xs text-ink-3 mt-0.5">
                    {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true })}
                  </p>
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
