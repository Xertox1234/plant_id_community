import { useContext } from 'react'
import { AuthContext } from '../contexts/AuthContext'

/**
 * useAuth Hook
 *
 * Custom hook to access authentication context.
 * Provides user state and authentication methods to components.
 *
 * @returns {Object} Authentication context value
 * @returns {Object|null} user - Current user or null
 * @returns {boolean} isLoading - Loading state
 * @returns {string|null} error - Error message
 * @returns {boolean} isAuthenticated - Whether user is logged in
 * @returns {Function} login - Login function
 * @returns {Function} logout - Logout function
 * @returns {Function} signup - Signup function
 *
 * @throws {Error} If used outside of AuthProvider
 *
 * @example
 * function MyComponent() {
 *   const { user, login, logout, isAuthenticated } = useAuth()
 *
 *   if (isAuthenticated) {
 *     return <div>Welcome, {user.name}!</div>
 *   }
 *
 *   return <LoginForm onLogin={login} />
 * }
 */
export function useAuth() {
  const context = useContext(AuthContext)

  if (context === null) {
    throw new Error(
      'useAuth must be used within an AuthProvider. ' +
        'Wrap your app with <AuthProvider> in main.jsx'
    )
  }

  return context
}
