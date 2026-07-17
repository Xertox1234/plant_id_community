import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { Menu, X, User, Settings as SettingsIcon, Sun, Moon, Leaf, Search } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import NotificationBell from './NotificationBell';
import UserMenu from './UserMenu';

/**
 * Header Component
 *
 * Responsive navigation header with mobile menu and authentication.
 * Features:
 * - Sticky header with logo and navigation
 * - Desktop navigation (visible on md+ breakpoints)
 * - Mobile hamburger menu with slide animation
 * - Active link highlighting with NavLink
 * - Authentication-aware UI (shows user info when logged in)
 * - Phase 3: Basic auth integration (enhanced in Phase 5 with UserMenu)
 */
export default function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const { user, isAuthenticated, logout } = useAuth();
  const { mode, toggleMode } = useTheme();
  const themeLabel = mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';

  const toggleMenu = () => setIsMenuOpen(!isMenuOpen);
  const closeMenu = () => setIsMenuOpen(false);

  const handleLogout = async () => {
    await logout();
    closeMenu();
  };

  return (
    <nav className="bg-surface-2 border-b border-line sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2" aria-label="PlantID Home">
            <div
              className="w-8 h-8 bg-gradient-to-br from-primary to-secondary rounded-lg"
              role="img"
              aria-hidden="true"
            />
            <span className="text-xl font-bold text-ink">PlantID</span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-8">
            <NavLink
              to="/identify"
              className={({ isActive }) =>
                `font-medium transition-colors ${
                  isActive ? 'text-primary' : 'text-ink-2 hover:text-primary'
                }`
              }
            >
              Identify
            </NavLink>
            <NavLink
              to="/diagnose"
              className={({ isActive }) =>
                `font-medium transition-colors ${
                  isActive ? 'text-primary' : 'text-ink-2 hover:text-primary'
                }`
              }
            >
              Diagnose
            </NavLink>
            <NavLink
              to="/blog"
              className={({ isActive }) =>
                `font-medium transition-colors ${
                  isActive ? 'text-primary' : 'text-ink-2 hover:text-primary'
                }`
              }
            >
              Blog
            </NavLink>
            <NavLink
              to="/forum"
              className={({ isActive }) =>
                `font-medium transition-colors ${
                  isActive ? 'text-primary' : 'text-ink-2 hover:text-primary'
                }`
              }
            >
              Community
            </NavLink>
          </div>

          {/* Notification bell (shared across breakpoints — a SINGLE instance,
              always visible, so it never double-mounts and double-polls
              alongside the mobile drawer's own copy) + Desktop Auth Actions +
              Mobile menu button, grouped so they sit together at the row's end. */}
          <div className="flex items-center gap-2 md:gap-4">
            <Link
              to="/forum/search"
              aria-label="Search the forum"
              title="Search the forum"
              className="p-2 rounded-lg text-ink-2 hover:text-primary hover:bg-surface transition-colors"
            >
              <Search className="w-5 h-5" />
            </Link>
            {isAuthenticated && <NotificationBell />}

            <div className="hidden md:flex items-center gap-4">
              <button
                type="button"
                onClick={toggleMode}
                aria-label={themeLabel}
                aria-pressed={mode === 'dark'}
                title={themeLabel}
                className="p-2 rounded-lg text-ink-2 hover:text-primary hover:bg-surface transition-colors"
              >
                {mode === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>
              {isAuthenticated ? (
                <UserMenu />
              ) : (
                <>
                  <Link
                    to="/login"
                    className="text-ink-2 hover:text-primary font-medium transition-colors"
                  >
                    Log in
                  </Link>
                  <Link
                    to="/signup"
                    className="px-4 py-2 bg-clay text-on-clay rounded-lg font-medium hover:bg-clay/90 transition-colors"
                  >
                    Sign up
                  </Link>
                </>
              )}
            </div>

            {/* Mobile menu button */}
            <button
              onClick={toggleMenu}
              className="md:hidden p-2 rounded-lg text-ink-3 hover:bg-surface transition-colors"
              aria-label="Toggle menu"
              aria-expanded={isMenuOpen}
            >
              {isMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {isMenuOpen && (
        <div className="md:hidden border-t border-line bg-surface-2">
          <div className="px-4 py-4 space-y-3">
            <NavLink
              to="/identify"
              onClick={closeMenu}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg font-medium transition-colors ${
                  isActive ? 'bg-primary/10 text-primary' : 'text-ink-2 hover:bg-surface'
                }`
              }
            >
              Identify
            </NavLink>
            <NavLink
              to="/diagnose"
              onClick={closeMenu}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg font-medium transition-colors ${
                  isActive ? 'bg-primary/10 text-primary' : 'text-ink-2 hover:bg-surface'
                }`
              }
            >
              Diagnose
            </NavLink>
            <NavLink
              to="/blog"
              onClick={closeMenu}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg font-medium transition-colors ${
                  isActive ? 'bg-primary/10 text-primary' : 'text-ink-2 hover:bg-surface'
                }`
              }
            >
              Blog
            </NavLink>
            <NavLink
              to="/forum"
              onClick={closeMenu}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg font-medium transition-colors ${
                  isActive ? 'bg-primary/10 text-primary' : 'text-ink-2 hover:bg-surface'
                }`
              }
            >
              Community
            </NavLink>
            <NavLink
              to="/forum/search"
              onClick={closeMenu}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg font-medium transition-colors ${
                  isActive ? 'bg-primary/10 text-primary' : 'text-ink-2 hover:bg-surface'
                }`
              }
            >
              Search Forum
            </NavLink>

            {/* Theme toggle */}
            <button
              type="button"
              onClick={toggleMode}
              aria-label={themeLabel}
              aria-pressed={mode === 'dark'}
              className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-ink-2 hover:bg-surface font-medium transition-colors"
            >
              {mode === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              {mode === 'dark' ? 'Light mode' : 'Dark mode'}
            </button>

            {/* Mobile Auth Actions */}
            <div className="pt-4 border-t border-line">
              {isAuthenticated ? (
                <>
                  <div className="flex items-center gap-2 px-3 py-2 text-ink-2 mb-2">
                    <User className="w-5 h-5 text-primary" />
                    <span className="font-medium">{user?.username || user?.email}</span>
                  </div>
                  <Link
                    to="/my-plants"
                    onClick={closeMenu}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-ink-2 hover:bg-surface font-medium transition-colors"
                  >
                    <Leaf className="w-4 h-4" />
                    My Plants
                  </Link>
                  <Link
                    to="/profile"
                    onClick={closeMenu}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-ink-2 hover:bg-surface font-medium transition-colors"
                  >
                    <User className="w-4 h-4" />
                    Profile
                  </Link>
                  <Link
                    to="/settings"
                    onClick={closeMenu}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-ink-2 hover:bg-surface font-medium transition-colors"
                  >
                    <SettingsIcon className="w-4 h-4" />
                    Settings
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-3 py-2 rounded-lg text-error hover:bg-error/10 font-medium transition-colors"
                  >
                    Log out
                  </button>
                </>
              ) : (
                <>
                  <Link
                    to="/login"
                    onClick={closeMenu}
                    className="block px-3 py-2 rounded-lg text-ink-2 hover:bg-surface font-medium transition-colors"
                  >
                    Log in
                  </Link>
                  <Link
                    to="/signup"
                    onClick={closeMenu}
                    className="block px-3 py-2 rounded-lg bg-clay text-on-clay hover:bg-clay/90 text-center font-medium mt-2 transition-colors"
                  >
                    Sign up
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
