/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useMemo, ReactNode } from 'react'
import * as authService from '../services/authService'
import { logger } from '../utils/logger'
import { AuthErrorCode } from '../types/auth'
import type { User, LoginCredentials, SignupData, AuthError } from '../types/auth'

// Re-export all auth types for convenience (single import source)
export type { User, LoginCredentials, SignupData, AuthError } from '../types/auth'
export { AuthErrorCode } from '../types/auth'

/**
 * Convert any error to structured AuthError
 * Extracts error code from known error messages for better categorization
 */
function toAuthError(err: unknown, defaultMessage: string): AuthError {
  if (!err) {
    return {
      message: defaultMessage,
      code: AuthErrorCode.UNKNOWN,
    }
  }

  const message = err instanceof Error ? err.message : defaultMessage
  const lowerMessage = message.toLowerCase()

  // Categorize based on error message patterns
  // IMPORTANT: Check specific patterns BEFORE general ones to avoid misclassification
  let code = AuthErrorCode.UNKNOWN

  // Check specific patterns first
  if (lowerMessage.includes('expired') || lowerMessage.includes('session')) {
    code = AuthErrorCode.SESSION_EXPIRED
  } else if (lowerMessage.includes('rate') || lowerMessage.includes('too many')) {
    code = AuthErrorCode.RATE_LIMITED
  } else if (lowerMessage.includes('exists') || lowerMessage.includes('already')) {
    code = AuthErrorCode.EMAIL_EXISTS
  } else if (lowerMessage.includes('network') || lowerMessage.includes('fetch')) {
    code = AuthErrorCode.NETWORK_ERROR
  } else if (lowerMessage.includes('validation')) {
    code = AuthErrorCode.VALIDATION_ERROR
  } else if (lowerMessage.includes('invalid') || lowerMessage.includes('incorrect')) {
    // Check "invalid" last since it's general (e.g., "invalid session" should be SESSION_EXPIRED)
    code = AuthErrorCode.INVALID_CREDENTIALS
  }

  return {
    message,
    code,
    details: err instanceof Error ? { name: err.name, stack: err.stack } : undefined,
  }
}

/**
 * Authentication operation result
 */
export interface AuthResult {
  success: boolean;
  user?: User;
  error?: AuthError;
}

/**
 * AuthContext value type
 *
 * Provides authentication state and methods throughout the app.
 */
export interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  error: AuthError | null;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<AuthResult>;
  logout: () => Promise<void>;
  signup: (userData: SignupData) => Promise<AuthResult>;
  clearError: () => void;
}

/**
 * AuthContext
 *
 * Provides authentication state and methods throughout the app.
 * Uses React 19's createContext which can be used directly as a provider.
 *
 * Context Value:
 * - user: Current user object or null
 * - isLoading: Boolean indicating auth state is being determined
 * - error: Structured error object if auth operation failed
 * - isAuthenticated: Boolean indicating if user is logged in
 * - login(credentials): Function to log in
 * - logout(): Function to log out
 * - signup(userData): Function to sign up
 * - clearError(): Function to manually clear error state
 *
 * Note: eslint-disable for react-refresh is intentional - this file exports
 * both the context and provider, which is a common and acceptable pattern.
 */
export const AuthContext = createContext<AuthContextValue | null>(null)

/**
 * useAuth Hook
 *
 * Custom hook to consume AuthContext.
 * Provides a cleaner API for accessing auth state and methods.
 *
 * @returns Auth context value
 * @throws Error if used outside of AuthProvider
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)

  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider')
  }

  return context
}

/**
 * AuthProvider props
 */
export interface AuthProviderProps {
  children: ReactNode;
}

/**
 * AuthProvider Component
 *
 * Wraps the app to provide authentication context to all children.
 * Handles authentication state, persistence, and API calls.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<AuthError | null>(null)

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
   * Regenerates request ID on successful login for per-user session tracing
   */
  const login = async (credentials: LoginCredentials): Promise<AuthResult> => {
    setIsLoading(true)
    setError(null)

    try {
      const userData = await authService.login(credentials)
      setUser(userData)

      // Regenerate request ID for new user session (better distributed tracing)
      try {
        sessionStorage.removeItem('requestId')
      } catch (e) {
        // Ignore sessionStorage errors
      }

      return { success: true, user: userData }
    } catch (err) {
      const authError = toAuthError(err, 'Login failed. Please try again.')
      setError(authError)
      return { success: false, error: authError }
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * Sign up new user
   * Regenerates request ID on successful signup for per-user session tracing
   */
  const signup = async (userData: SignupData): Promise<AuthResult> => {
    setIsLoading(true)
    setError(null)

    try {
      const newUser = await authService.signup(userData)
      setUser(newUser)

      // Regenerate request ID for new user session (better distributed tracing)
      try {
        sessionStorage.removeItem('requestId')
      } catch (e) {
        // Ignore sessionStorage errors
      }

      return { success: true, user: newUser }
    } catch (err) {
      const authError = toAuthError(err, 'Signup failed. Please try again.')
      setError(authError)
      return { success: false, error: authError }
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * Logout current user
   * Clears user state and calls logout API
   */
  const logout = async (): Promise<void> => {
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

  /**
   * Manually clear error state
   * Useful for dismissing error messages in UI
   */
  const clearError = () => {
    setError(null)
  }

  // Memoize context value to prevent unnecessary re-renders
  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      error,
      isAuthenticated: !!user,
      login,
      logout,
      signup,
      clearError,
    }),
    [user, isLoading, error]
  )

  // React 19: Use AuthContext directly as provider
  return <AuthContext value={value}>{children}</AuthContext>
}
