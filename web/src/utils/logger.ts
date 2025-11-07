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
} as const

type LogLevel = typeof LOG_LEVELS[keyof typeof LOG_LEVELS]

/**
 * Log context object
 */
interface LogContext {
  component?: string
  error?: unknown
  url?: string
  [key: string]: unknown
}

/**
 * Base context with automatic injected fields
 */
interface BaseContext {
  timestamp: string
  environment: string
  requestId?: string
  userId?: string
}

/**
 * Logger initialization options
 */
interface InitLoggerOptions {
  getRequestId?: (() => string | null) | null
  getUserId?: (() => string | null) | null
}

/**
 * Global context accessor functions
 * These are set up lazily to avoid circular dependencies with React contexts
 */
let getRequestId: (() => string | null) | null = null
let getUserId: (() => string | null) | null = null

/**
 * Initialize logger with context accessors
 * Called from main.jsx after contexts are set up
 *
 * @param options - Context accessor functions
 */
export function initLogger({ getRequestId: reqIdFn, getUserId: userIdFn }: InitLoggerOptions): void {
  getRequestId = reqIdFn || null
  getUserId = userIdFn || null
}

/**
 * Get base log context
 * Automatically includes requestId, userId, timestamp, environment
 *
 * @returns Base context object
 */
function getBaseContext(): BaseContext {
  const context: BaseContext = {
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
 * Sanitize URL by removing query parameters and hash
 * Prevents PII exposure from query params (user IDs, emails, tokens)
 *
 * @param url - URL to sanitize
 * @returns URL without query params or hash
 *
 * @example
 * sanitizeUrl('/api/users?email=user@example.com&id=123')
 * // Returns: '/api/users'
 */
function sanitizeUrl(url: unknown): unknown {
  if (!url || typeof url !== 'string') return url

  try {
    // Check if it's a full URL (starts with http:// or https://)
    if (url.startsWith('http://') || url.startsWith('https://')) {
      const urlObj = new URL(url)
      return `${urlObj.origin}${urlObj.pathname}`
    }

    // For relative URLs, use string manipulation
    // Remove query params (?...) and hash (#...)
    return url.split('?')[0].split('#')[0]
  } catch {
    // If parsing fails, fallback to string manipulation
    return url.split('?')[0].split('#')[0]
  }
}

/**
 * Sanitized error object with only safe properties
 */
interface SafeError {
  message?: string
  name?: string
  stack?: string
  status?: number
  statusText?: string
}

/**
 * Sanitize error object by removing sensitive properties
 * Filters out config, headers, request details that may contain secrets
 *
 * @param error - Error object to sanitize
 * @returns Sanitized error with only safe properties
 *
 * @example
 * const axiosError = { message: 'Failed', config: { headers: { Authorization: 'Bearer secret' } } }
 * sanitizeError(axiosError)
 * // Returns: { message: 'Failed', name: undefined, stack: undefined, status: undefined }
 */
function sanitizeError(error: unknown): unknown {
  if (!error) return error

  // If it's a primitive (string, number), return as-is
  if (typeof error !== 'object') return error

  // Extract only safe properties
  const errorObj = error as Record<string, unknown>
  const safe: SafeError = {
    message: errorObj.message as string | undefined,
    name: errorObj.name as string | undefined,
    stack: import.meta.env.DEV ? (errorObj.stack as string | undefined) : undefined, // Stack traces in dev only
  }

  // Add Axios-specific safe properties if present
  if (errorObj.response && typeof errorObj.response === 'object') {
    const response = errorObj.response as Record<string, unknown>
    safe.status = response.status as number | undefined
    safe.statusText = response.statusText as string | undefined
  }

  // Omit sensitive properties:
  // - error.config (may contain headers, auth, API keys)
  // - error.config.headers (Authorization, X-CSRFToken, etc.)
  // - error.config.data (request body with passwords, tokens)
  // - error.request (XMLHttpRequest object with full request details)
  // - error.response.config (same as error.config)
  // - error.response.request (same as error.request)

  return safe
}

/**
 * Format log entry for console output
 *
 * @param level - Log level
 * @param message - Log message
 * @param context - Additional context
 * @returns Formatted log entry
 */
function formatLogEntry(level: LogLevel, message: string, context: LogContext = {}): BaseContext & LogContext {
  // Only sanitize if context is an object
  if (context && typeof context === 'object') {
    // Sanitize URL if present in context
    if (context.url) {
      context.url = sanitizeUrl(context.url) as string
    }

    // Sanitize error if present in context
    // Only sanitize if it's an object (not Error instance which should be preserved)
    if (context.error && typeof context.error === 'object' && !(context.error instanceof Error)) {
      context.error = sanitizeError(context.error)
    }
  }

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
 * @param level - Log level
 * @param message - Log message
 * @param context - Additional context
 */
function sendToSentry(level: LogLevel, message: string, context: LogContext): void {
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
          component: (context.component as string) || 'unknown',
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
          component: (context.component as string) || 'unknown',
        },
        extra: context,
      })
    }
  } else if (level === LOG_LEVELS.WARNING) {
    Sentry.captureMessage(message, {
      level: 'warning',
      tags: {
        component: (context.component as string) || 'unknown',
      },
      extra: context,
    })
  }
  // INFO and DEBUG are breadcrumbs only
}

/**
 * Core logging function
 *
 * @param level - Log level
 * @param message - Log message
 * @param context - Additional context
 */
function log(level: LogLevel, message: string, context: LogContext = {}): void {
  const entry = formatLogEntry(level, message, context)

  if (import.meta.env.DEV) {
    // Development: Pretty-print to console
    const levelColors: Record<LogLevel, string> = {
      debug: 'color: gray',
      info: 'color: blue',
      warning: 'color: orange',
      error: 'color: red',
    }

    const style = levelColors[level] || ''
    // EXCEPTION: console.log is acceptable here (logger bootstrap/infrastructure)
    // This is the logger's own output mechanism - using logger here would cause infinite recursion
    // Note: no-console rule is disabled for logger.js in eslint.config.js
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
 * @param message - Debug message
 * @param context - Additional context
 */
function debug(message: string, context: LogContext = {}): void {
  if (import.meta.env.DEV) {
    log(LOG_LEVELS.DEBUG, message, context)
  }
}

/**
 * Log info message
 *
 * @param message - Info message
 * @param context - Additional context
 */
function info(message: string, context: LogContext = {}): void {
  log(LOG_LEVELS.INFO, message, context)
}

/**
 * Log warning message
 *
 * @param message - Warning message
 * @param context - Additional context
 */
function warn(message: string, context: LogContext = {}): void {
  log(LOG_LEVELS.WARNING, message, context)
}

/**
 * Log error message
 *
 * @param message - Error message
 * @param context - Additional context (should include error object)
 */
function error(message: string, context: LogContext = {}): void {
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
export function logError(message: string, error: unknown): void {
  logger.error(message, { error })
}

/**
 * @deprecated Use logger.warn() instead
 */
export function logWarning(message: string, data: unknown): void {
  logger.warn(message, { data })
}

/**
 * @deprecated Use logger.info() instead
 */
export function logInfo(message: string, data: unknown): void {
  logger.info(message, { data })
}

export default logger
