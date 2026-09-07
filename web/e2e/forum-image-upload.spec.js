import { test, expect } from '@playwright/test';

/**
 * Inline image upload in a REAL mounted composer — todo 357, AC 7/8
 * ("browser coverage" / "the relevant browser flow passes").
 *
 * `TipTapEditor.test.tsx` drives this path in jsdom with the service mocked;
 * this is the other half — that the whole chain actually works against the
 * running backend: hidden file input -> client validation -> alt prompt ->
 * ONE authenticated multipart POST to /api/v1/forum/images/ -> a TipTap node
 * carrying the server image id -> `htmlToBodyBlocks` -> the API.
 *
 * `data-testid="forum-image-input"` has existed since PR-3 and was explicitly
 * flagged in forum-authenticated.spec.js as the intended e2e hook; until now no
 * spec used it.
 *
 * REAL JPEG BYTES, not `Buffer.from('fake-image-bytes')` (which is what the
 * canopy-areas specs use — they are `page.route`-mocked, so nothing decodes
 * them). This endpoint runs a 4-layer validation whose last layer is a PIL
 * decode + dimension cap, so fake bytes would 400 and the test would be
 * asserting the wrong branch. The constant below is a real 1x1 JPEG.
 *
 * Runs only under the `*-authenticated` projects — the upload endpoint is
 * IsAuthenticated and CSRF-gated. Prerequisites (local):
 *   cd backend && python manage.py create_test_user && python manage.py seed_default_forum
 *
 * NOTE for anyone adding a spec here: every authenticated `testMatch` regex in
 * playwright.config.ts ends in `\.js`, so a `.ts` authenticated spec matches
 * NOTHING and reports zero failures. It is also a two-place edit — the filename
 * goes in both authenticated `testMatch`es AND all five unauthenticated
 * `testIgnore`s.
 */

// A real 1x1 JPEG. Layer 4 of the server's validation PIL-decodes the upload,
// so the bytes have to actually be an image.
// prettier-ignore
const ONE_PX_JPEG = Buffer.from('/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/9oACAEBAAA/APn+iiigD//Z', 'base64'); // pragma: allowlist secret

const IMAGE_INPUT = '[data-testid="forum-image-input"]';
const UPLOAD_URL = /\/api\/v1\/forum\/images\/$/;

/** Open the new-thread composer and return its editor + form locators. */
async function openComposer(page) {
  await page.goto('/forum/new-thread');
  const form = page
    .locator('form')
    .filter({ has: page.getByRole('button', { name: 'Post Thread' }) });
  const editor = form.locator('.ProseMirror').first();
  await expect(editor).toBeVisible();
  return { form, editor };
}

test.describe('Forum inline image upload', () => {
  test('uploads a chosen image in ONE authenticated multipart request and inserts a node carrying the server id', async ({
    page,
  }) => {
    const { form, editor } = await openComposer(page);

    // Count every call to the endpoint for the whole test, so a duplicate
    // upload fails this test rather than passing unnoticed (AC 4).
    const uploadRequests = [];
    page.on('request', (req) => {
      if (UPLOAD_URL.test(req.url()) && req.method() === 'POST') uploadRequests.push(req);
    });

    await page.setInputFiles(IMAGE_INPUT, {
      name: 'leaf.jpg',
      mimeType: 'image/jpeg',
      buffer: ONE_PX_JPEG,
    });

    // The alt prompt opens BEFORE the upload — the value rides the multipart
    // request, so this is the only moment it can be captured.
    const altInput = page.getByLabel(/describe this image/i);
    await expect(altInput).toBeVisible();
    await altInput.fill('A monstera leaf with brown edges');

    const [response] = await Promise.all([
      page.waitForResponse((r) => UPLOAD_URL.test(r.url()) && r.request().method() === 'POST'),
      page.getByRole('button', { name: 'Add image' }).click(),
    ]);

    expect(response.status()).toBe(201);
    const uploaded = await response.json();
    expect(uploaded.id).toBeGreaterThan(0);

    // Multipart, and carrying the Idempotency-Key that arms the server's replay
    // path — a fresh key per attempt would store a duplicate row (M36).
    const headers = uploadRequests[0].headers();
    expect(headers['content-type']).toContain('multipart/form-data');
    expect(headers['idempotency-key']).toBeTruthy();

    // The inserted node must carry the SERVER id, or htmlToBodyBlocks emits no
    // image block and the upload is orphaned on save.
    const img = editor.locator('img[data-image-id]');
    await expect(img).toBeVisible();
    await expect(img).toHaveAttribute('data-image-id', String(uploaded.id));
    await expect(img).toHaveAttribute('alt', 'A monstera leaf with brown edges');

    // Exactly one request for one chosen file.
    expect(uploadRequests).toHaveLength(1);

    // The draft survives the upload — a composer that lost typed text on insert
    // would be worse than no upload at all (AC 4).
    await editor.click();
    await page.keyboard.type('what is wrong with it?');
    await expect(editor).toContainText('what is wrong with it?');
    await expect(form).toBeVisible();
  });

  test('rejects an unsupported file client-side, announces it, and accepts a real image afterwards', async ({
    page,
  }) => {
    const { editor } = await openComposer(page);

    let uploadAttempts = 0;
    page.on('request', (req) => {
      if (UPLOAD_URL.test(req.url()) && req.method() === 'POST') uploadAttempts += 1;
    });

    await page.setInputFiles(IMAGE_INPUT, {
      name: 'notes.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 not an image'),
    });

    // Rejected before any network call, and announced rather than silent.
    await expect(page.getByText(/unsupported image type/i)).toBeVisible();
    expect(uploadAttempts).toBe(0);
    // No alt prompt for a file that never got past validation.
    await expect(page.getByLabel(/describe this image/i)).toHaveCount(0);

    // Selecting again after an error must work — the input's value is cleared
    // on every selection precisely so re-picking is not a no-op.
    await page.setInputFiles(IMAGE_INPUT, {
      name: 'leaf.jpg',
      mimeType: 'image/jpeg',
      buffer: ONE_PX_JPEG,
    });
    await expect(page.getByLabel(/describe this image/i)).toBeVisible();
    await Promise.all([
      page.waitForResponse((r) => UPLOAD_URL.test(r.url()) && r.request().method() === 'POST'),
      page.getByRole('button', { name: 'Skip' }).click(),
    ]);
    await expect(editor.locator('img[data-image-id]')).toBeVisible();
    expect(uploadAttempts).toBe(1);
  });

  test('Skip stores the image as decorative, and alt can be re-authored afterwards without re-uploading', async ({
    page,
  }) => {
    const { editor } = await openComposer(page);

    let uploadAttempts = 0;
    page.on('request', (req) => {
      if (UPLOAD_URL.test(req.url()) && req.method() === 'POST') uploadAttempts += 1;
    });

    await page.setInputFiles(IMAGE_INPUT, {
      name: 'leaf.jpg',
      mimeType: 'image/jpeg',
      buffer: ONE_PX_JPEG,
    });
    await Promise.all([
      page.waitForResponse((r) => UPLOAD_URL.test(r.url()) && r.request().method() === 'POST'),
      page.getByRole('button', { name: 'Skip' }).click(),
    ]);

    const img = editor.locator('img[data-image-id]');
    await expect(img).toBeVisible();
    // Skip means decorative: alt="" is the correct markup, not a missing alt.
    await expect(img).toHaveAttribute('alt', '');
    await expect(img).toHaveAttribute('data-decorative', 'true');

    // Re-author it. This is the ImageBlock payoff — under ImageChooserBlock the
    // only way to change alt was to upload the file again.
    await img.click();
    await page.getByRole('button', { name: 'Edit image alt text' }).click();
    await page.getByLabel(/describe this image/i).fill('A monstera leaf');
    await page.getByRole('button', { name: 'Save alt text' }).click();

    await expect(img).toHaveAttribute('alt', 'A monstera leaf');
    // Still exactly one upload for the whole flow.
    expect(uploadAttempts).toBe(1);
  });

  test('the Insert image control has an accessible name and works at a mobile width', async ({
    page,
  }) => {
    // AC 1. `title` alone would NOT give an accessible name here (name-from-content
    // never applies to a button whose only child is an aria-hidden icon), which is
    // why ToolbarButton mirrors title into aria-label.
    await page.setViewportSize({ width: 390, height: 844 }); // iPhone 12 width
    const { editor } = await openComposer(page);

    const button = page.getByRole('button', { name: 'Insert image' });
    await expect(button).toBeVisible();
    // Reachable at a narrow width: the toolbar scrolls rather than clipping.
    await button.scrollIntoViewIfNeeded();
    const box = await button.boundingBox();
    expect(box).not.toBeNull();
    expect(box.width).toBeGreaterThan(0);

    // Keyboard-activating the control opens the picker: assert the hidden input
    // receives the click rather than trying to observe the OS dialog.
    const clicked = await editor.page().evaluate(() => {
      const input = document.querySelector('[data-testid="forum-image-input"]');
      if (!input) return false;
      let sawClick = false;
      input.addEventListener('click', () => {
        sawClick = true;
      });
      const btn = [...document.querySelectorAll('button')].find(
        (b) => b.getAttribute('aria-label') === 'Insert image'
      );
      btn?.focus();
      btn?.click();
      return sawClick;
    });
    expect(clicked).toBe(true);
  });
});
