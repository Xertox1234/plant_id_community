import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { fetchNotifications, markNotificationsRead } from '../../services/notificationService';
import { threadPath, postAnchor } from '../../utils/forumUrls';
import { useUnreadNotifications } from '../../contexts/UnreadNotificationsContext';
import type { ForumNotification } from '../../types/notifications';

// COPY HAS TWO HOMES (todo 287, 2026-07-31 - was three). The two BACKEND
// surfaces, the push tray and the email subject/body, now both read one table:
// backend/apps/forum_host/notification_copy.py. This bell is the remaining
// second home, deliberately: the frontend cannot import a Python table, so
// converging it means serving the label from the API rather than duplicating
// the table in TypeScript. That is not built.
//
// So: a wording change here still needs a matching edit in notification_copy.py
// (one file now, not two), and the strings still disagree by design - a reply
// reads 'Someone replied to "X"' here vs 'New reply in "X"' in the tray. If you
// are doing an i18n pass, serve these labels from the API instead of
// translating them twice.
function notificationLabel(notification: ForumNotification): string {
  const actorName = notification.actor?.display_name || notification.actor?.username || 'Someone';
  const topicTitle = notification.topic?.title || 'your topic';
  switch (notification.verb) {
    case 'mention':
      return `${actorName} mentioned you in "${topicTitle}"`;
    case 'quote':
      // Someone quoted one of your posts (todo 342). post_id is the QUOTING
      // post, so the deep link below lands on the quote, like a reply.
      return `${actorName} quoted your post in "${topicTitle}"`;
    case 'reply':
    default:
      return `${actorName} replied to "${topicTitle}"`;
  }
}

/**
 * Bell with unread-notification count and a dropdown list (todo 253 slice 1,
 * audit C2). Unread count comes from UnreadNotificationsContext (one shared
 * poll for the bell and the sidebar Forum badge); this component owns only
 * the dropdown list. Only ever mounted while authenticated — AppShell
 * conditionally renders it.
 */
export default function NotificationBell() {
  const navigate = useNavigate();
  const { unreadCount, decrement, clear } = useUnreadNotifications();
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<ForumNotification[]>([]);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [listError, setListError] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);

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
      clear();
    }
  };

  const handleSelectNotification = async (notification: ForumNotification) => {
    setIsOpen(false);
    if (!notification.read_at) {
      markNotificationsRead([notification.id]).catch(() => {
        /* best-effort — a missed mark-read just leaves it unread for next poll */
      });
      decrement();
    }
    if (notification.topic) {
      const { topic } = notification;
      navigate(
        threadPath(
          { id: String(topic.board_id), slug: topic.board_slug, name: topic.board_slug },
          { id: String(topic.id), slug: topic.slug, title: topic.title }
        ) + (notification.post_id != null ? postAnchor(notification.post_id) : '')
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
