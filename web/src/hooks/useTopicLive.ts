import { useEffect, useRef, useState } from 'react';
import { openTopicLive } from '../services/forumLiveSocket';
import type { LiveEvent, LiveStatus } from '../types/forumLive';

interface UseTopicLiveOptions {
  topicId: number | null;
  enabled: boolean;
  onEvent: (event: LiveEvent) => void;
  /** Every (re)open — the page runs its one catch-up read here. */
  onOpen: () => void;
}

/**
 * Bind the live topic socket to a component (forum live replies, slice 3).
 * The socket reopens only when `topicId` or `enabled` changes; the callbacks
 * ride in refs, so a new function each render never reconnects. Disabled, a
 * null topic, or unmount closes it.
 */
export function useTopicLive({ topicId, enabled, onEvent, onOpen }: UseTopicLiveOptions): {
  status: LiveStatus;
  connected: boolean;
} {
  const [status, setStatus] = useState<LiveStatus>('off');
  const onEventRef = useRef(onEvent);
  const onOpenRef = useRef(onOpen);

  useEffect(() => {
    onEventRef.current = onEvent;
    onOpenRef.current = onOpen;
  }, [onEvent, onOpen]);

  useEffect(() => {
    if (!enabled || topicId == null) return;
    const live = openTopicLive(topicId, {
      onEvent: (event) => onEventRef.current(event),
      onOpen: () => onOpenRef.current(),
      onStatus: setStatus,
    });
    return () => live.close();
  }, [topicId, enabled]);

  const effective: LiveStatus = enabled && topicId != null ? status : 'off';
  return { status: effective, connected: effective === 'live' };
}
