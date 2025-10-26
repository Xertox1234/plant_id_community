/**
 * Authentication Service
 *
 * Handles all authentication-related API calls to the Django backend.
 * Uses cookie-based JWT authentication (HttpOnly cookies).
 *
 * API Endpoints (Django backend):
 * - POST /api/v1/users/login/
 * - POST /api/v1/users/signup/
 * - POST /api/v1/users/logout/
 * - GET  /api/v1/users/me/
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/**
 * Login user with email and password
 * @param {Object} credentials - User credentials
 * @param {string} credentials.email - User email
 * @param {string} credentials.password - User password
 * @returns {Promise<Object>} User data
 */
export async function login(credentials) {
  try {
    const response = await fetch(`${API_URL}/api/v1/users/login/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Include cookies
      body: JSON.stringify(credentials),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.message || 'Login failed')
    }

    const data = await response.json()

    // Store user in localStorage for persistence
    localStorage.setItem('user', JSON.stringify(data.user))

    return data.user
  } catch (error) {
    console.error('[authService] Login error:', error)
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
    const response = await fetch(`${API_URL}/api/v1/users/signup/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Include cookies
      body: JSON.stringify(userData),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.message || 'Signup failed')
    }

    const data = await response.json()

    // Store user in localStorage for persistence
    localStorage.setItem('user', JSON.stringify(data.user))

    return data.user
  } catch (error) {
    console.error('[authService] Signup error:', error)
    throw error
  }
}

/**
 * Logout current user
 * Clears cookie and localStorage
 * @returns {Promise<void>}
 */
export async function logout() {
  try {
    const response = await fetch(`${API_URL}/api/v1/users/logout/`, {
      method: 'POST',
      credentials: 'include', // Include cookies
    })

    if (!response.ok) {
      console.warn('[authService] Logout API failed, clearing local state anyway')
    }

    // Always clear localStorage regardless of API response
    localStorage.removeItem('user')
  } catch (error) {
    console.error('[authService] Logout error:', error)
    // Still clear localStorage even if API fails
    localStorage.removeItem('user')
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
    const response = await fetch(`${API_URL}/api/v1/users/me/`, {
      method: 'GET',
      credentials: 'include', // Include cookies
    })

    if (!response.ok) {
      // Not authenticated - clear localStorage
      localStorage.removeItem('user')
      return null
    }

    const data = await response.json()

    // Update localStorage with fresh user data
    localStorage.setItem('user', JSON.stringify(data))

    return data
  } catch (error) {
    console.error('[authService] Get current user error:', error)
    // On error, try to get user from localStorage as fallback
    const storedUser = localStorage.getItem('user')
    return storedUser ? JSON.parse(storedUser) : null
  }
}

/**
 * Get user from localStorage (synchronous)
 * Used for initial state on app load
 * @returns {Object|null} User data or null
 */
export function getStoredUser() {
  try {
    const storedUser = localStorage.getItem('user')
    return storedUser ? JSON.parse(storedUser) : null
  } catch (error) {
    console.error('[authService] Error parsing stored user:', error)
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
