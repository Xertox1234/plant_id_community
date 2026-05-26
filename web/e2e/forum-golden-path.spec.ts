import { test, expect } from '@playwright/test';

// Assumes a seeded forum with >=1 category. Unauthenticated browse path only;
// reply/react/upload are covered by manual verification (see todo 094, Task 10).

test('forum public golden path: browse → open category → open topic', async ({ page }) => {
  await page.goto('/forum');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

  // Open the first category, then the first thread.
  await page.locator('a[href^="/forum/"]').first().click();
  await expect(page).toHaveURL(/\/forum\/\d+-/); // id-anchored category URL

  const firstThread = page.locator('a[href*="/forum/"]').filter({ hasText: /.+/ }).first();
  await firstThread.click();
  await expect(page).toHaveURL(/\/forum\/\d+-.+\/\d+-/); // id-anchored thread URL

  // Posts render.
  await expect(page.locator('article, [data-testid="post-card"]').first()).toBeVisible();
});
