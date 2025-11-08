import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { User, Settings, LogOut, ChevronDown } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

/**
 * UserMenu Component
 *
 * Dropdown menu for authenticated users.
 * Features:
 * - User initials or avatar display
 * - Dropdown menu with Profile, Settings, Logout
 * - Click outside to close (using useEffect and ref)
 * - Keyboard navigation (Escape to close)
 * - Smooth transitions
 *
 * @example
 * <UserMenu />
 */
export default function UserMenu() {
  const { user, logout } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef(null)

  /**
   * Get user initials from name or email
   * @returns {string} Two-letter initials
   */
  const getInitials = () => {
    if (user?.name) {
      const names = user.name.split(' ')
      if (names.length >= 2) {
        return `${names[0][0]}${names[1][0]}`.toUpperCase()
      }
      return user.name.substring(0, 2).toUpperCase()
    }
    if (user?.email) {
      return user.email.substring(0, 2).toUpperCase()
    }
    return 'U'
  }

  /**
   * Handle click outside to close menu
   */
  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }

    // Handle Escape key to close menu
    function handleEscape(event) {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleEscape)

      return () => {
        document.removeEventListener('mousedown', handleClickOutside)
        document.removeEventListener('keydown', handleEscape)
      }
    }
  }, [isOpen])

  /**
   * Handle logout
   */
  const handleLogout = async () => {
    setIsOpen(false)
    await logout()
  }

  return (
    <div className="relative" ref={menuRef}>
      {/* User Avatar Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors"
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        {/* Avatar Circle */}
        <div className="w-8 h-8 rounded-full bg-green-600 text-white flex items-center justify-center font-medium text-sm">
          {getInitials()}
        </div>

        {/* User Name (desktop only) */}
        <span className="hidden md:inline font-medium">
          {user?.name || user?.email}
        </span>

        {/* Chevron Icon */}
        <ChevronDown
          className={`w-4 h-4 transition-transform ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          role="menu"
          aria-label="User menu"
          className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50"
        >
          {/* User Info Header */}
          <div className="px-4 py-3 border-b border-gray-200">
            <p className="text-sm font-medium text-gray-900">
              {user?.name || 'User'}
            </p>
            <p className="text-xs text-gray-500 truncate">{user?.email}</p>
          </div>

          {/* Menu Items */}
          <div className="py-2">
            <Link
              to="/profile"
              role="menuitem"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <User className="w-4 h-4" />
              <span>Profile</span>
            </Link>

            <Link
              to="/settings"
              role="menuitem"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <Settings className="w-4 h-4" />
              <span>Settings</span>
            </Link>
          </div>

          {/* Logout Button */}
          <div className="border-t border-gray-200 pt-2">
            <button
              onClick={handleLogout}
              role="menuitem"
              className="flex items-center gap-3 w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span>Log out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
