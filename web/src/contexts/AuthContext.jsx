/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useMemo } from 'react'
import * as authService from '../services/authService'
import { logger } from '../utils/logger'

/**
 * AuthContext
 *
 * Provides authentication state and methods throughout the app.
 * Uses React 19's createContext which can be used directly as a provider.
 *
 * Context Value:
 * - user: Current user object or null
 * - isLoading: Boolean indicating auth state is being determined
 * - error: Error message if auth operation failed
 * - isAuthenticated: Boolean indicating if user is logged in
 * - login(credentials): Function to log in
 * - logout(): Function to log out
 * - signup(userData): Function to sign up
 *
 * Note: eslint-disable for react-refresh is intentional - this file exports
 * both the context and provider, which is a common and acceptable pattern.
 */
export const AuthContext = createContext(null)

/**
 * useAuth Hook
 *
 * Custom hook to consume AuthContext.
 * Provides a cleaner API for accessing auth state and methods.
 *
 * @returns {Object} Auth context value
 * @throws {Error} If used outside of AuthProvider
 */
export function useAuth() {
  const context = useContext(AuthContext)

  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider')
  }

  return context
}

/**
 * AuthProvider Component
 *
 * Wraps the app to provide authentication context to all children.
 * Handles authentication state, persistence, and API calls.
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Child components
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  // Initialize auth state on mount
  useEffect(() => {
    async function initAuth() {
      try {
        // First, try to get stored user for immediate UI update
        const storedUser = authService.getStoredUser()
        if (storedUser) {
          setUser(storedUser)
        }

        // Then verify with backend to ensure session is still valid
        const currentUser = await authService.getCurrentUser()
        setUser(currentUser)
      } catch (err) {
        logger.error('[AuthContext] Auth initialization failed:', err)
        setUser(null)
      } finally {
        setIsLoading(false)
      }
    }

    initAuth()
  }, [])

  /**
   * Login user with email and password
   * @param {Object} credentials - User credentials
   * @returns {Promise<Object>} Result object with success flag
   */
  const login = async (credentials) => {
    setIsLoading(true)
    setError(null)

    try {
      const userData = await authService.login(credentials)
      setUser(userData)
      return { success: true, user: userData }
    } catch (err) {
      const errorMessage = err.message || 'Login failed. Please try again.'
      setError(errorMessage)
      return { success: false, error: errorMessage }
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * Sign up new user
   * @param {Object} userData - New user data (name, email, password)
   * @returns {Promise<Object>} Result object with success flag
   */
  const signup = async (userData) => {
    setIsLoading(true)
    setError(null)

    try {
      const newUser = await authService.signup(userData)
      setUser(newUser)
      return { success: true, user: newUser }
    } catch (err) {
      const errorMessage = err.message || 'Signup failed. Please try again.'
      setError(errorMessage)
      return { success: false, error: errorMessage }
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * Logout current user
   * Clears user state and calls logout API
   */
  const logout = async () => {
    try {
      await authService.logout()
      setUser(null)
      setError(null)
    } catch (err) {
      logger.error('[AuthContext] Logout failed:', err)
      // Still clear user state even if API fails
      setUser(null)
    }
  }

  // Memoize context value to prevent unnecessary re-renders
  const value = useMemo(
    () => ({
      user,
      isLoading,
      error,
      isAuthenticated: !!user,
      login,
      logout,
      signup,
    }),
    [user, isLoading, error]
  )

  // React 19: Use AuthContext directly as provider
  return <AuthContext value={value}>{children}</AuthContext>
}
