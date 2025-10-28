import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ErrorBoundary } from 'react-error-boundary'
import { AuthProvider } from './contexts/AuthContext'
import { ErrorFallback } from './components/ErrorBoundary'
import { initSentry } from './config/sentry'
import './index.css'
import App from './App.jsx'

// Initialize Sentry error tracking (production only)
initSentry()

/**
 * App Entry Point
 *
 * Wraps the app with:
 * - StrictMode for development warnings
 * - ErrorBoundary to catch and display errors gracefully
 * - BrowserRouter for routing
 * - AuthProvider for authentication state (Phase 3)
 * - Sentry error tracking (production only)
 *
 * Error handling strategy:
 * - ErrorBoundary catches React errors and prevents white screen
 * - Sentry logs errors to monitoring service (production)
 * - ErrorFallback provides user-friendly error UI with recovery options
 */
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary
      FallbackComponent={ErrorFallback}
      onError={(error, errorInfo) => {
        // Log to console in development
        if (import.meta.env.DEV) {
          console.error('[ErrorBoundary] Caught error:', error);
          console.error('[ErrorBoundary] Error info:', errorInfo);
        }
        // Sentry automatically captures errors via its ErrorBoundary integration
      }}
      onReset={() => {
        // ErrorBoundary automatically resets component tree
        // Only add custom logic here if you need to clear specific app state
        console.log('[ErrorBoundary] Resetting error boundary');
      }}
    >
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)
