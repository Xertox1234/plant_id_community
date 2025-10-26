/**
 * Production-Safe Logger
 *
 * Provides logging utilities that are development-friendly
 * but safe for production environments.
 *
 * In development: Logs to console
 * In production: Sends to Sentry for error tracking
 *
 * @example
 * import { logger } from '../utils/logger'
 * logger.error('[LoginPage] Login failed:', error)
 */

import * as Sentry from '@sentry/react'

/**
 * Log error message
 * @param {string} message - Error message with context prefix
 * @param {Error|any} error - Error object or additional data
 */
export function logError(message, error) {
  if (import.meta.env.DEV) {
    console.error(message, error)
  } else if (import.meta.env.PROD) {
    // Send to Sentry in production
    Sentry.captureException(error, {
      tags: { context: message },
      extra: { message },
    })
  }
}

/**
 * Log warning message
 * @param {string} message - Warning message
 * @param {any} data - Additional data
 */
export function logWarning(message, data) {
  if (import.meta.env.DEV) {
    console.warn(message, data)
  } else if (import.meta.env.PROD) {
    // Send to Sentry as warning level in production
    Sentry.captureMessage(message, {
      level: 'warning',
      extra: data ? { data } : {},
    })
  }
}

/**
 * Log info message (development only)
 * @param {string} message - Info message
 * @param {any} data - Additional data
 */
export function logInfo(message, data) {
  if (import.meta.env.DEV) {
    console.log(message, data)
  }
}

/**
 * Logger object with method interface
 */
export const logger = {
  error: logError,
  warn: logWarning,
  info: logInfo,
}

export default logger
