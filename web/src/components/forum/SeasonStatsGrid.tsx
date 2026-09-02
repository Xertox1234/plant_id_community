import { Check, Flame, MessagesSquare, ScanSearch } from 'lucide-react';
import StatCard from '../ui/StatCard';
import type { ForumMyStats } from '@/types';

interface SeasonStatsGridProps {
  stats: ForumMyStats;
  /** Extra classes on the grid wrapper — callers own their own vertical rhythm. */
  className?: string;
}

/**
 * The "Your season" four-card grid for `GET me/stats/`.
 *
 * Extracted from CategoryListPage (todo 300) when HomePage grew the same row
 * (todo 315) — the cards' tone/label/sublabel rules are the presentation of
 * one API shape, so they live in one place rather than being copied per page.
 * Callers own the heading and the wrapper margin; this renders only the grid.
 */
export default function SeasonStatsGrid({ stats, className = '' }: SeasonStatsGridProps) {
  return (
    <div className={`grid grid-cols-2 gap-4 lg:grid-cols-4 ${className}`.trim()}>
      <StatCard
        icon={<ScanSearch className="h-4 w-4" aria-hidden="true" />}
        value={stats.identifications_shared}
        label="Identifications"
        // Badge progress (todo 300 AC2) lives on this card — its
        // value IS the badge's tracked metric, so no 5th slot is
        // needed in the fixed 4-card grid.
        sublabel={
          stats.badge_progress >= stats.badge_target
            ? `${stats.badge_name} badge complete`
            : `${stats.badge_target - stats.badge_progress} to ${stats.badge_name} badge`
        }
        tone="sage"
        progress={{
          value: stats.badge_progress,
          max: stats.badge_target,
          label: `${stats.badge_name} badge progress`,
        }}
      />
      <StatCard
        icon={<MessagesSquare className="h-4 w-4" aria-hidden="true" />}
        value={stats.posts}
        label="Posts"
        sublabel="all time"
        tone="pollen"
      />
      <StatCard
        icon={<Check className="h-4 w-4" aria-hidden="true" />}
        value={stats.solutions_accepted}
        label="Solutions"
        sublabel="accepted answers"
        tone="bloom"
      />
      <StatCard
        icon={<Flame className="h-4 w-4" aria-hidden="true" />}
        value={stats.streak_days}
        label="Day streak"
        sublabel={
          stats.streak_days === 0
            ? 'Post to start a streak'
            : stats.streak_days === 1
              ? 'day in a row'
              : 'days in a row'
        }
        tone="orchid"
      />
    </div>
  );
}
