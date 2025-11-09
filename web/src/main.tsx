import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ErrorBoundary, FallbackProps } from 'react-error-boundary'
import { AuthProvider } from './contexts/AuthContext'
import { RequestProvider } from './contexts/RequestContext'
import { ErrorFallback } from './components/ErrorBoundary'
import { initSentry } from './config/sentry'
import { logger, initLogger } from './utils/logger'
import './index.css'
import App from './App'

// Initialize Sentry error tracking (production only)
initSentry()

// Initialize logger with context accessors
// Note: We can't directly access React context here, so we'll use a workaround
// The logger will attempt to get context values when logging, not at init time
initLogger({
  getRequestId: () => {
    try {
      // Try to get from sessionStorage (set by RequestContext)
      return sessionStorage.getItem('requestId')
    } catch {
      return null
    }
  },
  getUserId: () => {
    try {
      // Try to get from sessionStorage (set by AuthContext)
      const userStr = sessionStorage.getItem('user')
      if (userStr) {
        const user = JSON.parse(userStr)
        return user?.id || user?.username || null
      }
    } catch {
      return null
    }
  },
})

/**
 * App Entry Point
 *
 * Wraps the app with:
 * - StrictMode for development warnings
 * - ErrorBoundary to catch and display errors gracefully
 * - BrowserRouter for routing
 * - RequestProvider for distributed tracing (Phase 2)
 * - AuthProvider for authentication state (Phase 3)
 * - Sentry error tracking (production only)
 *
 * Error handling strategy:
 * - ErrorBoundary catches React errors and prevents white screen
 * - Sentry logs errors to monitoring service (production)
 * - ErrorFallback provides user-friendly error UI with recovery options
 */
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary
      FallbackComponent={ErrorFallback}
      onError={(error: Error, errorInfo: { componentStack: string }) => {
        // Log errors using structured logger
        logger.error('ErrorBoundary caught error', {
          component: 'ErrorBoundary',
          error,
          errorInfo,
        })
        // Sentry automatically captures errors via its ErrorBoundary integration
      }}
      onReset={() => {
        // ErrorBoundary automatically resets component tree
        // Only add custom logic here if you need to clear specific app state
        logger.info('ErrorBoundary reset', {
          component: 'ErrorBoundary',
        })
      }}
    >
      <BrowserRouter>
        <RequestProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </RequestProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)
