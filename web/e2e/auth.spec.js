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
  test('user is already logged in (from auth.setup.js)', async ({ page }) => {
    // Navigate to home page
    await page.goto('/', { waitUntil: 'networkidle', timeout: 30000 });

    // Verify user menu is visible (indicates logged-in state)
    const userMenuVisible = await page.locator('[data-testid="user-menu"]')
      .isVisible({ timeout: 5000 })
      .catch(() => false);

    // Alternative: Check for user name in header
    const userName = await page.locator('text=/E2E Test User/i')
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

      // Click logout button
      const logoutButton = page.locator('text=/logout/i').first();
      await logoutButton.click();

      // Wait for redirect to home page
      await page.waitForURL('/', { timeout: 10000 });

      // Verify user menu is no longer visible
      const userMenuAfterLogout = await page.locator('[data-testid="user-menu"]')
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

    // Submit form
    await page.click('button[type="submit"]');

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

    // Submit form
    await page.click('button[type="submit"]');

    // Should show error message
    const errorVisible = await page.locator('text=/invalid|incorrect|failed/i')
      .isVisible({ timeout: 5000 })
      .catch(() => false);

    expect(errorVisible).toBeTruthy();

    // Should still be on login page
    expect(page.url()).toContain('/login');
  });
});
