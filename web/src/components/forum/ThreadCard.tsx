import { memo } from 'react';
import { Link } from 'react-router-dom';
import { Check, Eye, Lock, Pin, Reply } from 'lucide-react';
import Card from '../ui/Card';
import Timestamp from '../ui/Timestamp';
import { threadPath } from '../../utils/forumUrls';
import type { Thread } from '@/types';

interface ThreadCardProps {
  thread: Thread;
  compact?: boolean;
  /** Pass true for search results where author data is unavailable (sentinel). */
  hideAuthor?: boolean;
  /**
   * Filter the list by a tag (audit M5). When omitted the tags still render,
   * but as inert chips — used where there is no list to filter (search).
   */
  onTagClick?: (tag: string) => void;
  /** The tag currently filtering the list, so its chip can read as active. */
  activeTag?: string;
}

/**
 * ThreadCard — a Canopy topic row: gradient card, state chips, title in the
 * display face, excerpt, mono stat line. Tags sit OUTSIDE the row link
 * (nested anchors/buttons are invalid HTML — same contract as before).
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
    <Card
      interactive
      className={`${compact ? 'p-3.5' : 'p-card'} ${thread.is_locked ? 'opacity-75' : ''}`}
    >
      <Link to={threadUrl} viewTransition className="block">
        {(compact ||
          thread.is_pinned ||
          thread.is_locked ||
          thread.is_solved ||
          thread.is_unread) && (
          <div className="gt-label mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
            {compact && (
              <span>
                {thread.category.icon && (
                  <span className="mr-1" aria-hidden="true">
                    {thread.category.icon}
                  </span>
                )}
                {thread.category.name}
              </span>
            )}
            {thread.is_pinned && (
              <span className="inline-flex items-center gap-1 text-tertiary">
                <Pin className="h-3 w-3" aria-hidden="true" /> Pinned
              </span>
            )}
            {thread.is_locked && (
              <span className="inline-flex items-center gap-1">
                <Lock className="h-3 w-3" aria-hidden="true" /> Locked
              </span>
            )}
            {thread.is_solved && (
              <span className="inline-flex items-center gap-1 text-secondary">
                <Check className="h-3 w-3" aria-hidden="true" /> Solved
              </span>
            )}
            {thread.is_unread && <span className="font-semibold text-primary">New</span>}
          </div>
        )}

        <h3
          className={`gt-h3 text-ink ${compact ? 'mb-0.5' : 'mb-1.5'}`}
          style={{ viewTransitionName: `thread-${thread.id}` }}
        >
          {thread.title}
        </h3>

        {!compact && thread.excerpt && (
          <p className="line-clamp-2 max-w-prose text-sm leading-relaxed text-ink-2">
            {thread.excerpt}
          </p>
        )}

        <div
          className={`gt-label flex flex-wrap items-center gap-x-2 gap-y-1 ${compact ? 'mt-1' : 'mt-2.5'}`}
        >
          {!hideAuthor && (
            <>
              <span className="normal-case tracking-normal text-ink-2">
                {thread.author.display_name || thread.author.username}
              </span>
              <span aria-hidden="true">·</span>
            </>
          )}
          <span className="inline-flex items-center gap-1" title={`${thread.post_count} replies`}>
            <Reply className="h-3 w-3" aria-hidden="true" /> {thread.post_count || 0}
          </span>
          <span aria-hidden="true">·</span>
          <span className="inline-flex items-center gap-1" title={`${thread.view_count} views`}>
            <Eye className="h-3 w-3" aria-hidden="true" /> {thread.view_count || 0}
          </span>
          <span aria-hidden="true">·</span>
          <Timestamp iso={thread.last_activity_at} prefix="Last activity" />
        </div>
      </Link>

      {tags.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-2">
          {tags.map((tag) =>
            onTagClick ? (
              <button
                key={tag}
                type="button"
                onClick={() => onTagClick(tag)}
                aria-pressed={tag === activeTag}
                className={`gt-label inline-flex min-h-11 items-center rounded-pill border px-3 transition-colors ${
                  tag === activeTag
                    ? 'border-secondary/60 bg-secondary/15 text-ink'
                    : 'border-line bg-transparent hover:border-line-2 hover:bg-surface-2'
                }`}
              >
                #{tag}
              </button>
            ) : (
              <span
                key={tag}
                className="gt-label inline-flex items-center rounded-pill border border-line px-3 py-1"
              >
                #{tag}
              </span>
            )
          )}
        </div>
      )}
    </Card>
  );
}

export default memo(ThreadCard);
