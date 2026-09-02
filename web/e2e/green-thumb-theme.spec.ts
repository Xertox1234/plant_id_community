// web/e2e/green-thumb-theme.spec.ts
import { test, expect, type Page } from '@playwright/test';

// Drive the theme through ThemeContext's own storage keys, then reload so the
// provider initialises from them.
//
// This used to write `data-mode`/`data-density` onto <html> directly, from a time
// when ThemeContext did not exist yet ("exactly as ThemeContext will"). Now that it
// does, its mount effect re-applies its own state over any direct write, so the
// attributes snapped back to the defaults (dark / cozy) before the assertion ran.
// That is why only the tests expecting the DEFAULTS passed — the light-mode and
// compact-density ones were silently asserting against an unchanged page.
//
// Keys and defaults mirror src/contexts/ThemeContext.tsx (gt-mode: dark,
// gt-density: cozy); omitting a key clears it so the provider falls back.
async function setTheme(page: Page, attrs: { mode?: string; density?: string }) {
  await page.evaluate((a) => {
    const set = (key: string, value?: string) =>
      value ? localStorage.setItem(key, value) : localStorage.removeItem(key);
    set('gt-mode', a.mode);
    set('gt-density', a.density);
  }, attrs);
  await page.reload();
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
