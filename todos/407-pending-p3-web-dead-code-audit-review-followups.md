---
status: pending
priority: p3
issue_id: "407"
tags: [blog, web, testing, security, review-followup]
dependencies: []
source_review: "docs/audits/2026-09-23-web-dead-code.md"
source_finding: "review-r1"
---

# Web dead-code audit: non-blocking review findings (round 1)

## Problem

Review round 1 on the audit PR had four passes: bundled /code-review, plus the
wagtail, react-typescript and cross-cutting checklist reviewers. They found one
real blocker, fixed in the PR: a never-saved post's preview 500'd in
`get_comment_count`. Everything else was non-blocking. Under the two-round
review budget, those findings land here instead of widening the PR.

## Findings

**Preview hardening (backend)**

- **Item 1:** **Preview tokens never expire by themselves.**
  - `get_page_from_preview_token` calls `TimestampSigner.unsign()` with no
   `max_age`.
  - `PagePreview.garbage_collect()` runs only inside `serve_preview`, and
   `created_at` is a date, not a time.
  - So a leaked preview URL (browser history, Referer, logs) keeps working
   until some editor previews again.
  - The response also carries no `Cache-Control: no-store`.
  - `backend/apps/blog/api/viewsets.py` `BlogPostPreviewAPIViewSet.get_object`.
- **Item 2:** **Old env value format.** The env var kept its name, `HEADLESS_PREVIEW_CLIENT_URL`,
   but its expected value changed from `…/{content_type}/{token}/` to
   `…/blog/preview`. A stale Railway value in the old format produces
   unroutable URLs. Either reject values containing `{` at startup, or check
   this as part of todo 406.
- **Item 3:** **Dead `known_query_parameters`.** The union is never checked, because the
   overridden `listing_view` does not call `check_query_parameters`. The
   inherited `<int:pk>/` detail route ignores `pk`, and the inherited `find/`
   route runs against live pages. It is confusing surface, so trim or document
   it.

**Test gaps**

- **Item 4:** Nothing discriminates the `issubclass(model, BlogPostPage)` half of the
   content-type guard, because BlogPostPage is the only `HeadlessPreviewMixin`
   model. Add a unit test with a fake mixin model that is not a BlogPostPage.
- **Item 5:** Only the write direction of the cache bypass is pinned. Add a test that
   warms `BlogCacheService` for the live post first, then asserts the preview
   still returns the draft.
- **Item 6:** `fetchBlogPreview` has no unit test in `web/src/services/blogService.test.ts`.
   Cover the URL and params, and the 404 message mapping.
- **Item 7:** The CSP `frame-src` test reads only the report-only dict under `DEBUG=True`,
   never the enforcing production dict. Use a shared constant, or add a
   `DEBUG=False` assertion.
- **Item 8:** `CommunityExpertsModule.test.tsx` asserts on the `.bg-ok` class. Assert on
   Avatar's stable `[data-presence]` hook instead.

**Web client**

- **Item 9:** `profileService.authenticatedFetch` has no retry on a stale CSRF token and
   no refresh on a 401, unlike `apiClient`. It also sends
   `Content-Type: application/json` on a bodyless GET, which forces a CORS
   preflight. `notificationService` has the same shape, so consider moving
   both onto `apiClient`.

**Environment (information only)**

- **Item 10:** The local dev Postgres is missing at least `wagtailcore_apitoken`, so it is
  not fully migrated to Wagtail 8.0. Run `manage.py migrate` before any
  manual `/cms/` check (todo 406).

## Recommended Action

Each item is independent and small. 1 and 2 matter most, because they are
production-facing.

## Technical Details

See each item's file reference. The review reports are summarised in the PR
description.

## Acceptance Criteria

- [ ] Items 1–3: preview hardening is done or explicitly accepted, with a reason.
- [ ] Items 4–8: each test gap is closed, and each new test is mutation-checked.
- [ ] Item 9: the profile and notification services handle a stale CSRF token.

## Work Log

### 2026-09-23 - Filed from the audit PR's review round 1

Non-blocking under the two-round review budget.

The wagtail reviewer's second "blocking" claim was **refuted**. It said
previewing on the create screen crashes in the library's `create_page_preview`
because `get_parent()` is None. Wagtail 8's **pages** `PreviewOnCreateView`
sets `depth`/`path` from the parent, so `get_parent()` resolves. The
reviewer's probe used a bare `BlogPostPage()`, which the admin never produces.
`test_previews_a_brand_new_never_saved_post` now mirrors that view exactly and
mints its token through `create_page_preview()`.
