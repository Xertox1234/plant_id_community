import { defineConfig, devices } from '@playwright/test';
import { authFileFor } from './e2e/config.js';

/**
 * Setup project names. The authenticated projects derive both their
 * `dependencies` entry and their `storageState` path from these, so a rename
 * moves all three together — the state file an authenticated project loads is
 * by construction the one its own setup project writes (todo 329).
 */
const SETUP_CHROMIUM = 'setup-chromium';
const SETUP_FIREFOX = 'setup-firefox';

/**
 * Playwright E2E Testing Configuration
 *
 * This config manages both frontend (Vite) and backend (Django) servers,
 * ensuring they're ready before tests run.
 *
 * Key features:
 * - Auto-starts and waits for both servers
 * - Prevents terminal crashes with proper reporter config
 * - Reuses existing servers in development
 * - Optimized for CI/CD environments
 */
export default defineConfig({
  // Test directory
  testDir: './e2e',

  // Timeout for each test
  timeout: 30000,

  // Expect timeout for assertions
  expect: {
    timeout: 5000,
  },

  // Run tests in files in parallel
  fullyParallel: true,

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Limit workers on CI to prevent memory issues
  workers: process.env.CI ? 1 : undefined,

  // Reporter configuration - CRITICAL to prevent terminal crashes
  reporter: [
    ['html', { open: 'never' }], // Never auto-open browser (prevents hangs)
    ['list'], // Console output
    process.env.CI ? ['github'] : ['list'], // GitHub Actions integration
  ],

  // Shared settings for all projects
  use: {
    // Base URL for your frontend
    baseURL: 'http://localhost:5174',

    // Collect trace on first retry of a failed test
    trace: 'on-first-retry',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Video on failure
    video: 'retain-on-failure',

    // Headless by default, can override with --headed flag
    headless: true,
  },

  // Web servers configuration - STARTS BOTH FRONTEND AND BACKEND
  webServer: [
    // Frontend - Vite dev server
    {
      command: 'npm run dev',
      url: 'http://localhost:5174',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000, // 2 minutes
      stdout: 'pipe', // Show server logs
      stderr: 'pipe',
    },

    // Backend - Django server
    {
      command: 'cd ../backend && source venv/bin/activate && python manage.py runserver 8000',
      url: 'http://localhost:8000/api/v1/auth/csrf/', // Health check endpoint
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000, // 2 minutes
      stdout: 'pipe',
      stderr: 'pipe',
    },
  ],

  /**
   * Project layout — two constraints drive it (todo 329):
   *
   * 1. LOGIN RATE-LIMIT BUDGET. `POST /api/v1/auth/login/` is IP-rate-limited to
   *    5/15m (backend/apps/plant_identification/constants.py); the 6th request in
   *    the window 429s, and every POST counts, not just failed ones. login.spec.js
   *    costs 2 per project that runs it and each setup project costs 1, so a full
   *    `npm run test:e2e` currently spends 2 + 1 + 1 = 4 of 5. Adding login.spec.js
   *    to a second project costs 2 more and breaks the budget. Before todo 329
   *    those tests lived in auth.spec.js, which every one of the 7 non-setup
   *    projects matched: 15 POSTs against a budget of 5.
   *
   * 2. NO SHARED AUTH STATE. auth.spec.js's "can logout successfully" blacklists
   *    the refresh token backing the storageState it loaded. One setup project per
   *    authenticated browser, each writing its own file, keeps one project's logout
   *    from invalidating the other's session mid-run (`fullyParallel: true` means
   *    they overlap, and `mode: 'serial'` only orders tests *within* a project).
   */
  projects: [
    // Setup projects - one per authenticated browser, each logging in separately
    // so no two authenticated projects share a refresh token.
    {
      name: SETUP_CHROMIUM,
      use: { ...devices['Desktop Chrome'] },
      testMatch: /auth\.setup\.js/,
    },
    {
      name: SETUP_FIREFOX,
      use: { ...devices['Desktop Firefox'] },
      testMatch: /auth\.setup\.js/,
    },

    // Unauthenticated tests (e.g., health checks, login page).
    // `chromium` is the ONLY project that runs login.spec.js - see constraint 1.
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      testIgnore:
        /(auth\.setup|auth\.spec|forum-authenticated\.spec|canopy-areas-authenticated\.spec|forum-mention\.spec)\.js/,
    },

    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
      testIgnore:
        /(auth\.setup|auth\.spec|login\.spec|forum-authenticated\.spec|canopy-areas-authenticated\.spec|forum-mention\.spec)\.js/,
    },

    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
      testIgnore:
        /(auth\.setup|auth\.spec|login\.spec|forum-authenticated\.spec|canopy-areas-authenticated\.spec|forum-mention\.spec)\.js/,
    },

    // Mobile viewports (unauthenticated)
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
      testIgnore:
        /(auth\.setup|auth\.spec|login\.spec|forum-authenticated\.spec|canopy-areas-authenticated\.spec|forum-mention\.spec)\.js/,
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
      testIgnore:
        /(auth\.setup|auth\.spec|login\.spec|forum-authenticated\.spec|canopy-areas-authenticated\.spec|forum-mention\.spec)\.js/,
    },

    // Authenticated tests (forum, protected routes). Each loads the state file
    // written by its own setup project - see constraint 2. Both the dependency and
    // the path derive from the same constant, and auth.setup.js writes via the same
    // authFileFor(), so the two cannot drift apart.
    {
      name: 'chromium-authenticated',
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFileFor(SETUP_CHROMIUM),
      },
      dependencies: [SETUP_CHROMIUM],
      testMatch: /(forum-authenticated|canopy-areas-authenticated|forum-mention|auth)\.spec\.js/,
    },

    {
      name: 'firefox-authenticated',
      use: {
        ...devices['Desktop Firefox'],
        storageState: authFileFor(SETUP_FIREFOX),
      },
      dependencies: [SETUP_FIREFOX],
      testMatch: /(forum-authenticated|canopy-areas-authenticated|forum-mention|auth)\.spec\.js/,
    },
  ],
});
