/**
 * Authentication Service
 *
 * Handles all authentication-related API calls to the Django backend.
 * Uses cookie-based JWT authentication (HttpOnly cookies).
 *
 * API Endpoints (Django backend):
 * - GET  /api/v1/auth/csrf/ (fetch CSRF token)
 * - POST /api/v1/auth/login/
 * - POST /api/v1/auth/register/
 * - POST /api/v1/auth/logout/
 * - GET  /api/v1/auth/user/ (current user)
 */

import { logger } from '../utils/logger'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// HTTPS enforcement for production
if (import.meta.env.PROD && API_URL.startsWith('http://')) {
  logger.error('[authService] SECURITY ERROR: API_URL must use HTTPS in production')
  throw new Error('Cannot send credentials over HTTP in production. Set VITE_API_URL to https:// endpoint.')
}

/**
 * Get CSRF token from cookie
 * Django sets csrftoken cookie that must be sent as X-CSRFToken header
 * @returns {string|null} CSRF token or null if not found
 */
function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/)
  return match ? match[1] : null
}

/**
 * Fetch CSRF token from Django backend
 * This endpoint sets the csrftoken cookie
 * @returns {Promise<void>}
 */
async function fetchCsrfToken() {
  try {
    await fetch(`${API_URL}/api/v1/auth/csrf/`, {
      method: 'GET',
      credentials: 'include', // Include cookies
    })
  } catch (error) {
    logger.warn('[authService] Failed to fetch CSRF token:', error)
  }
}

/**
 * Login user with email and password
 * @param {Object} credentials - User credentials
 * @param {string} credentials.email - User email
 * @param {string} credentials.password - User password
 * @returns {Promise<Object>} User data
 */
export async function login(credentials) {
  try {
    // Fetch CSRF token first if we don't have one
    if (!getCsrfToken()) {
      await fetchCsrfToken()
    }

    const csrfToken = getCsrfToken()
    const headers = {
      'Content-Type': 'application/json',
    }

    // Add CSRF token if available (required by Django backend)
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken
    }

    const response = await fetch(`${API_URL}/api/v1/auth/login/`, {
      method: 'POST',
      headers,
      credentials: 'include', // Include cookies
      body: JSON.stringify(credentials),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.message || 'Login failed')
    }

    const data = await response.json()

    // Store user in sessionStorage (cleared on tab close - more secure than localStorage)
    sessionStorage.setItem('user', JSON.stringify(data.user))

    return data.user
  } catch (error) {
    logger.error('[authService] Login error:', error)
    throw error
  }
}

/**
 * Sign up new user
 * @param {Object} userData - New user data
 * @param {string} userData.name - User's full name
 * @param {string} userData.email - User's email
 * @param {string} userData.password - User's password
 * @returns {Promise<Object>} User data
 */
export async function signup(userData) {
  try {
    // Fetch CSRF token first if we don't have one
    if (!getCsrfToken()) {
      await fetchCsrfToken()
    }

    const csrfToken = getCsrfToken()
    const headers = {
      'Content-Type': 'application/json',
    }

    // Add CSRF token if available (required by Django backend)
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken
    }

    const response = await fetch(`${API_URL}/api/v1/auth/register/`, {
      method: 'POST',
      headers,
      credentials: 'include', // Include cookies
      body: JSON.stringify(userData),
    })

    if (!response.ok) {
      let errorData
      try {
        errorData = await response.json()
      } catch (e) {
        throw new Error(`Signup failed with status ${response.status}`)
      }

      // Log detailed error for debugging
      logger.error('[authService] Signup failed:', {
        status: response.status,
        error: errorData
      })

      // Extract error message from backend
      const errorMessage = errorData.error?.message || errorData.message || JSON.stringify(errorData)
      throw new Error(errorMessage)
    }

    const data = await response.json()

    // Store user in sessionStorage (cleared on tab close - more secure than localStorage)
    sessionStorage.setItem('user', JSON.stringify(data.user))

    return data.user
  } catch (error) {
    logger.error('[authService] Signup error:', error)
    throw error
  }
}

/**
 * Logout current user
 * Clears cookie and sessionStorage
 * @returns {Promise<void>}
 */
export async function logout() {
  try {
    const csrfToken = getCsrfToken()
    const headers = {}

    // Add CSRF token if available (required by Django backend)
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken
    }

    const response = await fetch(`${API_URL}/api/v1/auth/logout/`, {
      method: 'POST',
      headers,
      credentials: 'include', // Include cookies
    })

    if (!response.ok) {
      logger.warn('[authService] Logout API failed, clearing local state anyway')
    }

    // Always clear sessionStorage regardless of API response
    sessionStorage.removeItem('user')
  } catch (error) {
    logger.error('[authService] Logout error:', error)
    // Still clear sessionStorage even if API fails
    sessionStorage.removeItem('user')
    throw error
  }
}

/**
 * Get current user from backend
 * Used to verify authentication status on app load
 * @returns {Promise<Object|null>} User data or null if not authenticated
 */
export async function getCurrentUser() {
  try {
    const response = await fetch(`${API_URL}/api/v1/auth/user/`, {
      method: 'GET',
      credentials: 'include', // Include cookies
    })

    if (!response.ok) {
      // Not authenticated - clear sessionStorage
      sessionStorage.removeItem('user')
      return null
    }

    const data = await response.json()

    // Update sessionStorage with fresh user data
    sessionStorage.setItem('user', JSON.stringify(data))

    return data
  } catch (error) {
    logger.error('[authService] Get current user error:', error)
    // On error, try to get user from sessionStorage as fallback
    const storedUser = sessionStorage.getItem('user')
    return storedUser ? JSON.parse(storedUser) : null
  }
}

/**
 * Get user from sessionStorage (synchronous)
 * Used for initial state on app load
 * @returns {Object|null} User data or null
 */
export function getStoredUser() {
  try {
    const storedUser = sessionStorage.getItem('user')
    return storedUser ? JSON.parse(storedUser) : null
  } catch (error) {
    logger.error('[authService] Error parsing stored user:', error)
    return null
  }
}

export const authService = {
  login,
  signup,
  logout,
  getCurrentUser,
  getStoredUser,
}
