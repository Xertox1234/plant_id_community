import { memo } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, MessagesSquare, MousePointerClick, Reply } from 'lucide-react';
import Card from '../ui/Card';
import Tile from '../ui/Tile';
import Timestamp from '../ui/Timestamp';
import { categoryPath, forumLinkHref } from '../../utils/forumUrls';
import { boardIdentity } from '../../utils/forumTones';
import type { Forum, ForumLink } from '@/types';

interface ForumCardProps {
  forum: Forum;
  /**
   * The name's heading level. `h4` when the card sits under a category
   * header (`h3`) on the forum index, so the outline nests (todo 665).
   */
  headingLevel?: 'h3' | 'h4';
}

/**
 * ForumCard — a Canopy board row.
 *
 * Gradient card with the board's accent tile, name, description, and a mono
 * stat line. Subcategory chips sit OUTSIDE the row link (nested anchors are
 * invalid HTML).
 */
function ForumCard({ forum, headingLevel = 'h3' }: ForumCardProps) {
  const Heading = headingLevel;
  const hasChildren = !!(forum.children && forum.children.length > 0);
  const { tone, Icon } = boardIdentity(forum.slug);

  return (
    <Card interactive className="p-card">
      <Link to={categoryPath(forum)} viewTransition className="flex items-start gap-4">
        <Tile tone={tone} aria-hidden="true">
          {forum.icon ? (
            <span className="text-xl leading-none">{forum.icon}</span>
          ) : (
            <Icon className="h-5 w-5" />
          )}
        </Tile>
        <div className="min-w-0 flex-1">
          <Heading className="gt-h3 flex items-center gap-2 text-ink">
            {forum.name}
            {forum.has_unread && (
              // Unread marker (todo 671): a dot for the eye, words for a
              // screen reader.
              <span className="inline-flex items-center">
                <span aria-hidden="true" className="h-2 w-2 rounded-full bg-primary" />
                <span className="sr-only">Unread posts</span>
              </span>
            )}
          </Heading>
          {forum.description && (
            <p className="mt-1 line-clamp-2 max-w-prose text-sm leading-relaxed text-ink-2">
              {forum.description}
            </p>
          )}
          <div className="gt-label mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="inline-flex items-center gap-1">
              <MessagesSquare className="h-3 w-3" aria-hidden="true" />
              {forum.thread_count || 0} threads
            </span>
            <span aria-hidden="true">·</span>
            <span className="inline-flex items-center gap-1">
              <Reply className="h-3 w-3" aria-hidden="true" />
              {forum.post_count || 0} posts
            </span>
            <span aria-hidden="true">·</span>
            {forum.last_post_at ? (
              <Timestamp iso={forum.last_post_at} prefix="Last activity" />
            ) : (
              <span>No activity yet</span>
            )}
          </div>
        </div>
      </Link>

      {hasChildren && (
        <div className="mt-3 flex flex-wrap items-center gap-2 sm:pl-[62px]">
          <span className="gt-label">Subcategories</span>
          {forum.children.map((child) => (
            <Link
              key={child.id}
              to={categoryPath(child)}
              className="gt-label inline-flex min-h-11 items-center rounded-pill border border-line px-3 transition-colors hover:border-line-2 hover:bg-surface-2 hover:text-ink-2"
            >
              {child.icon && (
                <span className="mr-1" aria-hidden="true">
                  {child.icon}
                </span>
              )}
              {child.name}
            </Link>
          ))}
        </div>
      )}
    </Card>
  );
}

export default memo(ForumCard);

interface ForumLinkCardProps {
  link: ForumLink;
  headingLevel?: 'h3' | 'h4';
}

/**
 * ForumLinkCard — a link row (todo 670; phpBB's link forum). An external
 * link, never a router link: a tracked one goes through the backend's
 * counting redirect and shows its click count. `nofollow` keeps crawlers
 * from inflating the count; a URL that is not plain http(s) renders no
 * link at all.
 */
function ForumLinkCardImpl({ link, headingLevel = 'h3' }: ForumLinkCardProps) {
  const Heading = headingLevel;
  const href = forumLinkHref(link);
  const { tone } = boardIdentity(link.slug);
  const body = (
    <>
      <Tile tone={tone} aria-hidden="true">
        <ExternalLink className="h-5 w-5" />
      </Tile>
      <div className="min-w-0 flex-1">
        <Heading className="gt-h3 text-ink">{link.name}</Heading>
        {link.description && (
          <p className="mt-1 line-clamp-2 max-w-prose text-sm leading-relaxed text-ink-2">
            {link.description}
          </p>
        )}
        <div className="gt-label mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1">
          <span>External link</span>
          {link.track_clicks && link.click_count !== null && (
            <>
              <span aria-hidden="true">·</span>
              <span className="inline-flex items-center gap-1">
                <MousePointerClick className="h-3 w-3" aria-hidden="true" />
                {link.click_count} {link.click_count === 1 ? 'click' : 'clicks'}
              </span>
            </>
          )}
        </div>
      </div>
    </>
  );

  return (
    <Card interactive={!!href} className="p-card">
      {href ? (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="flex items-start gap-4"
        >
          {body}
        </a>
      ) : (
        <div className="flex items-start gap-4">{body}</div>
      )}
    </Card>
  );
}

export const ForumLinkCard = memo(ForumLinkCardImpl);
