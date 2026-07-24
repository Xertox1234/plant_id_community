import { memo, useMemo } from 'react';
import { formatDistanceToNow } from 'date-fns';

interface TimestampProps {
  /** ISO 8601 timestamp string. */
  iso: string;
  className?: string;
  /**
   * Prefix for the accessible label, e.g. "Posted" → "Posted 3 May 2026, 14:02".
   * The absolute date is exposed to screen readers and touch users (who can't
   * hover a `title`); the visible text stays the short relative form.
   */
  prefix?: string;
}

/**
 * Timestamp
 *
 * Renders a relative time ("3 hours ago") inside a `<time datetime>` element,
 * with the absolute date reachable by every user — `title` for mouse hover and
 * `aria-label` for screen readers / touch (audit 2026-07-11 L12; a hover-only
 * `title` on a bare `<span>` is inaccessible to both).
 */
function Timestamp({ iso, className, prefix }: TimestampProps) {
  const formatted = useMemo(() => {
    const date = new Date(iso);
    if (isNaN(date.getTime())) return null;
    return {
      relative: formatDistanceToNow(date, { addSuffix: true }),
      absolute: date.toLocaleString(),
    };
  }, [iso]);

  if (!formatted) {
    return <span className={className}>recently</span>;
  }

  const label = prefix ? `${prefix} ${formatted.absolute}` : formatted.absolute;
  return (
    <time dateTime={iso} title={formatted.absolute} aria-label={label} className={className}>
      {formatted.relative}
    </time>
  );
}

export default memo(Timestamp);
