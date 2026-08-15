import { HTMLAttributes, ReactNode } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
  /** Hover-lift + border-brighten for clickable cards/rows. */
  interactive?: boolean;
}

export default function Card({
  children,
  interactive = false,
  className = '',
  ...props
}: CardProps) {
  return (
    <div
      className={`canopy-card rounded-md ${interactive ? 'canopy-interactive' : ''} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
