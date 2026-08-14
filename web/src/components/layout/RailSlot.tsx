import { useEffect, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

export const RAIL_CONTAINER_ID = 'app-rail';

/** Portals page-provided content into the AppShell right rail.
 *  Mount-gated: the rail div exists only after AppShell commits. */
export default function RailSlot({ children }: { children: ReactNode }) {
  const [target, setTarget] = useState<HTMLElement | null>(null);
  useEffect(() => {
    setTarget(document.getElementById(RAIL_CONTAINER_ID));
  }, []);
  return target ? createPortal(children, target) : null;
}
