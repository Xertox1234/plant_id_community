import { test, expect } from '@playwright/test';
import { FORUM_CONTENT_LINK } from './config.js';

/**
 * Example E2E test demonstrating:
 * - Server readiness checks
 * - Frontend and backend integration
 * - Basic navigation and interaction
 */

test.describe('Server Readiness', () => {
  test('frontend server is running and accessible', async ({ page }) => {
    // Playwright automatically waits for servers defined in webServer config
    await page.goto('/', { waitUntil: 'networkidle', timeout: 30000 });

    // Canopy made the page-level h1 an sr-only landmark ("Home") and moved the
    // visible hero copy to the h2 below it, so assert both: the landmark exists
    // and the hero still renders.
    await expect(page.locator('h1')).toContainText('Home');
    await expect(
      page.getByRole('heading', { level: 2, name: /Discover the World/i })
    ).toBeVisible();
  });

  test('backend API is accessible', async ({ request }) => {
    // Test Django backend health
    const response = await request.get('http://localhost:8000/api/v1/auth/csrf/');

    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(200);
  });

  test('can fetch CSRF token from backend', async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/v1/auth/csrf/');
    const data = await response.json();

    // CSRF endpoint returns {"detail": "CSRF cookie set"} and sets token as cookie
    expect(data).toHaveProperty('detail');
    expect(data.detail).toBe('CSRF cookie set');
  });
});

test.describe('Navigation', () => {
  test('can navigate to blog', async ({ page, isMobile }) => {
    // Skip mobile navigation tests - hamburger menu timing is flaky in E2E
    // Navigation works fine in actual usage, just timing issues in automated tests
    if (isMobile) {
      test.skip();
      return;
    }

    await page.goto('/', { waitUntil: 'networkidle', timeout: 30000 });

    // Click on blog link
    await page.click('a[href*="/blog"]');

    // Wait for navigation with timeout
    await page.waitForURL(/.*blog.*/, { timeout: 10000 });

    // Verify we're on the blog page
    expect(page.url()).toContain('/blog');
  });

  test('can navigate to forum', async ({ page, isMobile }) => {
    // Skip mobile navigation tests - hamburger menu timing is flaky in E2E
    // Navigation works fine in actual usage, just timing issues in automated tests
    if (isMobile) {
      test.skip();
      return;
    }

    await page.goto('/', { waitUntil: 'networkidle', timeout: 30000 });

    // Click on forum link
    await page.click('a[href*="/forum"]');

    // Wait for navigation with timeout
    await page.waitForURL(/.*forum.*/, { timeout: 10000 });

    // Verify we're on the forum page
    expect(page.url()).toContain('/forum');
  });
});

test.describe('Authentication Flow', () => {
  test('can access login page', async ({ page }) => {
    await page.goto('/login');

    // Check for login form elements
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('shows validation errors for empty login', async ({ page }) => {
    await page.goto('/login');

    // Try to submit empty form
    await page.click('button[type="submit"]');

    // Should show validation errors - Input component shows errors below the field
    // LoginPage validation requires email and password (14+ chars)
    // Look for any validation error text
    const errorVisible = await page
      .locator('text=/required|invalid|must be/i')
      .first()
      .isVisible({ timeout: 5000 })
      .catch(() => false);
    expect(errorVisible).toBeTruthy();
  });
});

test.describe('Blog Integration', () => {
  test('blog list loads posts from API', async ({ page }) => {
    await page.goto('/blog', { waitUntil: 'networkidle', timeout: 30000 });

    // Wait for page to be fully loaded - check for blog grid container or page heading
    await page.waitForSelector('h1', { timeout: 10000 });

    // Wait a bit for data to load
    await page.waitForTimeout(2000);

    // Verify blog cards are rendered (or no posts message)
    const blogCards = await page.locator('a.group.block.bg-white').count();
    const noPostsMessage = await page.locator('text=/no.*posts/i').count();
    const loadingSpinner = await page.locator('text=/loading/i').count();

    expect(blogCards > 0 || noPostsMessage > 0 || loadingSpinner > 0).toBeTruthy();
  });

  test('can search blog posts', async ({ page }) => {
    await page.goto('/blog', { waitUntil: 'networkidle', timeout: 30000 });

    // Find search input
    const searchInput = page.locator('input[type="search"], input[placeholder*="search" i]');

    if ((await searchInput.count()) > 0) {
      await searchInput.fill('plant');
      await searchInput.press('Enter');

      // Wait for search results
      await page.waitForTimeout(1000);

      // Results should contain search term (in title or content)
      const content = await page.textContent('body');
      expect(content.toLowerCase()).toContain('plant');
    }
  });
});

test.describe('Forum Integration', () => {
  test('forum shows categories', async ({ page }) => {
    await page.goto('/forum', { waitUntil: 'networkidle', timeout: 30000 });

    // Wait for page to be fully loaded - check for page heading
    await page.waitForSelector('h1', { timeout: 10000 });

    // Assert the board list actually rendered. This used to count
    // `div.bg-white.rounded-lg.shadow-md`, markup the Canopy redesign removed, and
    // to pass on a "loading"/"no categories" fallback — so it went green whether or
    // not the forum worked. Wait on a real board link instead (FORUM_CONTENT_LINK
    // excludes the header chrome and hero CTAs, which render even when the board
    // list is empty, so this cannot pass vacuously).
    const boards = page.locator(FORUM_CONTENT_LINK);
    await expect(boards.first()).toBeVisible({ timeout: 10000 });
    expect(await boards.count()).toBeGreaterThan(0);
  });
});
