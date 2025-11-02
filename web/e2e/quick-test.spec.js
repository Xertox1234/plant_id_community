import { test, expect } from '@playwright/test';

/**
 * Quick E2E Test - Verify basic functionality
 *
 * This test checks that both servers are running and the blog loads
 */

test('Blog page loads successfully', async ({ page }) => {
  // Navigate to blog
  await page.goto('http://localhost:5174/blog', { waitUntil: 'networkidle', timeout: 30000 });

  // Check that we're on the blog page
  expect(page.url()).toContain('/blog');

  // Check for blog posts (BlogCard is a Link with specific classes) or loading/no posts state
  const blogCards = await page.locator('a.group.block.bg-white').count();
  const loadingSpinner = await page.locator('text=/loading/i').count();
  const noPostsMessage = await page.locator('text=/no.*posts/i').count();

  const hasContent = blogCards > 0 || loadingSpinner > 0 || noPostsMessage > 0;

  expect(hasContent).toBeTruthy();

  console.log('✅ Blog page loaded successfully!');
});

test('API is accessible from frontend', async ({ page }) => {
  await page.goto('http://localhost:5174');

  // Test API call from browser context
  const apiWorks = await page.evaluate(async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v2/blog-posts/?limit=1');
      return res.ok;
    } catch (error) {
      console.error('API test failed:', error);
      return false;
    }
  });

  expect(apiWorks).toBeTruthy();
  console.log('✅ API is accessible from frontend!');
});
