/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { fetchUnreadCount } from '../services/notificationService';
import { fetchUnreadConversationCount } from '../services/messageService';
import { useAuth } from './AuthContext';

// Generous relative to the backend's 120/m rate limit on this endpoint — the
// bell and the sidebar badge share THIS one poll (moved here from
// NotificationBell so a second consumer never means a second request stream).
// The DM inbox badge (todo 339) rides the SAME tick: one interval, two
// requests, never a second poll stream.
export const UNREAD_POLL_INTERVAL_MS = 30_000;

interface UnreadNotificationsValue {
  unreadCount: number;
  /** Conversations with unread direct messages (todo 339) — the inbox badge. */
  unreadConversations: number;
  refresh: () => void;
  decrement: () => void;
  clear: () => void;
}

const noop = () => {};
const UnreadNotificationsContext = createContext<UnreadNotificationsValue>({
  unreadCount: 0,
  unreadConversations: 0,
  refresh: noop,
  decrement: noop,
  clear: noop,
});

interface UnreadNotificationsProviderProps {
  children: ReactNode;
}

export function UnreadNotificationsProvider({ children }: UnreadNotificationsProviderProps) {
  const { isAuthenticated } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);
  const [unreadConversations, setUnreadConversations] = useState(0);
  // useRef for the timer id, not useState (CLAUDE.md gotcha: useState
  // re-renders + recreates the callback + leaks the timer on unmount).
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Monotonic request epoch: a response only lands if no logout (or newer
  // request) happened after it started — otherwise a fetch in flight during
  // logout repaints a phantom badge after the reset below.
  const requestEpochRef = useRef(0);

  const refresh = useCallback(() => {
    if (!isAuthenticated) return;
    const epoch = ++requestEpochRef.current;
    // allSettled, not all: the two counts are independent, so one endpoint
    // failing must not blank the other's badge for a whole poll interval.
    // A transient failure on either side just retries next tick.
    Promise.allSettled([fetchUnreadCount(), fetchUnreadConversationCount()]).then(
      ([notifications, conversations]) => {
        if (epoch !== requestEpochRef.current) return;
        if (notifications.status === 'fulfilled') setUnreadCount(notifications.value);
        if (conversations.status === 'fulfilled') setUnreadConversations(conversations.value);
      }
    );
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) {
      // Invalidate any in-flight response BEFORE zeroing, or its .then would
      // re-set the count after this reset.
      requestEpochRef.current++;
      setUnreadCount(0);
      setUnreadConversations(0);
      return;
    }
    refresh();
    // Hidden tabs skip the fetch — no point polling a badge nobody can see;
    // the visibility listener refreshes immediately on return instead.
    pollTimerRef.current = setInterval(() => {
      if (!document.hidden) refresh();
    }, UNREAD_POLL_INTERVAL_MS);
    const handleVisibilityChange = () => {
      if (!document.hidden) refresh();
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [isAuthenticated, refresh]);

  // Local mutations follow the same rule as the logout reset above: bump the
  // epoch BEFORE setting, or a poll response already in flight repaints the
  // count the user just cleared (for up to a full poll interval). Tradeoff:
  // the discarded response means the badge can lag server truth until the
  // next tick — correct-but-stale beats resurrecting a dismissed badge.
  // Tradeoff of the shared epoch: a mark-read/clear also discards an
  // in-flight COMBINED response, so the DM count can lag one poll interval
  // after a notification action. Accepted — the alternative is a second
  // epoch (and a second failure surface) for a badge that self-corrects.
  const decrement = useCallback(() => {
    requestEpochRef.current++;
    setUnreadCount((prev) => Math.max(0, prev - 1));
  }, []);
  const clear = useCallback(() => {
    requestEpochRef.current++;
    setUnreadCount(0);
  }, []);

  const value = useMemo(
    () => ({ unreadCount, unreadConversations, refresh, decrement, clear }),
    [unreadCount, unreadConversations, refresh, decrement, clear]
  );

  return (
    <UnreadNotificationsContext.Provider value={value}>
      {children}
    </UnreadNotificationsContext.Provider>
  );
}

export function useUnreadNotifications(): UnreadNotificationsValue {
  return useContext(UnreadNotificationsContext);
}
