import { ButtonHTMLAttributes, ReactNode } from 'react';

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  children: ReactNode;
}

export default function Chip({ active = false, children, className = '', ...props }: ChipProps) {
  const look = active
    ? 'canopy-cta font-semibold'
    : 'border border-line bg-surface-2/60 text-ink-2 hover:bg-surface-2 hover:text-ink';
  return (
    <button
      type="button"
      aria-pressed={active}
      className={`rounded-pill px-4 py-2 text-body-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary ${look} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
