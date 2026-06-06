// web/src/components/ui/GrainOverlay.tsx
import type { ReactNode } from 'react';

const NOISE =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E";

export interface GrainOverlayProps {
  children: ReactNode;
}

export default function GrainOverlay({ children }: GrainOverlayProps) {
  return (
    <div className="relative">
      <div
        data-testid="grain-overlay"
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-0 opacity-[0.04] mix-blend-multiply dark:mix-blend-screen"
        style={{ backgroundImage: `url("${NOISE}")` }}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
