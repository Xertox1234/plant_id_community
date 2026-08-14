import { Outlet } from 'react-router-dom';
import AppShell from './AppShell';

/** All routes render inside the Canopy AppShell (sidebar + topbar + rail). */
export default function RootLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
