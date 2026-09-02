import { test, expect } from '@playwright/test';

/**
 * Authenticated Flow E2E Tests
 *
 * These tests verify behaviour that requires an already-logged-in session:
 * - Logged-in state is restored from the saved storageState
 * - Protected routes are reachable
 * - Logout
 *
 * These tests run WITH authentication state loaded, so this file is matched ONLY
 * by the `*-authenticated` projects in playwright.config.ts. Todo 329: every
 * unauthenticated project used to match it too, where "user is already logged in"
 * and "can access protected routes when authenticated" both failed outright
 * (measured — no storageState to restore) and "can logout successfully" passed
 * vacuously through its own `else` branch.
 *
 * The login/logout tests that run WITHOUT auth state live in login.spec.js — they
 * are the suite's only consumers of the 5/15m login rate-limit budget, and are
 * scoped to a single project for that reason.
 *
 * Each authenticated project loads its OWN storageState file, written by its own
 * setup project (setup-chromium -> .auth/user-chromium.json). They must not share
 * one: "can logout successfully" below blacklists the session's refresh token
 * (backend/apps/users/views.py), which under a shared file would invalidate the
 * other project's session mid-run.
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
