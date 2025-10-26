/**
 * Production-Safe Logger
 *
 * Provides logging utilities that are development-friendly
 * but safe for production environments.
 *
 * In development: Logs to console
 * In production: Silent (or integrate with monitoring service like Sentry)
 *
 * @example
 * import { logger } from '../utils/logger'
 * logger.error('[LoginPage] Login failed:', error)
 */

/**
 * Log error message
 * @param {string} message - Error message with context prefix
 * @param {Error|any} error - Error object or additional data
 */
export function logError(message, error) {
  if (import.meta.env.DEV) {
    console.error(message, error)
  }

  // TODO: In production, send to monitoring service
  // if (import.meta.env.PROD && window.errorTracker) {
  //   window.errorTracker.captureException(error, {
  //     tags: { context: message }
  //   })
  // }
}

/**
 * Log warning message
 * @param {string} message - Warning message
 * @param {any} data - Additional data
 */
export function logWarning(message, data) {
  if (import.meta.env.DEV) {
    console.warn(message, data)
  }

  // TODO: In production, send to monitoring service
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
