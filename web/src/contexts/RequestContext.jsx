/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useMemo } from 'react'
import { v4 as uuidv4 } from 'uuid'

/**
 * RequestContext
 *
 * Provides a unique request ID for distributed tracing across the application.
 * The request ID is generated once per session and can be used to correlate
 * frontend and backend logs in Sentry and other monitoring tools.
 *
 * Context Value:
 * - requestId: UUID v4 string generated on context initialization
 *
 * Usage:
 * ```jsx
 * import { useRequestId } from '../contexts/RequestContext'
 *
 * function MyComponent() {
 *   const requestId = useRequestId()
 *   // requestId is automatically included in logger calls
 * }
 * ```
 *
 * Note: eslint-disable for react-refresh is intentional - this file exports
 * both the context and provider, which is a common and acceptable pattern.
 */
export const RequestContext = createContext(null)

/**
 * useRequestId Hook
 *
 * Custom hook to consume RequestContext and get the current request ID.
 * Provides a cleaner API for accessing the request ID.
 *
 * @returns {string} UUID v4 request ID
 * @throws {Error} If used outside of RequestProvider
 */
export function useRequestId() {
  const context = useContext(RequestContext)

  if (context === null) {
    throw new Error('useRequestId must be used within a RequestProvider')
  }

  return context.requestId
}

/**
 * RequestProvider Component
 *
 * Wraps the app to provide request ID context to all children.
 * Generates a single request ID per session for distributed tracing.
 *
 * The request ID is:
 * - Generated once using crypto.randomUUID() (UUID v4)
 * - Persisted in session storage for consistency across page refreshes
 * - Used to correlate frontend and backend logs via X-Request-ID header
 * - Automatically included in structured log messages
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Child components
 */
export function RequestProvider({ children }) {
  // Generate or retrieve request ID from session storage
  const getOrCreateRequestId = () => {
    try {
      // Check if request ID exists in session storage
      const stored = sessionStorage.getItem('requestId')
      if (stored) {
        return stored
      }

      // Generate new UUID v4 request ID
      const newRequestId = crypto.randomUUID()
      sessionStorage.setItem('requestId', newRequestId)
      return newRequestId
    } catch (error) {
      // Fallback if sessionStorage is not available (e.g., private browsing)
      // Use uuid library as fallback for older browsers
      return uuidv4()
    }
  }

  const requestId = getOrCreateRequestId()

  // Memoize context value to prevent unnecessary re-renders
  const value = useMemo(
    () => ({
      requestId,
    }),
    [requestId]
  )

  // React 19: Use RequestContext directly as provider
  return <RequestContext value={value}>{children}</RequestContext>
}
