import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { Menu, X, User } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'

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
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const { user, isAuthenticated, logout } = useAuth()

  const toggleMenu = () => setIsMenuOpen(!isMenuOpen)
  const closeMenu = () => setIsMenuOpen(false)

  const handleLogout = async () => {
    await logout()
    closeMenu()
  }

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <Link
            to="/"
            className="flex items-center gap-2"
            aria-label="PlantID Home"
          >
            <div
              className="w-8 h-8 bg-gradient-to-br from-green-500 to-emerald-500 rounded-lg"
              role="img"
              aria-hidden="true"
            />
            <span className="text-xl font-bold text-gray-900">PlantID</span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-8">
            <NavLink
              to="/identify"
              className={({ isActive }) =>
                `font-medium transition-colors ${
                  isActive
                    ? 'text-green-600'
                    : 'text-gray-700 hover:text-green-600'
                }`
              }
            >
              Identify
            </NavLink>
            <NavLink
              to="/blog"
              className={({ isActive }) =>
                `font-medium transition-colors ${
                  isActive
                    ? 'text-green-600'
                    : 'text-gray-700 hover:text-green-600'
                }`
              }
            >
              Blog
            </NavLink>
            <NavLink
              to="/forum"
              className={({ isActive }) =>
                `font-medium transition-colors ${
                  isActive
                    ? 'text-green-600'
                    : 'text-gray-700 hover:text-green-600'
                }`
              }
            >
              Community
            </NavLink>
          </div>

          {/* Desktop Auth Actions */}
          <div className="hidden md:flex items-center gap-4">
            {isAuthenticated ? (
              <>
                <div className="flex items-center gap-2 text-gray-700">
                  <User className="w-5 h-5 text-green-600" />
                  <span className="font-medium">{user?.name || user?.email}</span>
                </div>
                <button
                  onClick={handleLogout}
                  className="px-4 py-2 text-gray-700 hover:text-green-600 font-medium transition-colors"
                >
                  Log out
                </button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="text-gray-700 hover:text-green-600 font-medium transition-colors"
                >
                  Log in
                </Link>
                <Link
                  to="/signup"
                  className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
                >
                  Sign up
                </Link>
              </>
            )}
          </div>

          {/* Mobile menu button */}
          <button
            onClick={toggleMenu}
            className="md:hidden p-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors"
            aria-label="Toggle menu"
            aria-expanded={isMenuOpen}
          >
            {isMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {isMenuOpen && (
        <div className="md:hidden border-t border-gray-200 bg-white">
          <div className="px-4 py-4 space-y-3">
            <NavLink
              to="/identify"
              onClick={closeMenu}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg font-medium transition-colors ${
                  isActive
                    ? 'bg-green-50 text-green-600'
                    : 'text-gray-700 hover:bg-gray-50'
                }`
              }
            >
              Identify
            </NavLink>
            <NavLink
              to="/blog"
              onClick={closeMenu}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg font-medium transition-colors ${
                  isActive
                    ? 'bg-green-50 text-green-600'
                    : 'text-gray-700 hover:bg-gray-50'
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
                  isActive
                    ? 'bg-green-50 text-green-600'
                    : 'text-gray-700 hover:bg-gray-50'
                }`
              }
            >
              Community
            </NavLink>

            {/* Mobile Auth Actions */}
            <div className="pt-4 border-t border-gray-200">
              {isAuthenticated ? (
                <>
                  <div className="flex items-center gap-2 px-3 py-2 text-gray-700">
                    <User className="w-5 h-5 text-green-600" />
                    <span className="font-medium">{user?.name || user?.email}</span>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-3 py-2 rounded-lg text-gray-700 hover:bg-gray-50 font-medium transition-colors"
                  >
                    Log out
                  </button>
                </>
              ) : (
                <>
                  <Link
                    to="/login"
                    onClick={closeMenu}
                    className="block px-3 py-2 rounded-lg text-gray-700 hover:bg-gray-50 font-medium transition-colors"
                  >
                    Log in
                  </Link>
                  <Link
                    to="/signup"
                    onClick={closeMenu}
                    className="block px-3 py-2 rounded-lg bg-green-600 text-white hover:bg-green-700 text-center font-medium mt-2 transition-colors"
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
  )
}
