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
import { getCsrfToken, clearCsrfToken } from './csrf'

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
 * Adds X-Request-ID header and CSRF token, logs outgoing requests
 */
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    try {
      // Add X-Request-ID header from session storage
      const requestId = sessionStorage.getItem('requestId')
      if (requestId) {
        config.headers['X-Request-ID'] = requestId
      }

      // Add CSRF token from API endpoint (Issue #144 fix)
      // Only fetch token for state-changing requests
      const needsCsrfToken = ['post', 'put', 'patch', 'delete'].includes(
        config.method?.toLowerCase() || ''
      )
      if (needsCsrfToken) {
        const csrfToken = await getCsrfToken()
        if (csrfToken) {
          config.headers['X-CSRFToken'] = csrfToken
        }
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
 * Logs responses, handles errors, auto-retries CSRF failures
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
  async (error: AxiosError) => {
    const status = error.response?.status
    const url = error.config?.url
    const message = (error.response?.data as { message?: string })?.message || error.message

    // Handle CSRF token expiration (Issue #144 fix)
    // If we get a 403 CSRF error, refresh token and retry once
    if (status === 403 && message?.toLowerCase().includes('csrf')) {
      logger.warn('CSRF token expired, refreshing and retrying', {
        component: 'httpClient',
        url,
      })

      // Clear cached token and fetch new one
      clearCsrfToken()
      const newToken = await getCsrfToken()

      if (newToken && error.config) {
        // Retry the original request with new token
        error.config.headers['X-CSRFToken'] = newToken
        return apiClient.request(error.config)
      }
    }

    // Log error response
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
