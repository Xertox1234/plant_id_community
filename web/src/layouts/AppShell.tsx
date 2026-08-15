import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';
import {
  Activity,
  BookOpen,
  Home,
  LogIn,
  LogOut,
  Menu,
  MessagesSquare,
  Moon,
  Plus,
  ScanSearch,
  Search,
  Settings as SettingsIcon,
  Sprout,
  Sun,
  X,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import {
  UnreadNotificationsProvider,
  useUnreadNotifications,
} from '../contexts/UnreadNotificationsContext';
import NotificationBell from '../components/layout/NotificationBell';
import UserMenu from '../components/layout/UserMenu';
import { RAIL_CONTAINER_ID } from '../components/layout/RailSlot';
import BrandMark from '../components/ui/BrandMark';
import CountBadge from '../components/ui/CountBadge';

const NAV = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/identify', label: 'Identify', icon: ScanSearch, end: false },
  { to: '/forum', label: 'Forum', icon: MessagesSquare, end: false },
  { to: '/blog', label: 'Blog', icon: BookOpen, end: false },
  { to: '/my-plants', label: 'My garden', icon: Sprout, end: false },
  { to: '/diagnose', label: 'Diagnose', icon: Activity, end: false },
];

function navClass({ isActive }: { isActive: boolean }) {
  return `flex items-center gap-2.5 rounded-md px-3 py-2 text-[13.5px] font-medium transition-colors ${
    isActive ? 'app-nav-active' : 'text-ink-2 hover:bg-surface-2/70 hover:text-ink'
  }`;
}

interface NavItemsProps {
  onNavigate?: () => void;
}
function NavItems({ onNavigate }: NavItemsProps) {
  const { unreadCount } = useUnreadNotifications();
  return (
    <>
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate} className={navClass}>
          <Icon className="h-[17px] w-[17px] opacity-85" aria-hidden="true" />
          {label}
          {to === '/forum' && unreadCount > 0 && (
            <span className="ml-auto" aria-label={`${unreadCount} unread notifications`}>
              <CountBadge count={unreadCount} />
            </span>
          )}
        </NavLink>
      ))}
    </>
  );
}

interface SideFootProps {
  onNavigate?: () => void;
}
function SideFoot({ onNavigate }: SideFootProps) {
  const { isAuthenticated, logout } = useAuth();
  const handleLogout = async () => {
    await logout();
    onNavigate?.();
  };
  return (
    <nav aria-label="Account" className="mt-auto flex flex-col gap-0.5">
      <NavLink to="/settings" onClick={onNavigate} className={navClass}>
        <SettingsIcon className="h-[17px] w-[17px] opacity-85" aria-hidden="true" />
        Settings
      </NavLink>
      {isAuthenticated ? (
        <button
          onClick={handleLogout}
          className="flex items-center gap-2.5 rounded-md px-3 py-2 text-left text-[13.5px] font-medium text-ink-2 transition-colors hover:bg-surface-2/70 hover:text-ink"
        >
          <LogOut className="h-[17px] w-[17px] opacity-85" aria-hidden="true" />
          Log out
        </button>
      ) : (
        <NavLink to="/login" onClick={onNavigate} className={navClass}>
          <LogIn className="h-[17px] w-[17px] opacity-85" aria-hidden="true" />
          Log in
        </NavLink>
      )}
    </nav>
  );
}

interface BrandProps {
  onNavigate?: () => void;
}
function Brand({ onNavigate }: BrandProps) {
  return (
    <Link
      to="/"
      onClick={onNavigate}
      className="flex items-center gap-2.5 px-2"
      aria-label="Houseplant MD home"
    >
      <BrandMark size={34} />
      <span className="text-[14.5px] leading-tight font-semibold text-ink">
        Houseplant MD
        <small className="block font-mono text-[9.5px] tracking-[0.14em] text-ink-3 uppercase">
          The plant clinic
        </small>
      </span>
    </Link>
  );
}

interface AppShellProps {
  children: ReactNode;
}
export default function AppShell({ children }: AppShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { isAuthenticated } = useAuth();
  const { mode, toggleMode } = useTheme();
  const themeLabel = mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
  const closeDrawer = () => setDrawerOpen(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Escape closes the drawer.
  useEffect(() => {
    if (!drawerOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeDrawer();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [drawerOpen]);

  // Body scroll lock while the drawer is open.
  useEffect(() => {
    if (!drawerOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [drawerOpen]);

  // Initial focus: send focus to the drawer's close button when it opens.
  useEffect(() => {
    if (drawerOpen) closeButtonRef.current?.focus();
  }, [drawerOpen]);

  return (
    <UnreadNotificationsProvider>
      <div className="min-h-screen">
        <div className="canopy-ground" aria-hidden="true" />
        <a href="#main-content" className="skip-nav">
          Skip to main content
        </a>
        <div className="app-shell mx-auto flex min-h-screen w-full max-w-[1500px]">
          {/* Sidebar (desktop) */}
          <aside className="sticky top-0 hidden h-screen w-[236px] flex-none flex-col gap-6 border-r border-line bg-surface px-3.5 py-5 md:flex">
            <Brand />
            <nav aria-label="Main" className="flex flex-col gap-0.5">
              <NavItems />
            </nav>
            <SideFoot />
          </aside>

          {/* Mobile drawer */}
          {drawerOpen && (
            <div className="fixed inset-0 z-50 md:hidden">
              <div
                className="absolute inset-0 bg-abyss/70"
                onClick={closeDrawer}
                aria-hidden="true"
              />
              <aside
                role="dialog"
                aria-modal="true"
                aria-label="Menu"
                className="absolute inset-y-0 left-0 flex w-[260px] flex-col gap-6 border-r border-line bg-surface px-3.5 py-5"
              >
                <div className="flex items-center justify-between">
                  <Brand onNavigate={closeDrawer} />
                  <button
                    ref={closeButtonRef}
                    onClick={closeDrawer}
                    aria-label="Close menu"
                    className="rounded-md p-2 text-ink-3 hover:bg-surface-2"
                  >
                    <X className="h-5 w-5" aria-hidden="true" />
                  </button>
                </div>
                <nav aria-label="Main" className="flex flex-col gap-0.5">
                  <NavItems onNavigate={closeDrawer} />
                </nav>
                <SideFoot onNavigate={closeDrawer} />
              </aside>
            </div>
          )}

          {/* Main column */}
          <div className="flex min-w-0 flex-1 flex-col bg-surface">
            <header className="sticky top-0 z-40 flex items-center gap-3 border-b border-line bg-surface px-4 py-3.5 md:px-7">
              <button
                onClick={() => setDrawerOpen(true)}
                className="rounded-md p-2 text-ink-3 hover:bg-surface-2 md:hidden"
                aria-label="Open menu"
                aria-expanded={drawerOpen}
              >
                <Menu className="h-5 w-5" aria-hidden="true" />
              </button>
              <Link
                to="/forum/search"
                className="flex max-w-[430px] flex-1 items-center gap-2.5 rounded-pill border border-line bg-surface-2/70 px-4 py-2.5 text-[13.5px] text-ink-3 transition-colors hover:border-line-2"
              >
                <Search className="h-[15px] w-[15px]" aria-hidden="true" />
                Search plants, posts, people…
              </Link>
              <div className="ml-auto flex items-center gap-2">
                <Link
                  to="/forum/new-thread"
                  aria-label="New post"
                  title="New post"
                  className="grid h-[38px] w-[38px] place-items-center rounded-md border border-line bg-surface-2/60 text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                </Link>
                <button
                  type="button"
                  onClick={toggleMode}
                  aria-label={themeLabel}
                  aria-pressed={mode === 'dark'}
                  title={themeLabel}
                  className="grid h-[38px] w-[38px] place-items-center rounded-md border border-line bg-surface-2/60 text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"
                >
                  {mode === 'dark' ? (
                    <Sun className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Moon className="h-4 w-4" aria-hidden="true" />
                  )}
                </button>
                {isAuthenticated && <NotificationBell />}
                {isAuthenticated ? (
                  <UserMenu />
                ) : (
                  <Link
                    to="/signup"
                    className="canopy-cta rounded-pill px-4 py-2 text-[13px] font-semibold"
                  >
                    Sign up
                  </Link>
                )}
              </div>
            </header>
            <div className="flex min-w-0 flex-1">
              <main id="main-content" className="min-w-0 flex-1">
                {children}
              </main>
              <aside
                id={RAIL_CONTAINER_ID}
                className="app-rail hidden w-[300px] flex-none flex-col gap-7 border-l border-line px-5 py-6 xl:flex"
                aria-label="Related"
              />
            </div>
          </div>
        </div>
      </div>
    </UnreadNotificationsProvider>
  );
}
