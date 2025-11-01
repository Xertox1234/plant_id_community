/**
 * Enterprise-Class Structured Logger
 *
 * Provides structured logging with automatic context injection for
 * distributed tracing and enterprise-grade monitoring.
 *
 * Features:
 * - Automatic request ID correlation (from RequestContext)
 * - Automatic user ID tracking (from AuthContext)
 * - Structured JSON logging in production
 * - Pretty-print in development
 * - Sentry integration with breadcrumbs
 * - Type-safe logging methods
 *
 * Architecture:
 * - Development: Pretty-printed structured logs to console
 * - Production: Structured JSON sent to Sentry with context
 *
 * @example
 * import { logger } from '../utils/logger'
 *
 * logger.error('API call failed', {
 *   component: 'BlogService',
 *   error: error,
 *   context: { endpoint: '/api/v2/blog-posts' }
 * })
 *
 * // Outputs in development:
 * // [ERROR] API call failed
 * // {
 * //   level: 'error',
 * //   message: 'API call failed',
 * //   requestId: 'uuid-here',
 * //   userId: 'user-123',
 * //   component: 'BlogService',
 * //   timestamp: '2025-10-31T...',
 * //   environment: 'development',
 * //   error: {...}
 * // }
 */

import * as Sentry from '@sentry/react'

/**
 * Log Levels
 */
export const LOG_LEVELS = {
  DEBUG: 'debug',
  INFO: 'info',
  WARNING: 'warning',
  ERROR: 'error',
}

/**
 * Global context accessor functions
 * These are set up lazily to avoid circular dependencies with React contexts
 */
let getRequestId = null
let getUserId = null

/**
 * Initialize logger with context accessors
 * Called from main.jsx after contexts are set up
 *
 * @param {Object} options
 * @param {Function} options.getRequestId - Function to get current request ID
 * @param {Function} options.getUserId - Function to get current user ID
 */
export function initLogger({ getRequestId: reqIdFn, getUserId: userIdFn }) {
  getRequestId = reqIdFn
  getUserId = userIdFn
}

/**
 * Get base log context
 * Automatically includes requestId, userId, timestamp, environment
 *
 * @returns {Object} Base context object
 */
function getBaseContext() {
  const context = {
    timestamp: new Date().toISOString(),
    environment: import.meta.env.MODE,
  }

  // Add request ID if available
  try {
    if (getRequestId) {
      const requestId = getRequestId()
      if (requestId) {
        context.requestId = requestId
      }
    }
  } catch {
    // Silently fail if context not available
  }

  // Add user ID if available
  try {
    if (getUserId) {
      const userId = getUserId()
      if (userId) {
        context.userId = userId
      }
    }
  } catch {
    // Silently fail if context not available
  }

  return context
}

/**
 * Format log entry for console output
 *
 * @param {string} level - Log level
 * @param {string} message - Log message
 * @param {Object} context - Additional context
 * @returns {Object} Formatted log entry
 */
function formatLogEntry(level, message, context = {}) {
  return {
    level,
    message,
    ...getBaseContext(),
    ...context,
  }
}

/**
 * Send log to Sentry with appropriate level
 *
 * @param {string} level - Log level
 * @param {string} message - Log message
 * @param {Object} context - Additional context
 */
function sendToSentry(level, message, context) {
  // Add breadcrumb for all log levels
  Sentry.addBreadcrumb({
    level: level === LOG_LEVELS.WARNING ? 'warning' : level,
    message,
    data: context,
  })

  // Send to Sentry based on level
  if (level === LOG_LEVELS.ERROR) {
    if (context.error instanceof Error) {
      Sentry.captureException(context.error, {
        tags: {
          component: context.component || 'unknown',
        },
        extra: {
          message,
          ...context,
        },
      })
    } else {
      Sentry.captureMessage(message, {
        level: 'error',
        tags: {
          component: context.component || 'unknown',
        },
        extra: context,
      })
    }
  } else if (level === LOG_LEVELS.WARNING) {
    Sentry.captureMessage(message, {
      level: 'warning',
      tags: {
        component: context.component || 'unknown',
      },
      extra: context,
    })
  }
  // INFO and DEBUG are breadcrumbs only
}

/**
 * Core logging function
 *
 * @param {string} level - Log level
 * @param {string} message - Log message
 * @param {Object} context - Additional context
 */
function log(level, message, context = {}) {
  const entry = formatLogEntry(level, message, context)

  if (import.meta.env.DEV) {
    // Development: Pretty-print to console
    const levelColors = {
      debug: 'color: gray',
      info: 'color: blue',
      warning: 'color: orange',
      error: 'color: red',
    }

    const style = levelColors[level] || ''
    console.log(`%c[${level.toUpperCase()}] ${message}`, style)
    console.log(entry)
  } else {
    // Production: Send structured data to Sentry
    sendToSentry(level, message, context)
  }
}

/**
 * Log debug message (development only)
 *
 * @param {string} message - Debug message
 * @param {Object} context - Additional context
 */
function debug(message, context = {}) {
  if (import.meta.env.DEV) {
    log(LOG_LEVELS.DEBUG, message, context)
  }
}

/**
 * Log info message
 *
 * @param {string} message - Info message
 * @param {Object} context - Additional context
 */
function info(message, context = {}) {
  log(LOG_LEVELS.INFO, message, context)
}

/**
 * Log warning message
 *
 * @param {string} message - Warning message
 * @param {Object} context - Additional context
 */
function warn(message, context = {}) {
  log(LOG_LEVELS.WARNING, message, context)
}

/**
 * Log error message
 *
 * @param {string} message - Error message
 * @param {Object} context - Additional context (should include error object)
 */
function error(message, context = {}) {
  log(LOG_LEVELS.ERROR, message, context)
}

/**
 * Logger object with method interface
 * Provides enterprise-class structured logging with automatic context
 */
export const logger = {
  debug,
  info,
  warn,
  error,
}

/**
 * Legacy function names for backward compatibility
 * @deprecated Use logger.error() instead
 */
export function logError(message, error) {
  logger.error(message, { error })
}

/**
 * @deprecated Use logger.warn() instead
 */
export function logWarning(message, data) {
  logger.warn(message, { data })
}

/**
 * @deprecated Use logger.info() instead
 */
export function logInfo(message, data) {
  logger.info(message, { data })
}

export default logger
