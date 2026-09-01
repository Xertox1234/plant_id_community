import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test as setup, expect } from '@playwright/test';
import { E2E_TIMEOUTS, E2E_URLS, E2E_TEST_USER, E2E_AUTH_FILE } from './config.js';

const BACKEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../backend');

/**
 * Authentication Setup for E2E Tests
 *
 * This file runs BEFORE all other tests (only for projects that depend on the
 * 'setup' project — an unauthenticated-only run like --project=chromium never
 * triggers it) to:
 * 1. Reset the shared IP-based login rate limit (todo 312 — auth.spec.js's own
 *    login attempts plus this file's real login otherwise exhaust the 5/15m
 *    budget across two runs in a row)
 * 2. Log in as the test user (e2e_test_user)
 * 3. Save the authentication state (cookies, localStorage)
 * 4. Store it in .auth/user.json for reuse
 *
 * Other tests can then load this state instead of logging in repeatedly.
 *
 * Prerequisites:
 * - Test user must exist (run: python manage.py create_test_user)
 * - Both servers must be running (Django + Vite)
 */

setup('authenticate as test user', async ({ page }) => {
  setup.setTimeout(E2E_TIMEOUTS.SETUP_TEST);

  // Reset rate-limit counters before every run — automatic, not a step a
  // human has to remember between runs (see todo 312's Work Log).
  execSync('source venv/bin/activate && python manage.py reset_ratelimits', {
    cwd: BACKEND_DIR,
    stdio: 'inherit',
    shell: '/bin/bash',
  });

  // Navigate to login page
  await page.goto(`${E2E_URLS.FRONTEND}/login`, {
    waitUntil: 'networkidle',
    timeout: E2E_TIMEOUTS.PAGE_LOAD,
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
  const userMenuVisible = await page
    .locator('[data-testid="user-menu"]')
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
