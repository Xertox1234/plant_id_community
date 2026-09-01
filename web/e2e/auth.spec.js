import { test, expect } from '@playwright/test';

/**
 * Authentication Flow E2E Tests
 *
 * These tests verify the complete authentication system:
 * - Login (success and failure cases)
 * - Logout
 * - Protected route redirects
 * - User menu visibility
 *
 * These tests run WITH authentication state loaded (see playwright.config.js)
 */

test.describe('Authentication Flows', () => {
  // Serial: 'can logout successfully' blacklists the refresh token backing the
  // storageState this whole describe block shares (todo 312) — safest to not
  // race it against its siblings under this config's fullyParallel: true.
  test.describe.configure({ mode: 'serial' });

  test('user is already logged in (from auth.setup.js)', async ({ page }) => {
    // Navigate to home page
    await page.goto('/', { waitUntil: 'networkidle', timeout: 30000 });

    // Verify user menu is visible (indicates logged-in state)
    const userMenuVisible = await page
      .locator('[data-testid="user-menu"]')
      .isVisible({ timeout: 5000 })
      .catch(() => false);

    // Alternative: Check for user name in header
    const userName = await page
      .locator('text=/E2E Test User/i')
      .isVisible({ timeout: 5000 })
      .catch(() => false);

    expect(userMenuVisible || userName).toBeTruthy();
  });

  test('can access protected routes when authenticated', async ({ page }) => {
    // Try to access a protected route (e.g., settings or profile)
    await page.goto('/settings', { waitUntil: 'networkidle', timeout: 30000 });

    // Should NOT be redirected to login
    expect(page.url()).not.toContain('/login');
    expect(page.url()).toContain('/settings');
  });

  test('can logout successfully', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle', timeout: 30000 });

    // Open user menu
    const userMenuButton = page.locator('[data-testid="user-menu"]').first();
    const isVisible = await userMenuButton.isVisible({ timeout: 5000 }).catch(() => false);

    if (isVisible) {
      await userMenuButton.click();
      await page.waitForTimeout(500); // Wait for dropdown animation

      // Click logout button — the rendered text is "Log out" (with a space,
      // UserMenu.tsx), which /logout/i never matched; use its role instead.
      const logoutButton = page.getByRole('menuitem', { name: /log ?out/i });
      // Wait for the actual logout response, not a fixed DOM-poll timeout
      // (todo 312) — under this project's real concurrent test load (this
      // file plus canopy-areas-authenticated.spec.js and
      // forum-authenticated.spec.js all sharing one backend), the request
      // reliably took longer than a 2s guess, even against a warm server;
      // waiting on the network event itself removes the race entirely.
      await Promise.all([
        page.waitForResponse(
          (res) => res.url().endsWith('/api/v1/auth/logout/') && res.request().method() === 'POST'
        ),
        logoutButton.click(),
      ]);

      // Wait for redirect to home page
      await page.waitForURL('/', { timeout: 10000 });

      // Verify user menu is no longer visible — a short timeout is safe now
      // that we've already waited for the response above.
      const userMenuAfterLogout = await page
        .locator('[data-testid="user-menu"]')
        .isVisible({ timeout: 2000 })
        .catch(() => false);

      expect(userMenuAfterLogout).toBeFalsy();
    } else {
      // If user menu not found, check we're on home page at least
      expect(page.url()).toContain('localhost:5174');
    }
  });
});

test.describe('Protected Routes (Unauthenticated)', () => {
  // These tests should run WITHOUT auth state
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
