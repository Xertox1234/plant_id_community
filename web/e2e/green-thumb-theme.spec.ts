// web/e2e/green-thumb-theme.spec.ts
import { test, expect, type Page } from '@playwright/test';

// Set theme data-attributes on <html> exactly as ThemeContext will (Task 3).
async function setTheme(page: Page, attrs: { mode?: string; density?: string }) {
  await page.evaluate((a) => {
    const el = document.documentElement;
    if (a.mode) el.dataset.mode = a.mode;
    else delete el.dataset.mode;
    if (a.density) el.dataset.density = a.density;
    else delete el.dataset.density;
  }, attrs);
}

test.describe('Canopy runtime tokens', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/debug/theme');
  });

  test('default (dark) surface resolves to pine', async ({ page }) => {
    await setTheme(page, {});
    await expect(page.getByTestId('probe-surface')).toHaveCSS(
      'background-color',
      'rgb(11, 43, 38)'
    );
  });

  test('light mode resolves to mint cream', async ({ page }) => {
    await setTheme(page, { mode: 'light' });
    await expect(page.getByTestId('probe-surface')).toHaveCSS(
      'background-color',
      'rgb(218, 241, 222)'
    );
  });

  test('density changes resolved padding (discriminating wiring)', async ({ page }) => {
    await setTheme(page, { density: 'compact' });
    await expect(page.getByTestId('probe-pad')).toHaveCSS('padding-left', '12px');
    await setTheme(page, { density: 'comfortable' });
    await expect(page.getByTestId('probe-pad')).toHaveCSS('padding-left', '18px');
  });

  test('alpha modifier resolves on a themed token', async ({ page }) => {
    await setTheme(page, {});
    const bg = await page
      .getByTestId('probe-alpha')
      .evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(bg).not.toBe('rgba(0, 0, 0, 0)'); // modifier ignored → transparent
    expect(bg).not.toBe('rgb(231, 183, 95)'); // modifier dropped → solid pollen #E7B75F
  });

  test('display headings use Bricolage Grotesque', async ({ page }) => {
    const family = await page
      .getByTestId('probe-display')
      .evaluate((el) => getComputedStyle(el).fontFamily);
    expect(family).toContain('Bricolage Grotesque');
  });

  test('light mode darkens accent tokens for text contrast', async ({ page }) => {
    await setTheme(page, { mode: 'light' });
    await expect(page.getByTestId('probe-leaf')).toHaveCSS('color', 'rgb(60, 107, 80)');
    await expect(page.getByTestId('probe-sky')).toHaveCSS('color', 'rgb(107, 79, 160)');
    await expect(page.getByTestId('probe-error')).toHaveCSS('color', 'rgb(166, 60, 42)');
  });
});
