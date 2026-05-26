import { test, expect } from '@playwright/test';

// Checks that the forum pages have no horizontal overflow at key breakpoints.
// Requires a running backend with at least one forum category seeded.

const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 800 },
];

function noHorizontalOverflow(page: import('@playwright/test').Page) {
  return page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth
  );
}

for (const vp of VIEWPORTS) {
  test(`forum index — no horizontal overflow at ${vp.name} (${vp.width}px)`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto('/forum');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    expect(await noHorizontalOverflow(page)).toBe(true);
  });

  test(`forum category list — no horizontal overflow at ${vp.name} (${vp.width}px)`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto('/forum');

    const categoryLink = page.locator('a[href^="/forum/"]').first();
    await categoryLink.click();
    await expect(page).toHaveURL(/\/forum\/\d+-/);
    expect(await noHorizontalOverflow(page)).toBe(true);
  });

  test(`thread detail — no horizontal overflow at ${vp.name} (${vp.width}px)`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto('/forum');

    await page.locator('a[href^="/forum/"]').first().click();
    await expect(page).toHaveURL(/\/forum\/\d+-/);

    const threadLink = page.locator('a[href*="/forum/"]').filter({ hasText: /.+/ }).first();
    await threadLink.click();
    await expect(page).toHaveURL(/\/forum\/\d+-.+\/\d+-/);
    expect(await noHorizontalOverflow(page)).toBe(true);
  });
}

test('forum index — sort select meets 44px tap target on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/forum');

  // Navigate into a category to see the sort select.
  await page.locator('a[href^="/forum/"]').first().click();
  await expect(page).toHaveURL(/\/forum\/\d+-/);

  const select = page.locator('select');
  const box = await select.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.height).toBeGreaterThanOrEqual(44);
});
