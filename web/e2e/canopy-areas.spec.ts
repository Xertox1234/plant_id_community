import { test, expect } from '@playwright/test';

/**
 * Public Canopy PR 4 smoke coverage — Home and Identify, both unauthenticated
 * routes (App.tsx route audit, spec §1). Identify's network calls are mocked;
 * no live Plant.id/PlantNet spend (spec §6.2).
 */

test.describe('Home', () => {
  test('renders the hero and feature-card links', async ({ page }) => {
    await page.goto('/');

    await expect(
      page.getByRole('heading', { level: 2, name: /discover the world of plants/i })
    ).toBeVisible();

    const getStarted = page.getByRole('link', { name: /get started/i });
    await expect(getStarted).toHaveAttribute('href', '/identify');

    await expect(page.getByRole('link', { name: /discussion forum/i })).toHaveAttribute(
      'href',
      '/forum'
    );
  });
});

test.describe('Identify', () => {
  test('upload → mocked result → confidence pill renders', async ({ page }) => {
    await page.route('**/api/v1/plant-identification/identify/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          plant_name: 'Swiss cheese plant',
          confidence: 0.82,
          source: 'plant_id',
          suggestions: [
            {
              plant_name: 'Swiss cheese plant',
              scientific_name: 'Monstera deliciosa',
              probability: 0.82,
              confidence: 0.82,
              source: 'plant_id',
            },
          ],
        }),
      });
    });

    await page.goto('/identify');

    await page.setInputFiles('input[type="file"]', {
      name: 'plant.jpg',
      mimeType: 'image/jpeg',
      buffer: Buffer.from('fake-image-bytes'),
    });
    await page.getByRole('button', { name: /identify plant/i }).click();

    await expect(page.getByText('Swiss cheese plant')).toBeVisible();
    await expect(page.getByText('82%')).toBeVisible();
  });
});
