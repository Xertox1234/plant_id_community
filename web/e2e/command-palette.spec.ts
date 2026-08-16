import { test, expect } from '@playwright/test';

test('command palette opens with the keyboard and closes with Escape', async ({ page }) => {
  await page.goto('/');
  // The Cmd/Ctrl+K listener is registered in an AppShell effect, so the shortcut
  // is a no-op until React has mounted — and page.goto resolves on 'load', before
  // that. Waiting on a shell element makes the keypress deterministic: without it
  // headless chromium fails 3/3 (headed passes only incidentally, on render latency).
  await expect(page.getByRole('button', { name: /Search plants, posts, people/ })).toBeVisible();
  await page.keyboard.press('ControlOrMeta+KeyK');
  const dialog = page.getByRole('dialog', { name: 'Search' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Identify a plant')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
});

test('topbar search pill opens the palette', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /Search plants, posts, people/ }).click();
  await expect(page.getByRole('dialog', { name: 'Search' })).toBeVisible();
});
