// web/e2e/green-thumb-theme.spec.ts
import { test, expect, type Page } from '@playwright/test';

// Set theme data-attributes on <html> exactly as ThemeContext will (Task 3).
async function setTheme(page: Page, attrs: { palette?: string; mode?: string; density?: string }) {
  await page.evaluate((a) => {
    const el = document.documentElement;
    if (a.palette) el.dataset.palette = a.palette;
    else delete el.dataset.palette;
    if (a.mode) el.dataset.mode = a.mode;
    else delete el.dataset.mode;
    if (a.density) el.dataset.density = a.density;
    else delete el.dataset.density;
  }, attrs);
}

test.describe('Green Thumb runtime tokens', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/debug/theme');
  });

  test('default (loam light) surface resolves', async ({ page }) => {
    await setTheme(page, {});
    await expect(page.getByTestId('probe-surface')).toHaveCSS(
      'background-color',
      'rgb(246, 240, 226)'
    );
  });

  test('palette switch changes resolved color', async ({ page }) => {
    await setTheme(page, { palette: 'forest' });
    await expect(page.getByTestId('probe-surface')).toHaveCSS(
      'background-color',
      'rgb(15, 26, 18)'
    );
    await setTheme(page, { palette: 'loam', mode: 'dark' });
    await expect(page.getByTestId('probe-surface')).toHaveCSS(
      'background-color',
      'rgb(18, 16, 10)'
    );
  });

  test('forest+dark stays forest (cascade-bug guard)', async ({ page }) => {
    await setTheme(page, { palette: 'forest', mode: 'dark' });
    // MUST be forest #0F1A12, NOT loam-dark #12100A
    await expect(page.getByTestId('probe-surface')).toHaveCSS(
      'background-color',
      'rgb(15, 26, 18)'
    );
  });

  test('density changes resolved padding (discriminating wiring)', async ({ page }) => {
    await setTheme(page, { density: 'compact' });
    await expect(page.getByTestId('probe-pad')).toHaveCSS('padding-left', '12px'); // ≠ cozy 16, ≠ comfortable 18
    await setTheme(page, { density: 'comfortable' });
    await expect(page.getByTestId('probe-pad')).toHaveCSS('padding-left', '18px');
  });

  test('alpha modifier resolves on a themed token (not transparent, not solid)', async ({
    page,
  }) => {
    await setTheme(page, {});
    const bg = await page
      .getByTestId('probe-alpha')
      .evaluate((el) => getComputedStyle(el).backgroundColor);
    // bg-clay/10 must compile to a partial color-mix of var(--gt-clay):
    expect(bg).not.toBe('rgba(0, 0, 0, 0)'); // modifier ignored → fully transparent
    expect(bg).not.toBe('rgb(201, 84, 42)'); // modifier dropped → solid clay #C9542A
  });

  test('display headings use Bricolage Grotesque', async ({ page }) => {
    const family = await page
      .getByTestId('probe-display')
      .evaluate((el) => getComputedStyle(el).fontFamily);
    expect(family).toContain('Bricolage Grotesque');
  });
});
