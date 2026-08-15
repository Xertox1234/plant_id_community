import { HTMLAttributes, ReactNode } from 'react';

export type TileTone = 'sage' | 'pollen' | 'bloom' | 'orchid';

interface TileProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: TileTone;
  size?: 'sm' | 'md';
  children?: ReactNode;
}

const SIZES: Record<'sm' | 'md', string> = {
  sm: 'h-9 w-9 rounded-[11px]',
  md: 'h-[46px] w-[46px] rounded-[14px]',
};

export default function Tile({
  tone = 'sage',
  size = 'md',
  children,
  className = '',
  style,
  ...props
}: TileProps) {
  return (
    <span
      className={`inline-grid flex-none place-items-center text-abyss ${SIZES[size]} ${className}`}
      style={{ background: `var(--gt-tile-${tone})`, ...style }}
      {...props}
    >
      {children}
    </span>
  );
}
