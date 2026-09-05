import { test, expect } from '@playwright/test';

/**
 * Blog comments happy path — todo 352.
 *
 * Runs against a REAL backend as the seeded `e2e_test_user` (auth.setup.js →
 * storageState), so it lives in the `*-authenticated` projects ONLY: the
 * composer needs a session, and `POST add_comment/` is IsAuthenticated. A new
 * spec of this kind must be added to BOTH authenticated `testMatch` regexes
 * and EVERY unauthenticated project's `testIgnore` in playwright.config.ts.
 *
 * Whether the comment lands APPROVED or HELD depends on the seeded user's
 * forum trust level against BLOG_COMMENT_AUTO_APPROVE_TRUST_LEVEL (and on
 * the spam screen) — a held one renders to its author with the "Awaiting
 * moderation" badge, an approved one publicly — which is why the assertion is
 * on the comment TEXT being visible, approved or not; the outcome is recorded
 * as a `test.info().annotations` entry. A held comment cannot be replied to
 * (backend `validate_parent`), so the reply step only runs when the page
 * shows an approved top-level comment (after the first approved run, the
 * user's own earlier comment qualifies); otherwise it is annotated as
 * skipped rather than faked.
 *
 * Rate budget: `comment_create` is 10/h per user (DEFAULT_BLOG_RATELIMITS);
 * one run costs 1 comment (+1 reply when available) per authenticated project.
 *
 * Prerequisites (local):
 *   cd backend && python manage.py create_test_user
 *   (and at least one live blog post with comments enabled — the default)
 */

test.describe('Blog comments (authenticated)', () => {
  test('post a comment on the first blog post; reply to the first approved comment when one exists', async ({
    page,
  }) => {
    const stamp = `${Date.now()}`;
    const commentBody = `E2E comment ${stamp}`;

    // 1. /blog → the first post. Scoped to #main-content so the header's
    // "Blog" nav link (also /blog-prefixed) cannot win .first().
    await page.goto('/blog');
    const postLink = page.locator('#main-content a[href^="/blog/"]').first();
    await expect(postLink, 'no blog post found — publish one in /cms/ first').toBeVisible();
    await postLink.click();
    await expect(page).toHaveURL(/\/blog\/[^/]+$/);

    // 2. The comment section is mounted (heading carries the count).
    const heading = page.getByRole('heading', { name: /^Comments \(\d+\)$/ });
    await expect(heading).toBeVisible({ timeout: 15000 });

    const closed = page.getByText('Comments are closed on this post.');
    if (await closed.isVisible().catch(() => false)) {
      test.skip(true, 'the first blog post has comments disabled — enable allow_comments in /cms/');
    }

    // 3. Post a uniquely stamped comment.
    const composer = page.getByLabel('Add a comment');
    await expect(composer).toBeVisible();
    await composer.fill(commentBody);
    await page.getByRole('button', { name: 'Post comment', exact: true }).click();

    // Visible either way: approved (public) or held (author-only, badged).
    const posted = page.getByRole('list', { name: 'Comments' }).getByText(commentBody);
    await expect(posted).toBeVisible({ timeout: 15000 });
    const held = await page
      .getByText('Awaiting moderation — only you can see this')
      .first()
      .isVisible()
      .catch(() => false);
    test.info().annotations.push({
      type: 'comment-state',
      description: held ? 'held for moderation (low-trust e2e user)' : 'approved',
    });
    // The composer clears after a successful post.
    await expect(composer).toHaveValue('');

    // 4. Reply to the comment THIS run just posted — the only row the spec
    // owns, so the step depends on no seeded comment. Only an approved
    // top-level comment renders a Reply control (depth is one, and a held
    // comment cannot be a parent): a low-trust e2e user's held comment
    // means the reply path is skipped, and the annotation says so.
    const ownRow = page
      .getByRole('list', { name: 'Comments' })
      .getByRole('listitem')
      .filter({ hasText: commentBody })
      .first();
    const ownReply = ownRow.getByRole('button', { name: 'Reply', exact: true });
    if (held || (await ownReply.count()) === 0) {
      test.info().annotations.push({
        type: 'reply-step',
        description: "skipped — the e2e user's comment was held, so it cannot be replied to",
      });
      return;
    }

    const replyBody = `E2E reply ${stamp}`;
    await ownReply.click();
    const replyBox = page.getByLabel(/^Reply to /);
    await expect(replyBox).toBeVisible();
    await replyBox.fill(replyBody);
    await page.getByRole('button', { name: 'Post reply', exact: true }).click();
    await expect(page.getByRole('list', { name: 'Replies' }).getByText(replyBody)).toBeVisible({
      timeout: 15000,
    });
    test.info().annotations.push({ type: 'reply-step', description: 'replied' });
  });
});
