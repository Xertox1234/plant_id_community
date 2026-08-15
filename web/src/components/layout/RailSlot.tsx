import { useEffect, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useMediaQuery } from '../../hooks/useMediaQuery';

export const RAIL_CONTAINER_ID = 'app-rail';
// Tailwind's default `xl` — must match the aside's `xl:flex` in AppShell.
export const RAIL_MEDIA_QUERY = '(min-width: 1280px)';

interface RailSlotProps {
  children: ReactNode;
}

/** Portals page-provided content into the AppShell right rail.
 *  Mount-gated twice: the rail div exists only after AppShell commits, and
 *  below the xl breakpoint the aside is display:none — children (and their
 *  data fetches, e.g. FromTheBlogModule's) must not mount at all there. */
export default function RailSlot({ children }: RailSlotProps) {
  const visible = useMediaQuery(RAIL_MEDIA_QUERY);
  const [target, setTarget] = useState<HTMLElement | null>(null);
  useEffect(() => {
    setTarget(document.getElementById(RAIL_CONTAINER_ID));
  }, []);
  return visible && target ? createPortal(children, target) : null;
}
