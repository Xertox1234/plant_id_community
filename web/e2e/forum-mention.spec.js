import { test, expect } from '@playwright/test';

/**
 * @mention suggestion dropdown in a REAL mounted composer — todo 336
 * (audit 2026-09-04 L5). `forumMentionNode.test.ts` drives the dropdown's
 * `render()` lifecycle (onStart/onUpdate/onKeyDown/onExit) with hand-built
 * props; this is the other half of the contract — that ProseMirror's
 * suggestion plugin actually calls those hooks at the right moment against a
 * live `EditorView`, with a real `clientRect`, and that Escape / an in-app
 * route change tear the dropdown down. It drives the NEW-THREAD composer: the same
 * `TipTapEditor` with the same `ForumMention` extension as the reply
 * composer, reachable without a seeded topic (a fresh local forum has none)
 * and without posting anything — nothing is ever submitted.
 *
 * Runs only under the `*-authenticated` projects (the reply composer and the
 * user-search endpoint both need a session; see web/CLAUDE.md on the login
 * rate limit). Prerequisites (local):
 *   cd backend && python manage.py create_test_user && python manage.py seed_default_forum
 *
 * Selectors: the dropdown is appended to <body> (outside the React tree)
 * with data-testid="mention-suggestions" (forumMentionNode.ts) and holds one
 * <button> per suggestion labelled `@<username>`; positioning is manual
 * (`position: fixed` from the suggestion's clientRect).
 * The seeded e2e user mentions itself — `users/search/` is a username
 * istartswith match and does not exclude the caller.
 */

const DROPDOWN = '[data-testid="mention-suggestions"]'; // DROPDOWN_TESTID in forumMentionNode.ts
const QUERY = '@e2e_test_u'; // istartswith → e2e_test_user, deterministic
const MENTION = '@e2e_test_user';
// The committed node (TipTap Mention renderHTML: span[data-type="mention"]).
const MENTION_NODE = 'span[data-type="mention"]';

test.describe('Forum @mention dropdown in the real composer', () => {
  test('typing @ mounts the dropdown; Enter commits the highlighted item; Escape and an in-app route change remove it', async ({
    page,
  }) => {
    await page.goto('/forum/new-thread');
    const composer = page
      .locator('form')
      .filter({ has: page.getByRole('button', { name: 'Post Thread' }) });
    const editor = composer.locator('.ProseMirror').first();
    await expect(editor).toBeVisible();
    await editor.click();

    // 1. onStart/onUpdate: real keystrokes → suggestion plugin → dropdown in <body>
    //    (after the 300 ms search debounce + the users/search request).
    await page.keyboard.type(QUERY);
    const dropdown = page.locator(DROPDOWN);
    await expect(dropdown).toBeVisible();
    const suggestion = dropdown.getByRole('button', { name: MENTION });
    await expect(suggestion).toBeVisible();
    // Positioned from a live clientRect: position() only sets `fixed` +
    // top/left when the plugin handed it a rect — a null rect would leave the
    // div in static flow (still at a non-zero y, so a bare box check proves
    // nothing).
    await expect(dropdown).toHaveCSS('position', 'fixed');
    const box = await dropdown.boundingBox();
    expect(box).not.toBeNull();
    expect(box.x + box.y).toBeGreaterThan(0);

    // 2. onKeyDown: Enter commits the highlighted item → exactly one mention
    //    NODE in the doc (a substring check would also pass on plain text),
    //    dropdown gone (onExit). ArrowDown is pressed for the real key path,
    //    but with the single seeded user it is a no-op (index wraps to 0) —
    //    item-to-item navigation is pinned by forumMentionNode.test.ts.
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    const mentionNodes = editor.locator(MENTION_NODE);
    await expect(mentionNodes).toHaveCount(1);
    await expect(mentionNodes.first()).toHaveText(MENTION);
    await expect(page.locator(DROPDOWN)).toHaveCount(0);

    // 3. Escape: @tiptap/suggestion calls onExit itself — no dropdown may
    //    linger, and NOTHING was committed: still exactly one mention node
    //    (the query text is a prefix of the committed label, so only the
    //    node count can tell "left as plain text" from "committed again").
    await page.keyboard.type(` ${QUERY}`);
    await expect(page.locator(DROPDOWN)).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator(DROPDOWN)).toHaveCount(0);
    await expect(editor.locator(MENTION_NODE)).toHaveCount(1);

    // 4. Editor teardown mid-suggestion leaves no orphan. An IN-APP route
    //    change (the breadcrumb <Link>, React Router unmounts the editor while
    //    document.body survives) — a page.goto() would wipe <body> and prove
    //    nothing.
    await page.keyboard.type(` ${QUERY}`);
    await expect(page.locator(DROPDOWN)).toBeVisible();
    await page.locator('#main-content a[href="/forum"]').first().click();
    await expect(page).toHaveURL(/\/forum\/?$/);
    await expect(page.locator(DROPDOWN)).toHaveCount(0);
  });
});
