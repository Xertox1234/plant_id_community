import { test, expect } from '@playwright/test';

/**
 * Authenticated Canopy PR 4 smoke coverage — Garden and Diagnose, both behind
 * ProtectedLayout (App.tsx route audit, spec §1). Runs as the seeded
 * e2e_test_user (auth.setup.js → storageState, same as forum-authenticated.spec.js).
 * Diagnose's network calls are mocked; no live disease-service spend (spec §6.2).
 *
 * Garden fixture data is seeded via direct API calls here, not through the
 * Identify UI — see the beforeAll below. Left-behind data across runs is an
 * accepted tradeoff, same as forum-authenticated.spec.js — the nickname is
 * timestamped (mirrors forum-authenticated's `stamp` pattern) so repeated
 * local runs don't collide, and the Garden assertions are scoped to the one
 * matching card so an unstamped field (the 90% confidence pill, shared by
 * every leftover fixture row) can't turn into a strict-mode multi-match.
 *
 * One deviation from a literal reading of the frontend services this spec
 * exercises, confirmed against real source before writing this file:
 *
 * 1. Both POSTs below carry an explicit `X-CSRFToken` header. Cookie-based
 *    auth enforces CSRF on mutations (CookieJWTAuthentication.enforce_csrf,
 *    apps/users/authentication.py) — the app's own fetch layer adds this
 *    header automatically (utils/csrf.ts), but Playwright's bare `request`
 *    fixture does not, so the token is read out of the inherited storageState
 *    cookie jar and attached by hand.
 */

test.describe('Garden', () => {
  let fixtureNickname;

  test.beforeAll(async ({ request }) => {
    const state = await request.storageState();
    const csrfToken = state.cookies.find((c) => c.name === 'csrftoken')?.value;
    const csrfHeaders = csrfToken ? { 'X-CSRFToken': csrfToken } : {};

    // Ensure a UserPlantCollection exists (plantIdService.saveToCollection's
    // real prerequisite) before seeding a plant into it.
    const collections = await request.get('/api/v1/auth/me/collections/');
    const existing = await collections.json();
    let collectionId = existing[0]?.id;

    if (!collectionId) {
      const created = await request.post('/api/v1/auth/me/collections/', {
        headers: csrfHeaders,
        data: { name: 'My Plants' },
      });
      expect(created.ok()).toBeTruthy();
      const collection = await created.json();
      collectionId = collection.id;
    }

    fixtureNickname = `E2E fixture rose ${Date.now()}`;

    const plantCreated = await request.post('/api/v1/plant-identification/plants/', {
      headers: csrfHeaders,
      data: {
        collection: collectionId,
        nickname: fixtureNickname,
        notes: 'Seeded by canopy-areas-authenticated.spec.js',
        care_instructions_json: {
          confidence: 0.9,
          common_names: ['Fixture Rose'],
          watering: 'Water weekly',
          source: 'plant_id',
        },
      },
    });
    expect(plantCreated.ok()).toBeTruthy();
  });

  test('populated grid renders a saved plant', async ({ page }) => {
    await page.goto('/my-plants');

    // Scoped to the one card matching this run's stamped nickname — the 90%
    // confidence pill alone isn't unique once earlier runs' fixtures pile up.
    const card = page.locator('.canopy-card').filter({ hasText: fixtureNickname });
    await expect(card).toBeVisible();
    await expect(card.getByText('90%')).toBeVisible();
  });
});

test.describe('Diagnose', () => {
  test('form submit → mocked results render', async ({ page }) => {
    await page.route('**/api/v1/plant-identification/disease-requests/', async (route) => {
      if (route.request().method() !== 'POST') return route.continue();
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ request_id: 'e2e-r1', status: 'diagnosed' }),
      });
    });
    await page.route(
      '**/api/v1/plant-identification/disease-requests/e2e-r1/results/',
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            request_id: 'e2e-r1',
            status: 'diagnosed',
            results: [
              {
                id: 1,
                uuid: 'u1',
                request_id: 'e2e-r1',
                suggested_disease_name: 'Black Spot',
                suggested_disease_type: 'fungal',
                confidence_score: 0.88,
                confidence_percentage: 88,
                diagnosis_source: 'api_plant_health',
                severity_assessment: 'moderate',
                symptoms_identified: 'black spots',
                recommended_treatments: 'fungicide',
                immediate_actions: 'remove affected leaves',
                notes: '',
                is_primary: true,
                display_name: 'Black Spot',
              },
            ],
          }),
        });
      }
    );

    await page.goto('/diagnose');

    await page.setInputFiles('input[type="file"]', {
      name: 'leaf.jpg',
      mimeType: 'image/jpeg',
      buffer: Buffer.from('fake-image-bytes'),
    });
    await page.getByLabel(/symptoms/i).fill('black spots on leaves');
    await page.getByRole('button', { name: /^diagnose$/i }).click();

    await expect(page.getByText('Black Spot')).toBeVisible();
    await expect(page.getByText('88%')).toBeVisible();
  });
});
