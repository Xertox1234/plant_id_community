import { Link } from 'react-router-dom';
import { Mail } from 'lucide-react';
import { useUnreadNotifications } from '../../contexts/UnreadNotificationsContext';

/**
 * Inbox entry point in the app shell (todo 339): an envelope beside the
 * notification bell with the unread-conversation badge. The count comes from
 * UnreadNotificationsContext — the same tick as the bell, never its own poll.
 * Only ever mounted while authenticated — AppShell conditionally renders it.
 */
export default function MessagesLink() {
  const { unreadConversations } = useUnreadNotifications();
  const badgeText = unreadConversations > 9 ? '9+' : String(unreadConversations);

  return (
    <Link
      to="/messages"
      aria-label={unreadConversations > 0 ? `Messages (${unreadConversations} unread)` : 'Messages'}
      title="Messages"
      className="relative inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-ink-2 hover:text-primary hover:bg-surface transition-colors"
    >
      <Mail className="w-5 h-5" aria-hidden="true" />
      {unreadConversations > 0 && (
        <span
          className="absolute top-0 right-0 flex items-center justify-center min-w-[1.1rem] h-[1.1rem] px-1 rounded-full bg-error text-on-error text-[0.65rem] font-medium leading-none"
          data-testid="messages-badge"
        >
          {badgeText}
        </span>
      )}
    </Link>
  );
}
