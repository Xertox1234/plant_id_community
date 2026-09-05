import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../ui/Card';
import Tile from '../ui/Tile';
import Timestamp from '../ui/Timestamp';
import SeasonStatsGrid from '../forum/SeasonStatsGrid';
import { fetchMyStats, fetchRecentTopics } from '../../services/forumService';
import { recentTopicPath } from '../../utils/forumUrls';
import { boardIdentity } from '../../utils/forumTones';
import { logger } from '../../utils/logger';
import type { ForumMyStats, RecentTopic } from '@/types';

/** How many community rows Home shows. Display-only; the rail's own cap is separate. */
const HOME_RECENT_TOPIC_LIMIT = 5;

/**
 * Home's logged-in activity feed (todo 315).
 *
 * Composes two endpoints that already exist and are already rendered on the
 * forum landing page — `GET me/stats/` and `GET topics/recent/` — rather than
 * introducing a new cross-domain aggregation endpoint (the todo's AC3: "no new
 * backend work"). HomePage mounts this only for authenticated visitors, so an
 * anonymous Home issues no extra requests at all and renders exactly the page
 * Canopy PR 4 shipped.
 *
 * Every section self-hides on empty or on failure: this is a nice-to-have on
 * top of the marketing page, never a dependency of it, so neither fetch may
 * surface an error state or a spinner on Home. Same fetch/ignore/self-hide
 * shape as the forum rail modules.
 */
export default function HomeActivity() {
  const [stats, setStats] = useState<ForumMyStats | null>(null);
  const [topics, setTopics] = useState<RecentTopic[]>([]);

  useEffect(() => {
    // react.dev's prescribed race guard: a response that arrives after unmount
    // is dropped instead of setting state.
    let ignore = false;

    fetchMyStats()
      .then((rows) => {
        if (!ignore) setStats(rows);
      })
      .catch((err) => {
        if (ignore) return;
        logger.error('Error loading home stats', { component: 'HomeActivity', error: err });
        setStats(null);
      });

    fetchRecentTopics(HOME_RECENT_TOPIC_LIMIT)
      .then((rows) => {
        if (!ignore) setTopics(rows);
      })
      .catch((err) => {
        if (ignore) return;
        logger.error('Error loading home recent topics', {
          component: 'HomeActivity',
          error: err,
        });
        setTopics([]);
      });

    return () => {
      ignore = true;
    };
  }, []);

  // Both halves empty (still loading, both failed, or a brand-new install with
  // no forum activity) — render nothing rather than an empty shell.
  if (!stats && topics.length === 0) return null;

  return (
    <section className="flex flex-col gap-6">
      {stats && (
        <div>
          <h2 className="gt-h3">Your season</h2>
          <SeasonStatsGrid stats={stats} className="mt-4" />
        </div>
      )}

      {topics.length > 0 && (
        <div>
          <div className="flex items-baseline justify-between gap-4">
            <h2 className="gt-h3">Active now</h2>
            <Link to="/forum" className="text-sm font-medium text-primary">
              All discussions →
            </Link>
          </div>
          <Card className="mt-4 p-card">
            <ul className="flex flex-col gap-4">
              {topics.slice(0, HOME_RECENT_TOPIC_LIMIT).map((t) => {
                const { Icon, tone } = boardIdentity(t.board.slug, t.board.name);
                return (
                  <li key={t.id}>
                    {/* One link per row: the whole row is the anchor, so nothing
                        inside it may be a link of its own (invalid nested <a>). */}
                    <Link to={recentTopicPath(t)} className="group flex items-start gap-3">
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
                        <span className="block text-sm leading-snug font-medium text-ink transition-colors group-hover:text-primary">
                          {t.title}
                        </span>
                        <span className="gt-label mt-0.5 block normal-case tracking-normal">
                          {t.board.name} · {t.reply_count}{' '}
                          {t.reply_count === 1 ? 'reply' : 'replies'}
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
          </Card>
        </div>
      )}
    </section>
  );
}
