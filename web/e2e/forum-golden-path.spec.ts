import { test, expect } from '@playwright/test';
import { FORUM_CONTENT_LINK, forumThreadLinkIn } from './config.js';

// Assumes a seeded forum with >=1 category. Unauthenticated browse path only;
// reply/react/upload are covered by manual verification (see todo 094, Task 10).

test('forum public golden path: browse → open category → open topic', async ({ page }) => {
  await page.goto('/forum');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

  // Open the first category, then the first thread. FORUM_CONTENT_LINK skips the
  // AppShell header's /forum/* chrome and the hero CTAs (docs/rules/testing.md).
  await page.locator(FORUM_CONTENT_LINK).first().click();
  await expect(page).toHaveURL(/\/forum\/\d+-/); // id-anchored category URL

  const boardPath = new URL(page.url()).pathname;
  const firstThread = page.locator(forumThreadLinkIn(boardPath)).first();
  await firstThread.click();
  await expect(page).toHaveURL(/\/forum\/\d+-.+\/\d+-/); // id-anchored thread URL

  // Posts render.
  await expect(page.locator('article, [data-testid="post-card"]').first()).toBeVisible();
});
