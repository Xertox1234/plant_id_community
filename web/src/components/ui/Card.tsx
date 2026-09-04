import { HTMLAttributes, ReactNode } from 'react';

export type CardRadius = 'md' | 'lg';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
  /** Hover-lift + border-brighten for clickable cards/rows. */
  interactive?: boolean;
  /**
   * Corner radius. A prop, not a `rounded-*` className override: the compiled
   * stylesheet emits `.rounded-lg` BEFORE `.rounded-md`, so an override on top
   * of the component's own `rounded-md` silently loses (verified against the
   * vite build, todo 333).
   */
  radius?: CardRadius;
}

const RADIUS: Record<CardRadius, string> = { md: 'rounded-md', lg: 'rounded-lg' };

export default function Card({
  children,
  interactive = false,
  radius = 'md',
  className = '',
  ...props
}: CardProps) {
  return (
    <div
      className={`canopy-card ${RADIUS[radius]} ${interactive ? 'canopy-interactive' : ''} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
