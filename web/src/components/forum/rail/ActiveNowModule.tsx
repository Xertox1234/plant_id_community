import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Zap } from 'lucide-react';
import RailModule from '../../ui/RailModule';
import Tile from '../../ui/Tile';
import Timestamp from '../../ui/Timestamp';
import { fetchRecentTopics } from '../../../services/forumService';
import { recentTopicPath } from '../../../utils/forumUrls';
import { boardIdentity } from '../../../utils/forumTones';
import { logger } from '../../../utils/logger';
import type { RecentTopic } from '@/types';

/** The module's own display cap — enforced regardless of source (controller Ruling 3). */
const RAIL_TOPIC_LIMIT = 3;

interface ActiveNowModuleProps {
  /**
   * Pre-fetched rows from a page that already calls `fetchRecentTopics`
   * (e.g. CategoryListPage, which shares one fetch with this module rather
   * than duplicating the request) — always re-sliced to `RAIL_TOPIC_LIMIT`
   * rather than trusted as-is, so a caller passing more than 3 rows still
   * renders at most 3. When omitted, the module fetches its own (smaller) page.
   */
  topics?: RecentTopic[];
}

/**
 * Right-rail module: the most recently active topics.
 *
 * Self-hides while loading, on error, and when there are none — same
 * fetch/ignore/self-hide shape as `FromTheBlogModule`. Replaces the old
 * board-based "Active now" block on CategoryListPage.
 */
export default function ActiveNowModule({ topics: providedTopics }: ActiveNowModuleProps) {
  const [fetchedTopics, setFetchedTopics] = useState<RecentTopic[]>([]);

  useEffect(() => {
    if (providedTopics) return;
    let ignore = false;
    fetchRecentTopics(RAIL_TOPIC_LIMIT)
      .then((rows) => {
        if (!ignore) setFetchedTopics(rows);
      })
      .catch((err) => {
        logger.error('Error loading active-now rail', {
          component: 'ActiveNowModule',
          error: err,
        });
      });
    return () => {
      ignore = true;
    };
  }, [providedTopics]);

  const topics = (providedTopics ?? fetchedTopics).slice(0, RAIL_TOPIC_LIMIT);

  if (topics.length === 0) return null;

  return (
    <RailModule icon={<Zap aria-hidden="true" />} title="Active now">
      <ul className="flex flex-col gap-3">
        {topics.map((t) => {
          const { Icon, tone } = boardIdentity(t.board.slug, t.board.name);
          return (
            <li key={t.id}>
              <Link to={recentTopicPath(t)} className="group flex items-start gap-2.5">
                {t.thumbnail_url ? (
                  <img
                    src={t.thumbnail_url}
                    alt=""
                    className="h-10 w-10 flex-none rounded-sm border border-line object-cover"
                  />
                ) : (
                  <Tile tone={tone} size="sm" aria-hidden="true">
                    <Icon className="h-4 w-4" />
                  </Tile>
                )}
                <span className="min-w-0">
                  <span className="block text-meta leading-snug font-medium text-ink transition-colors group-hover:text-primary">
                    {t.title}
                  </span>
                  <span className="gt-label mt-0.5 block normal-case tracking-normal">
                    {t.reply_count} {t.reply_count === 1 ? 'reply' : 'replies'}
                    {t.last_post_at && (
                      <>
                        {' '}
                        · <Timestamp iso={t.last_post_at} />
                      </>
                    )}
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </RailModule>
  );
}
