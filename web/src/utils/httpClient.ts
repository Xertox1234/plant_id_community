/**
 * HTTP Client with Request ID Propagation
 *
 * Axios instance configured with interceptors to automatically
 * add X-Request-ID header for distributed tracing.
 *
 * Features:
 * - Automatic X-Request-ID header injection
 * - Request/response logging with structured logger
 * - Error handling with Sentry integration
 * - CSRF token handling for Django backend
 *
 * Usage:
 * ```javascript
 * import apiClient from '../utils/httpClient'
 *
 * // All requests automatically include X-Request-ID header
 * const response = await apiClient.get('/api/v2/blog-posts')
 * ```
 *
 * @example
 * // Before:
 * import axios from 'axios'
 * const response = await axios.get(`${API_URL}/api/v2/blog-posts`)
 *
 * // After:
 * import apiClient from '../utils/httpClient'
 * const response = await apiClient.get('/api/v2/blog-posts')
 */

import axios, { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { logger } from './logger'

/**
 * Get CSRF token from cookies
 * Django sets csrftoken cookie that we need to include in requests
 *
 * @returns CSRF token or null if not found
 */
function getCsrfToken(): string | null {
  try {
    const name = 'csrftoken'
    const value = `; ${document.cookie}`
    const parts = value.split(`; ${name}=`)
    if (parts.length === 2) {
      return parts.pop()?.split(';').shift() || null
    }
  } catch {
    // Silently fail if cookie parsing fails
  }
  return null
}

/**
 * Create axios instance with base configuration
 */
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000, // 30 second timeout
  withCredentials: true, // Include cookies for Django session auth
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * Request interceptor
 * Adds X-Request-ID header and logs outgoing requests
 */
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    try {
      // Add X-Request-ID header from session storage
      const requestId = sessionStorage.getItem('requestId')
      if (requestId) {
        config.headers['X-Request-ID'] = requestId
      }

      // Add CSRF token from cookies if available
      const csrfToken = getCsrfToken()
      if (csrfToken) {
        config.headers['X-CSRFToken'] = csrfToken
      }

      // Log outgoing request (development only)
      if (import.meta.env.DEV) {
        logger.debug('HTTP request', {
          component: 'httpClient',
          method: config.method?.toUpperCase(),
          url: config.url,
          requestId,
        })
      }
    } catch (error) {
      // Silently fail - don't block request
      logger.warn('Request interceptor error', {
        component: 'httpClient',
        error,
      })
    }

    return config
  },
  (error: AxiosError) => {
    logger.error('Request interceptor error', {
      component: 'httpClient',
      error,
    })
    return Promise.reject(error)
  }
)

/**
 * Response interceptor
 * Logs responses and handles errors
 */
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // Log successful response (development only)
    if (import.meta.env.DEV) {
      logger.debug('HTTP response', {
        component: 'httpClient',
        status: response.status,
        url: response.config.url,
      })
    }
    return response
  },
  (error: AxiosError) => {
    // Log error response
    const status = error.response?.status
    const url = error.config?.url
    const message = (error.response?.data as { message?: string })?.message || error.message

    logger.error('HTTP error', {
      component: 'httpClient',
      error,
      status,
      url,
      message,
    })

    return Promise.reject(error)
  }
)

export default apiClient
