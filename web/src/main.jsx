import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
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
 * - BrowserRouter for routing
 * - AuthProvider for authentication state (Phase 3)
 * - Sentry error tracking (production only)
 */
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
