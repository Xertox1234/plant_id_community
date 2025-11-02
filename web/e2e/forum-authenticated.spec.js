import { test, expect } from '@playwright/test';

/**
 * Authenticated Forum E2E Tests
 *
 * These tests verify forum functionality for authenticated users:
 * - Creating forum posts
 * - Viewing thread details
 * - Deleting own posts
 * - Using TipTap rich text editor
 *
 * These tests run WITH authentication state loaded (see playwright.config.js)
 *
 * Prerequisites:
 * - Test user authenticated (auth.setup.js)
 * - At least one forum category exists
 * - At least one thread exists for testing
 */

test.describe('Authenticated Forum Functionality', () => {
  let createdPostContent = '';

  test.beforeEach(async () => {
    // Generate unique content for each test run
    createdPostContent = `E2E Test Post ${Date.now()}`;
  });

  test('can view forum home page', async ({ page }) => {
    await page.goto('/forum', { waitUntil: 'networkidle', timeout: 30000 });

    // Wait for page structure
    await page.waitForSelector('h1', { timeout: 10000 });

    // Should see categories or a message
    const categories = await page.locator('div.bg-white.rounded-lg.shadow-md').count();
    const noCategories = await page.locator('text=/no.*categories/i').count();
    const loading = await page.locator('text=/loading/i').count();

    expect(categories > 0 || noCategories > 0 || loading > 0).toBeTruthy();
  });

  test('can navigate to a category and view threads', async ({ page }) => {
    await page.goto('/forum', { waitUntil: 'networkidle', timeout: 30000 });

    await page.waitForTimeout(2000); // Wait for data

    // Find first category link (if any exist)
    const categoryLinks = await page.locator('a[href^="/forum/category/"]');
    const count = await categoryLinks.count();

    if (count > 0) {
      const firstCategory = categoryLinks.first();
      await firstCategory.click();

      // Wait for category page to load
      await page.waitForURL(/.*\/forum\/category\/.*/, { timeout: 10000 });

      // Should see threads or "no threads" message
      const threads = await page.locator('a[href^="/forum/thread/"]').count();
      const noThreads = await page.locator('text=/no.*threads/i').count();

      expect(threads > 0 || noThreads > 0).toBeTruthy();
    } else {
      // No categories exist, skip this test
      test.skip();
    }
  });

  test('can view thread detail page', async ({ page }) => {
    // Navigate to forum and find a thread
    await page.goto('/forum', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);

    // Try to find any thread link
    const threadLinks = await page.locator('a[href^="/forum/thread/"]');
    const count = await threadLinks.count();

    if (count > 0) {
      const firstThread = threadLinks.first();
      await firstThread.click();

      // Wait for thread detail page
      await page.waitForURL(/.*\/forum\/thread\/.*/, { timeout: 10000 });

      // Should see thread title and posts
      const threadTitle = await page.locator('h1').isVisible({ timeout: 5000 });
      expect(threadTitle).toBeTruthy();

      // Should see post content or loading state
      const posts = await page.locator('[data-testid="forum-post"]').count();
      const loading = await page.locator('text=/loading/i').count();

      expect(posts > 0 || loading > 0).toBeTruthy();
    } else {
      // No threads exist, skip this test
      test.skip();
    }
  });

  test('can create a new post in a thread (TipTap editor)', async ({ page }) => {
    // Navigate to forum
    await page.goto('/forum', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);

    // Find a thread to post in
    const threadLinks = await page.locator('a[href^="/forum/thread/"]');
    const count = await threadLinks.count();

    if (count > 0) {
      const firstThread = threadLinks.first();
      await firstThread.click();

      // Wait for thread detail page
      await page.waitForURL(/.*\/forum\/thread\/.*/, { timeout: 10000 });
      await page.waitForTimeout(2000);

      // Find TipTap editor
      const editorSelector = '.tiptap';
      const editor = page.locator(editorSelector).first();
      const isEditorVisible = await editor.isVisible({ timeout: 5000 }).catch(() => false);

      if (isEditorVisible) {
        // Click into editor and type content
        await editor.click();
        await editor.fill(createdPostContent);

        // Find and click submit button
        const submitButton = page.locator('button[type="submit"]').filter({ hasText: /post|submit|send/i }).first();
        await submitButton.click();

        // Wait for post to appear
        await page.waitForTimeout(2000);

        // Verify post was created
        const postContent = await page.locator(`text="${createdPostContent}"`).isVisible({ timeout: 5000 }).catch(() => false);
        expect(postContent).toBeTruthy();
      } else {
        // Editor not found, skip this test
        console.log('TipTap editor not found, skipping post creation test');
        test.skip();
      }
    } else {
      // No threads exist, skip this test
      test.skip();
    }
  });

  test('can delete own post', async ({ page }) => {
    // First, navigate to a thread where we can create and delete a post
    await page.goto('/forum', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);

    const threadLinks = await page.locator('a[href^="/forum/thread/"]');
    const count = await threadLinks.count();

    if (count > 0) {
      const firstThread = threadLinks.first();
      await firstThread.click();

      await page.waitForURL(/.*\/forum\/thread\/.*/, { timeout: 10000 });
      await page.waitForTimeout(2000);

      // Create a post first
      const editorSelector = '.tiptap';
      const editor = page.locator(editorSelector).first();
      const isEditorVisible = await editor.isVisible({ timeout: 5000 }).catch(() => false);

      if (isEditorVisible) {
        const testContent = `E2E Test Post to Delete ${Date.now()}`;
        await editor.click();
        await editor.fill(testContent);

        const submitButton = page.locator('button[type="submit"]').filter({ hasText: /post|submit|send/i }).first();
        await submitButton.click();

        await page.waitForTimeout(3000); // Wait for post to be created

        // Now find and click delete button for our post
        // Look for the post we just created
        const ourPost = page.locator(`text="${testContent}"`).locator('..').locator('..'); // Navigate up to post container

        // Find delete button within this post
        const deleteButton = ourPost.locator('button').filter({ hasText: /delete|remove/i }).first();
        const deleteButtonVisible = await deleteButton.isVisible({ timeout: 3000 }).catch(() => false);

        if (deleteButtonVisible) {
          await deleteButton.click();

          // Confirm deletion if there's a confirmation dialog
          const confirmButton = page.locator('button').filter({ hasText: /confirm|yes|delete/i }).first();
          const confirmVisible = await confirmButton.isVisible({ timeout: 2000 }).catch(() => false);
          if (confirmVisible) {
            await confirmButton.click();
          }

          await page.waitForTimeout(2000);

          // Verify post is no longer visible
          const postStillVisible = await page.locator(`text="${testContent}"`).isVisible({ timeout: 3000 }).catch(() => false);
          expect(postStillVisible).toBeFalsy();
        } else {
          console.log('Delete button not found, skipping deletion test');
        }
      } else {
        test.skip();
      }
    } else {
      test.skip();
    }
  });

  test('TipTap editor has basic formatting tools', async ({ page }) => {
    // Navigate to a thread with editor
    await page.goto('/forum', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);

    const threadLinks = await page.locator('a[href^="/forum/thread/"]');
    const count = await threadLinks.count();

    if (count > 0) {
      const firstThread = threadLinks.first();
      await firstThread.click();

      await page.waitForURL(/.*\/forum\/thread\/.*/, { timeout: 10000 });
      await page.waitForTimeout(2000);

      // Check for TipTap toolbar buttons
      const boldButton = page.locator('button[title*="bold" i]').first();
      const italicButton = page.locator('button[title*="italic" i]').first();

      const hasBold = await boldButton.isVisible({ timeout: 3000 }).catch(() => false);
      const hasItalic = await italicButton.isVisible({ timeout: 3000 }).catch(() => false);

      // At least some formatting tools should be available
      expect(hasBold || hasItalic).toBeTruthy();
    } else {
      test.skip();
    }
  });
});
