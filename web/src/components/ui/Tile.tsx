import { HTMLAttributes, ReactNode } from 'react';
import { TILE_BOX, TILE_RADIUS, type TileSize } from './dimensions';

export type TileTone = 'sage' | 'pollen' | 'bloom' | 'orchid';

interface TileProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: TileTone;
  size?: TileSize;
  children?: ReactNode;
}

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
      className={`inline-grid flex-none place-items-center text-abyss ${TILE_BOX[size]} ${TILE_RADIUS[size]} ${className}`}
      style={{ background: `var(--gt-tile-${tone})`, ...style }}
      {...props}
    >
      {children}
    </span>
  );
}
