import { test as setup, expect } from '@playwright/test';
import { E2E_TIMEOUTS, E2E_URLS, E2E_TEST_USER, E2E_AUTH_FILE } from './config.js';

/**
 * Authentication Setup for E2E Tests
 *
 * This file runs BEFORE all other tests to:
 * 1. Log in as the test user (e2e_test_user)
 * 2. Save the authentication state (cookies, localStorage)
 * 3. Store it in .auth/user.json for reuse
 *
 * Other tests can then load this state instead of logging in repeatedly.
 *
 * Prerequisites:
 * - Test user must exist (run: python manage.py create_test_user)
 * - Both servers must be running (Django + Vite)
 */

setup('authenticate as test user', async ({ page }) => {
  // Navigate to login page
  await page.goto(`${E2E_URLS.FRONTEND}/login`, {
    waitUntil: 'networkidle',
    timeout: E2E_TIMEOUTS.PAGE_LOAD
  });

  // Fill in login form
  await page.fill('input[type="email"]', E2E_TEST_USER.EMAIL);
  await page.fill('input[type="password"]', E2E_TEST_USER.PASSWORD);

  // Submit login form
  await page.click('button[type="submit"]');

  // Wait for redirect to home page (successful login)
  await page.waitForURL(E2E_URLS.FRONTEND + '/', { timeout: E2E_TIMEOUTS.ROUTE_CHANGE });

  // Verify we're authenticated by checking for user menu
  // LoginPage redirects to '/' on success, and Header shows UserMenu when authenticated
  const userMenuVisible = await page.locator('[data-testid="user-menu"]')
    .isVisible({ timeout: E2E_TIMEOUTS.ELEMENT_VISIBLE })
    .catch(() => false);

  if (!userMenuVisible) {
    // Alternative: Check if we're NOT on the login page anymore
    const currentUrl = page.url();
    expect(currentUrl).not.toContain('/login');
  }

  // Save authentication state to file
  await page.context().storageState({ path: E2E_AUTH_FILE });

  console.log('✅ Authentication state saved to', E2E_AUTH_FILE);
});
