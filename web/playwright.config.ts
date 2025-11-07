import { defineConfig, devices } from '@playwright/test';

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
    timeout: 5000
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
    ['html', { open: 'never' }],  // Never auto-open browser (prevents hangs)
    ['list'],                      // Console output
    process.env.CI ? ['github'] : ['list']  // GitHub Actions integration
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
      timeout: 120 * 1000,  // 2 minutes
      stdout: 'pipe',       // Show server logs
      stderr: 'pipe',
    },

    // Backend - Django server
    {
      command: 'cd ../backend && source venv/bin/activate && python manage.py runserver 8000',
      url: 'http://localhost:8000/api/v1/auth/csrf/',  // Health check endpoint
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,  // 2 minutes
      stdout: 'pipe',
      stderr: 'pipe',
    },
  ],

  // Configure projects for multiple browsers
  projects: [
    // Setup project - runs first to authenticate and save state
    {
      name: 'setup',
      testMatch: /auth\.setup\.js/,
    },

    // Unauthenticated tests (e.g., health checks, login page)
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      testIgnore: /auth\.setup\.js/,
    },

    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
      testIgnore: /auth\.setup\.js/,
    },

    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
      testIgnore: /auth\.setup\.js/,
    },

    // Mobile viewports (unauthenticated)
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
      testIgnore: /auth\.setup\.js/,
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
      testIgnore: /auth\.setup\.js/,
    },

    // Authenticated tests (forum, protected routes)
    {
      name: 'chromium-authenticated',
      use: {
        ...devices['Desktop Chrome'],
        storageState: '.auth/user.json',
      },
      dependencies: ['setup'],
      testMatch: /(forum-authenticated|auth\.spec)\.js/,
    },

    {
      name: 'firefox-authenticated',
      use: {
        ...devices['Desktop Firefox'],
        storageState: '.auth/user.json',
      },
      dependencies: ['setup'],
      testMatch: /(forum-authenticated|auth\.spec)\.js/,
    },
  ],
});
