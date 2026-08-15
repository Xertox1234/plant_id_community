import { test, expect } from '@playwright/test';

/**
 * Authenticated forum WRITE-lifecycle E2E — todo 261 / M34.
 *
 * Runs against a REAL backend (playwright.config webServer boots Django + Vite)
 * as the seeded `e2e_test_user` (auth.setup.js → storageState). The user is
 * untrusted (trust_level 0), but clean prose auto-approves synchronously through
 * the heuristic spam workflow and publishes immediately
 * (wagtail_forum/workflow.py → SpamCheckTask.start), so the created topic and
 * reply are live right away — no moderation wait. All bodies below are plain
 * prose with no links, so the heuristic never flags them.
 *
 * Local-only: Playwright is excluded from CI (web/CLAUDE.md).
 *
 * Prerequisites (local):
 *   cd backend && python manage.py create_test_user && python manage.py seed_default_forum
 *
 * Selectors mirror the current id-anchored forum UI (no legacy /forum/category
 * or /forum/thread routes). The only forum data-testid is the image input, so
 * this targets stable roles/labels/titles/ids instead.
 */

// TipTap is a ProseMirror contenteditable; real keystrokes (not fill()) are
// what update its React state and enable the disabled-until-non-blank submit.
async function typeInto(editor, page, text) {
  await editor.click();
  await page.keyboard.type(text);
}

async function replaceInto(editor, page, text) {
  await editor.click();
  await page.keyboard.press('ControlOrMeta+A');
  await page.keyboard.press('Backspace');
  await page.keyboard.type(text);
}

test.describe('Authenticated forum write lifecycle', () => {
  test('create thread → reply → edit → react → delete', async ({ page }) => {
    const stamp = `${Date.now()}`;
    const threadTitle = `E2E lifecycle thread ${stamp}`;
    const openingBody = `E2E opening post body ${stamp}`;
    const replyBody = `E2E reply body ${stamp}`;
    const editedReply = `E2E edited reply body ${stamp}`;

    // 1. Forum home → open the first board (id-anchored URL). A board CategoryCard
    // link wraps an <h3>; the header search / new-thread links do not — filter on
    // that so we don't grab `/forum/search`.
    await page.goto('/forum');
    const boardLink = page
      .locator('a[href^="/forum/"]')
      .filter({ has: page.locator('h3') })
      .first();
    await expect(
      boardLink,
      'no forum board found — run: manage.py seed_default_forum'
    ).toBeVisible();
    await boardLink.click();
    await expect(page).toHaveURL(/\/forum\/\d+-/);

    // 2. Create a new thread. Scoped to #main-content — the topbar also has a
    // bare "New post" link (AppShell), which would otherwise win .first().
    await page.locator('#main-content a[href^="/forum/new-thread"]').first().click();
    await expect(page).toHaveURL(/\/forum\/new-thread/);
    await page.locator('#thread-title').fill(threadTitle);
    await typeInto(page.locator('.ProseMirror').first(), page, openingBody);
    await page.getByRole('button', { name: 'Post Thread' }).click();

    // Clean prose auto-publishes → redirect to the new topic (board/id-slug/id-slug).
    await expect(page).toHaveURL(/\/forum\/\d+-[^/]+\/\d+-/, { timeout: 15000 });
    await expect(page.getByRole('heading', { name: threadTitle })).toBeVisible();
    await expect(page.getByText(openingBody)).toBeVisible();

    // 3. Reply to the thread.
    const replyForm = page
      .locator('form')
      .filter({ has: page.getByRole('button', { name: 'Post Reply' }) });
    await typeInto(replyForm.locator('.ProseMirror'), page, replyBody);
    await replyForm.getByRole('button', { name: 'Post Reply' }).click();
    await expect(page.getByText(replyBody)).toBeVisible({ timeout: 15000 });

    // The reply is its own post container (#post-<id>); scope edits to it.
    const replyPost = page.locator('[id^="post-"]').filter({ hasText: replyBody });
    await expect(replyPost).toHaveCount(1);

    // 4. Edit the reply (owner can_edit → ✏️ control).
    await replyPost.getByTitle('Edit post').click();
    const editForm = page
      .locator('form')
      .filter({ has: page.getByRole('button', { name: 'Save' }) });
    await replaceInto(editForm.locator('.ProseMirror'), page, editedReply);
    await editForm.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByText(editedReply)).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(replyBody)).toHaveCount(0);

    const editedPost = page.locator('[id^="post-"]').filter({ hasText: editedReply });

    // 5. React: a zero-reaction post needs the picker opened first.
    await editedPost.locator('button[aria-label="Add reaction"]').click();
    await editedPost.locator('button[aria-label="React like"]').first().click();
    await expect(
      editedPost.locator('button[aria-label="React like"][aria-pressed="true"]')
    ).toBeVisible();

    // 6. Delete the reply via the in-page confirm modal (not window.confirm).
    // (Only the reply is removed; the created topic + opening post persist —
    // an accepted local-dev tradeoff, each run's thread is uniquely timestamped.)
    await editedPost.getByTitle('Delete post').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Delete' }).click();
    await expect(page.getByText(editedReply)).toHaveCount(0, { timeout: 15000 });
  });
});
