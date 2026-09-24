import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { MessageSquare, MessagesSquare } from 'lucide-react';
import Card from '../ui/Card';
import StatCard from '../ui/StatCard';
import Timestamp from '../ui/Timestamp';
import { fetchDashboardStats } from '../../services/profileService';
import type { DashboardStats } from '../../types/auth';

type StatsState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; stats: DashboardStats };

function StatsBody({ stats }: { stats: DashboardStats }) {
  const { forum_stats: forum, recent_activity: activity } = stats;

  if (forum.total_topics === 0 && forum.total_posts === 0 && activity.length === 0) {
    return (
      <p className="text-ink-2">
        You haven’t posted in the forum yet.{' '}
        <Link to="/forum" className="text-primary hover:underline">
          Visit the forum
        </Link>
      </p>
    );
  }

  return (
    <>
      <div className="grid grid-cols-2 gap-4">
        <StatCard
          icon={<MessagesSquare className="h-4 w-4" aria-hidden="true" />}
          value={forum.total_topics}
          label="Topics"
          sublabel={`${forum.topics_this_month} in the last 30 days`}
          tone="sage"
        />
        <StatCard
          icon={<MessageSquare className="h-4 w-4" aria-hidden="true" />}
          value={forum.total_posts}
          label="Posts"
          sublabel={`${forum.posts_this_month} in the last 30 days`}
          tone="pollen"
        />
      </div>

      {activity.length > 0 && (
        <Card className="mt-4 p-card">
          <h3 className="text-meta font-medium text-ink-2 mb-3">Recent activity</h3>
          <ul className="space-y-3">
            {activity.map((item) => (
              <li key={`${item.type}-${item.url}-${item.timestamp}`} className="min-w-0">
                <Link
                  to={item.url}
                  className="text-ink font-medium hover:text-primary hover:underline"
                >
                  {item.title}
                </Link>
                <p className="text-meta text-ink-3">
                  {item.description} · <Timestamp iso={item.timestamp} />
                </p>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

/**
 * The signed-in user's forum totals and recent activity on /profile, from
 * GET /api/v1/auth/me/dashboard-stats/ (todo 411). Loads independently of the
 * profile form, so a stats failure never blocks editing. Mount it keyed on the
 * user id so an account switch refetches.
 */
export default function ProfileStats() {
  const [state, setState] = useState<StatsState>({ kind: 'loading' });

  useEffect(() => {
    let cancelled = false;
    fetchDashboardStats()
      .then((stats) => {
        if (!cancelled) setState({ kind: 'ready', stats });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: 'error',
            message: error instanceof Error ? error.message : 'Could not load your activity.',
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section aria-labelledby="profile-activity-heading" className="mt-8">
      <h2 id="profile-activity-heading" className="text-lead font-semibold text-ink mb-4">
        Forum activity
      </h2>
      {state.kind === 'loading' && <p className="text-ink-3">Loading your activity…</p>}
      {state.kind === 'error' && (
        <p role="alert" className="text-error">
          {state.message}
        </p>
      )}
      {state.kind === 'ready' && <StatsBody stats={state.stats} />}
    </section>
  );
}
