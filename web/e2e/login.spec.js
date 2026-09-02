import { test, expect } from '@playwright/test';

/**
 * Login Flow E2E Tests (UNAUTHENTICATED)
 *
 * Split out of auth.spec.js by todo 329. That file's two describe blocks wanted
 * opposite project sets — "Authentication Flows" needs the `storageState` written
 * by auth.setup.js, while this block explicitly clears it — and one file cannot be
 * scoped two ways in playwright.config.ts.
 *
 * These tests are the E2E suite's ONLY consumers of the shared IP-based login rate
 * limit (5/15m, backend/apps/plant_identification/constants.py), at 2 real
 * POST /api/v1/auth/login/ per project that runs them. They are therefore scoped to
 * the `chromium` project alone: the other four unauthenticated projects exclude this
 * file via testIgnore. Before todo 329, auth.spec.js ran under all 7 non-setup
 * projects, costing 15 login POSTs against a budget of 5 — a full `npm run test:e2e`
 * was structurally guaranteed to 429.
 *
 * Budget accounting for one full invocation: 2 (here) + 1 (setup-chromium) +
 * 1 (setup-firefox) = 4 of 5. Adding another project to this file costs 2 more and
 * breaks the budget.
 */

test.describe('Protected Routes (Unauthenticated)', () => {
  // These tests should run WITHOUT auth state. Redundant under the `chromium`
  // project (which sets no storageState) but kept as the block's own guarantee —
  // it is what makes this file wrong for the authenticated projects.
  test.use({ storageState: { cookies: [], origins: [] } });

  test('protected routes redirect to login when not authenticated', async ({ page }) => {
    // Try to access a protected route
    await page.goto('/settings');

    // Should be redirected to login
    await page.waitForURL(/.*login.*/, { timeout: 10000 });
    expect(page.url()).toContain('/login');
  });

  test('can login with valid credentials', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'networkidle', timeout: 30000 });

    // Fill in login form
    await page.fill('input[type="email"]', 'e2e@test.com');
    await page.fill('input[type="password"]', 'E2ETestPassword123456');

    // Submit and wait for the actual login response, not a fixed URL-poll
    // timeout (todo 312) — this test makes the same rate-limited login POST
    // as its "invalid credentials" sibling below, so it needs the same
    // network-first wait and 429 diagnostic, not just a bigger guessed number.
    const [response] = await Promise.all([
      page.waitForResponse(
        (res) => res.url().endsWith('/api/v1/auth/login/') && res.request().method() === 'POST'
      ),
      page.click('button[type="submit"]'),
    ]);
    if (response.status() === 429) {
      throw new Error(
        'Login rate limit exhausted — run `manage.py reset_ratelimits` ' +
          '(auth.setup.js should already do this automatically; see todo 312).'
      );
    }

    // Wait for redirect to home page
    await page.waitForURL('/', { timeout: 10000 });

    // Verify successful login
    expect(page.url()).toContain('localhost:5174');
    expect(page.url()).not.toContain('/login');
  });

  test('shows error with invalid credentials', async ({ page }) => {
    await page.goto('/login', { waitUntil: 'networkidle', timeout: 30000 });

    // Fill in login form with wrong password
    await page.fill('input[type="email"]', 'e2e@test.com');
    await page.fill('input[type="password"]', 'WrongPassword123');

    // Submit and wait for the actual login response, not a fixed DOM-poll
    // timeout (todo 312) — under this project's real concurrent test load
    // (this file plus canopy-areas-authenticated.spec.js and
    // forum-authenticated.spec.js all sharing one backend), the request
    // reliably took longer than a 5s guess, even against a warm server;
    // waiting on the network event itself removes the race entirely.
    const [response] = await Promise.all([
      page.waitForResponse(
        (res) => res.url().endsWith('/api/v1/auth/login/') && res.request().method() === 'POST'
      ),
      page.click('button[type="submit"]'),
    ]);

    // Fail loudly and specifically if the shared IP-based login rate limit
    // (5/15m, backend/apps/plant_identification/constants.py) is exhausted —
    // that response has no "invalid|incorrect|failed" text at all, so
    // without this check a tripped limit reads as a confusing, unrelated
    // "errorVisible: false" instead of naming the real cause.
    if (response.status() === 429) {
      throw new Error(
        'Login rate limit exhausted — run `manage.py reset_ratelimits` ' +
          '(auth.setup.js should already do this automatically; see todo 312).'
      );
    }

    // Should show error message — a short timeout is safe now that we've
    // already waited for the response above.
    const errorVisible = await page
      .locator('text=/invalid|incorrect|failed/i')
      .isVisible({ timeout: 5000 })
      .catch(() => false);

    expect(errorVisible).toBeTruthy();

    // Should still be on login page
    expect(page.url()).toContain('/login');
  });
});
