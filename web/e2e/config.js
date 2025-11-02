/**
 * E2E Test Configuration
 *
 * Centralized configuration for E2E tests including timeouts,
 * URLs, and test credentials.
 *
 * This file follows the "Constants (No magic numbers)" pattern
 * from CLAUDE.md to ensure maintainability.
 */

/**
 * Timeout values for various E2E operations (in milliseconds)
 */
export const E2E_TIMEOUTS = {
  // Page loading
  PAGE_LOAD: 30000,           // 30s for initial page load with networkidle
  ROUTE_CHANGE: 10000,         // 10s for client-side routing navigation

  // Element visibility
  ELEMENT_VISIBLE: 5000,       // 5s for element to become visible
  ELEMENT_QUICK_CHECK: 2000,   // 2s for quick visibility checks
  ELEMENT_IMMEDIATE: 3000,     // 3s for elements that should appear quickly

  // API operations
  API_RESPONSE: 2000,          // 2s for API data to load and update UI
  POST_CREATION: 3000,         // 3s for forum post creation + DB write

  // UI animations
  MENU_ANIMATION: 500,         // 500ms for dropdown menu animations
  TRANSITION: 300,             // 300ms for standard CSS transitions

  // Element interactions
  SELECTOR_WAIT: 10000,        // 10s for waitForSelector (matches Playwright default)
};

/**
 * URLs for testing
 */
export const E2E_URLS = {
  FRONTEND: 'http://localhost:5174',
  BACKEND: 'http://localhost:8000',
  CSRF_ENDPOINT: 'http://localhost:8000/api/v1/auth/csrf/',
};

/**
 * Test user credentials
 *
 * NOTE: These credentials match the test user created by:
 * python manage.py create_test_user
 */
export const E2E_TEST_USER = {
  EMAIL: 'e2e@test.com',
  PASSWORD: 'E2ETestPassword123456',
  USERNAME: 'e2e_test_user',
  FIRST_NAME: 'E2E',
  LAST_NAME: 'Test User',
};

/**
 * Auth state file path
 */
export const E2E_AUTH_FILE = '.auth/user.json';
