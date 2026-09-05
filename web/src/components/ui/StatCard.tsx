import type { ReactNode } from 'react';
import Card from './Card';
import Tile, { type TileTone } from './Tile';
import ProgressBar from './ProgressBar';

interface StatCardProps {
  icon: ReactNode;
  value: ReactNode;
  label: string;
  sublabel?: string;
  tone?: TileTone;
  // `label` is used as the accessible name when a caller doesn't need to
  // describe the bar more specifically than the card itself (e.g. a
  // progress bar toward a differently-named badge threshold).
  progress?: { value: number; max: number; label?: string };
}

export default function StatCard({
  icon,
  value,
  label,
  sublabel,
  tone = 'sage',
  progress,
}: StatCardProps) {
  return (
    <Card className="flex flex-col gap-3 p-card">
      <Tile tone={tone} size="sm">
        {icon}
      </Tile>
      <div>
        <div className="font-mono text-[22px] tracking-tight tabular-nums">{value}</div>
        <div className="text-meta font-medium">{label}</div>
        {sublabel && <div className="text-micro text-ink-3">{sublabel}</div>}
      </div>
      {progress && (
        <ProgressBar
          value={progress.value}
          max={progress.max}
          tone={tone}
          label={progress.label ?? label}
        />
      )}
    </Card>
  );
}
