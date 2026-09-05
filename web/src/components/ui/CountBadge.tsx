interface CountBadgeProps {
  count: number;
  max?: number;
}

export default function CountBadge({ count, max = 99 }: CountBadgeProps) {
  if (count <= 0) return null;
  return (
    <span className="canopy-cta inline-grid h-5 min-w-5 place-items-center rounded-pill px-1.5 font-mono text-micro font-semibold">
      {count > max ? `${max}+` : count}
    </span>
  );
}
