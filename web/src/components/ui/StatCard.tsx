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
  progress?: { value: number; max: number };
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
        <div className="text-[12.5px] font-medium">{label}</div>
        {sublabel && <div className="text-[11.5px] text-ink-3">{sublabel}</div>}
      </div>
      {progress && (
        <ProgressBar value={progress.value} max={progress.max} tone={tone} label={label} />
      )}
    </Card>
  );
}
