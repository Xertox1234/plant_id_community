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
  PAGE_LOAD: 30000, // 30s for initial page load with networkidle
  ROUTE_CHANGE: 10000, // 10s for client-side routing navigation

  // Element visibility
  ELEMENT_VISIBLE: 5000, // 5s for element to become visible
  ELEMENT_QUICK_CHECK: 2000, // 2s for quick visibility checks
  ELEMENT_IMMEDIATE: 3000, // 3s for elements that should appear quickly

  // API operations
  API_RESPONSE: 2000, // 2s for API data to load and update UI
  POST_CREATION: 3000, // 3s for forum post creation + DB write

  // UI animations
  MENU_ANIMATION: 500, // 500ms for dropdown menu animations
  TRANSITION: 300, // 300ms for standard CSS transitions

  // Element interactions
  SELECTOR_WAIT: 10000, // 10s for waitForSelector (matches Playwright default)

  // Whole-test budgets
  SETUP_TEST: 60000, // 60s for auth.setup.js: reset_ratelimits (todo 312) + login,
  // on top of the default 30s config timeout it already runs close to
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
 * Selector for a real forum board/thread link on the current page.
 *
 * The AppShell header carries `/forum/search` and `/forum/new-thread` on EVERY
 * page, and the forum hero repeats both inside `#main-content` ahead of the board
 * list — so a bare `a[href^="/forum/"]` + `.first()` grabs chrome, not content,
 * and the click lands on the wrong URL. `docs/rules/testing.md` records this
 * biting three specs across PR #536/#537; it is defined once here so the next
 * spec cannot re-derive it wrongly.
 *
 * The exclusions are PREFIX matches, not exact ones: a board page's CTA carries a
 * query string (`/forum/new-thread?category=54-general-discussion`), which an
 * `[href="/forum/new-thread"]` exact match does NOT exclude — so `.first()` on a
 * board page lands on "New Thread" instead of the first thread.
 */
export const FORUM_CONTENT_LINK =
  '#main-content a[href^="/forum/"]:not([href^="/forum/new-thread"]):not([href^="/forum/search"])';

/**
 * Selector for a thread link *within* the board currently open.
 *
 * Needed for the second hop of browse → board → thread. `toHaveURL` resolves the
 * moment the SPA updates the URL, which is before the board's own markup replaces
 * the index's, so a generic forum-link locator can still match a stale board card
 * and click straight back to the board you are already on. Anchoring to the live
 * board path makes that structurally impossible: only a thread under this board
 * matches, and the board's "New Thread" CTA
 * (`/forum/new-thread?category=<slug>`) does not.
 *
 * @param {string} boardPath e.g. `/forum/54-general-discussion`
 */
export function forumThreadLinkIn(boardPath) {
  return `#main-content a[href^="${boardPath}/"]`;
}

/**
 * Auth state directory
 */
export const E2E_AUTH_DIR = '.auth';

/**
 * Auth state file path for a given setup project.
 *
 * Each authenticated project gets its OWN state file, written by its own setup
 * project, so the two never share a refresh token (todo 329): auth.spec.js's
 * "can logout successfully" blacklists the token backing whatever state it loaded
 * (backend/apps/users/views.py), which under one shared `.auth/user.json` would
 * invalidate the other project's session mid-run.
 *
 * setup-chromium -> .auth/user-chromium.json
 * setup-firefox  -> .auth/user-firefox.json
 *
 * This is the single source for those paths: auth.setup.js writes through it, and
 * playwright.config.ts derives each authenticated project's `storageState` from it
 * using the same project-name constant it passes to `dependencies`. Nothing
 * hardcodes a path, so a setup project rename cannot leave a project reading a file
 * no one writes.
 */
export function authFileFor(setupProjectName) {
  const browser = setupProjectName.replace(/^setup-/, '');
  if (!browser || browser === setupProjectName) {
    throw new Error(
      `authFileFor() expects a "setup-<browser>" project name, got "${setupProjectName}". ` +
        'Rename the setup project or update playwright.config.ts.'
    );
  }
  return `${E2E_AUTH_DIR}/user-${browser}.json`;
}
