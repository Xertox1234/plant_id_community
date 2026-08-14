import { memo } from 'react';
import { Link } from 'react-router-dom';
import { threadPath } from '../../utils/forumUrls';
import Timestamp from '../ui/Timestamp';
import { IconCheck, IconEye, IconLock, IconPin, IconReply } from './ForumIcons';
import type { Thread } from '@/types';

interface ThreadCardProps {
  thread: Thread;
  compact?: boolean;
  /** Pass true for search results where author data is unavailable (sentinel). */
  hideAuthor?: boolean;
  /**
   * Filter the list by a tag (audit M5). When omitted the tags still render, but
   * as inert chips — used where there is no list to filter (e.g. search results).
   */
  onTagClick?: (tag: string) => void;
  /** The tag currently filtering the list, so its chip can read as active. */
  activeTag?: string;
}

/**
 * ThreadCard Component — a Field Notes ledger entry.
 *
 * One ruled entry per thread: a Geist Mono collection-label line (record №,
 * states, stats), the title in the display face, excerpt, and author line.
 * Rendered inside a `.wf-ledger` list on the board page and search results.
 */
function ThreadCard({
  thread,
  compact = false,
  hideAuthor = false,
  onTagClick,
  activeTag,
}: ThreadCardProps) {
  const threadUrl = threadPath(thread.category, thread);
  const tags = thread.tags ?? [];

  return (
    <div
      className={`
      wf-entry
      ${thread.is_pinned ? 'bg-tertiary/5' : ''}
      ${thread.is_locked ? 'opacity-75' : ''}
      ${compact ? 'px-2 py-3' : 'px-2 py-5'}
    `}
    >
      <Link to={threadUrl} viewTransition className="wf-entry-link block">
        {/* Collection-label line: record №, states, stats — the ledger's voice. */}
        <div className="wf-label flex flex-wrap items-center gap-x-2 gap-y-1 mb-1.5">
          <span className="wf-entry-no transition-colors">No. {thread.id}</span>
          {compact && (
            <>
              <span aria-hidden="true">·</span>
              <span>
                {thread.category.icon && (
                  <span className="mr-1" aria-hidden="true">
                    {thread.category.icon}
                  </span>
                )}
                {thread.category.name}
              </span>
            </>
          )}
          {thread.is_pinned && (
            <>
              <span aria-hidden="true">·</span>
              <span className="inline-flex items-center gap-1 text-clay">
                <IconPin size={12} /> Pinned
              </span>
            </>
          )}
          {thread.is_locked && (
            <>
              <span aria-hidden="true">·</span>
              <span className="inline-flex items-center gap-1">
                <IconLock size={12} /> Locked
              </span>
            </>
          )}
          {thread.is_solved && (
            <>
              <span aria-hidden="true">·</span>
              {/* Rendered in the primary token (AA on every palette), never the
                  invariant --gt-ok green, which fails contrast on dark themes. */}
              <span className="inline-flex items-center gap-1 text-primary">
                <IconCheck size={12} /> Solved
              </span>
            </>
          )}
          {thread.is_unread && (
            <>
              <span aria-hidden="true">·</span>
              <span className="font-medium text-primary">New</span>
            </>
          )}
          <span aria-hidden="true">·</span>
          <span className="inline-flex items-center gap-1" title={`${thread.post_count} replies`}>
            <IconReply size={12} /> {thread.post_count || 0}
          </span>
          <span aria-hidden="true">·</span>
          <span className="inline-flex items-center gap-1" title={`${thread.view_count} views`}>
            <IconEye size={12} /> {thread.view_count || 0}
          </span>
          <span aria-hidden="true">·</span>
          <Timestamp iso={thread.last_activity_at} prefix="Last activity" />
        </div>

        {/* Thread Title */}
        <h3
          className={`wf-title wf-entry-title text-ink transition-colors ${compact ? 'mb-0.5' : 'mb-1.5'}`}
          style={{ viewTransitionName: `thread-${thread.id}` }}
        >
          {thread.title}
        </h3>

        {/* Excerpt (not in compact mode) */}
        {!compact && thread.excerpt && (
          <p className="text-ink-2 text-sm leading-relaxed line-clamp-2 max-w-prose">
            {thread.excerpt}
          </p>
        )}

        {/* Author — omitted for search results where no real author data exists.
            The whole entry is already a <Link>, so the name stays plain text — a
            nested <a> is invalid HTML. Clickable author links live on PostCard. */}
        {!hideAuthor && (
          <p className={`text-xs text-ink-3 ${compact ? 'mt-0.5' : 'mt-2'}`}>
            started by{' '}
            <span className="font-medium text-ink-2">
              {thread.author.display_name || thread.author.username}
            </span>
          </p>
        )}
      </Link>

      {/* Tags (audit M5) — deliberately OUTSIDE the entry-level <Link>: a nested
          <a>/<button> inside an anchor is invalid HTML (the browser auto-closes
          the outer one) and breaks getByRole('link'). Chips are buttons only
          when the parent can actually filter; otherwise they are inert text. */}
      {tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {tags.map((tag) =>
            onTagClick ? (
              <button
                key={tag}
                type="button"
                onClick={() => onTagClick(tag)}
                aria-pressed={tag === activeTag}
                className={`wf-label inline-flex min-h-11 items-center rounded-full border px-3 transition-colors ${
                  tag === activeTag
                    ? 'border-primary/50 bg-primary/10 text-primary'
                    : 'border-line bg-transparent hover:border-line-2 hover:bg-surface-2'
                }`}
              >
                #{tag}
              </button>
            ) : (
              <span
                key={tag}
                className="wf-label inline-flex items-center rounded-full border border-line px-3 py-1"
              >
                #{tag}
              </span>
            )
          )}
        </div>
      )}
    </div>
  );
}

export default memo(ThreadCard);
