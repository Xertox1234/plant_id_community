import type { TileTone } from './Tile';

interface ProgressBarProps {
  value: number;
  max: number;
  tone?: TileTone;
  /** Accessible name for the bar. */
  label: string;
}

export default function ProgressBar({ value, max, tone = 'sage', label }: ProgressBarProps) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      className="h-[5px] overflow-hidden rounded-pill bg-line"
    >
      <span
        className="block h-full rounded-pill"
        style={{ width: `${pct}%`, background: `var(--gt-tile-${tone})` }}
      />
    </div>
  );
}
