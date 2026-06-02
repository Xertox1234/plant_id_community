// web/src/components/ui/Eyebrow.tsx
import type { ReactNode } from 'react';

export default function Eyebrow({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <p
      className={`font-sans font-semibold uppercase text-ink-3 text-[11px] leading-[1.4] tracking-[0.66px] ${className}`}
    >
      {children}
    </p>
  );
}
