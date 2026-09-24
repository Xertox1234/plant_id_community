---
status: completed
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

- **Item 11 (round 2):** `test_previews_a_brand_new_never_saved_post` copies
  `PreviewOnCreateView.get_object()` but not the `get_form()` step that follows
  it, so the draft never carries categories, tags or a url_path. Round 2's probe
  showed those serialize fine with a pk-less page; pin it with one populated
  relation.

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

- [x] Items 1–3: preview hardening is done or explicitly accepted, with a reason.
- [x] Items 4–8 and 11: each test gap is closed, and each new test is mutation-checked.
- [x] Item 9: the profile and notification services handle a stale CSRF token.

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

### 2026-09-24 - Done: items 1–9 and 11 (10 is information only)

**Preview hardening (backend, `apps/blog/api/viewsets.py`, settings)**

- **Item 1.** `BlogPostPreviewAPIViewSet` now calls `unsign(token,
  max_age=PREVIEW_TOKEN_MAX_AGE)` (1 hour) before loading the draft.
  `SignatureExpired` is a `BadSignature`, so a stale token is a 404. Every
  Preview click signs a fresh token, so editors lose nothing. The response
  gets `add_never_cache_headers` (`no-store, private`).
- **Item 2.** `settings.validate_preview_client_url` raises
  `ImproperlyConfigured` at startup on a `{`/`}` value, the pre-0.9 path
  template. It does not verify Railway's actual value (todo 406 owns that).
- **Item 3.** `get_urlpatterns` exposes only the listing route, so the
  inherited `<int:pk>/` and `find/` routes are gone (404). The dead
  `known_query_parameters` union and the `detail_view` override were removed.

**Test gaps**

- **Item 4.** A fake `HeadlessPreviewMixin` model that is not a
  `BlogPostPage`, with a validly signed token, is a 404.
- **Item 5.** Warming the live post's cache first still serves the draft.
- **Item 6.** `fetchBlogPreview`: URL and params, 404 → "Preview not found or
  expired" (cause attached), other errors unchanged.
- **Item 7.** Both CSP dicts now take `frame-src` from one module constant,
  `PREVIEW_FRAME_SRC`. The test pins that the constant carries the origin and
  that both `"frame-src"` entries in `settings.py` are that name (AST check),
  because only one dict is ever built per run. It is **not** named `CSP_*`:
  django-csp 4 flags any `CSP_`-prefixed setting as its old format
  (`csp.E001`), which failed `manage.py check` in the first attempt.
- **Item 8.** `CommunityExpertsModule` tests assert `[data-presence]`, not
  `.bg-ok`.
- **Item 11.** A never-saved draft with a populated category serializes it.

**Web client**

- **Item 9.** `profileService` and `notificationService` now go through the
  shared `apiClient`. They inherit its stale-CSRF refresh-and-retry and send
  the CSRF header only on mutations; a bodyless GET carries no
  `Content-Type`. Signatures and error messages are unchanged. Premise
  correction: `apiClient` has **no** 401 refresh (only the CSRF retry), so
  none was inherited; token refresh lives in `AuthContext`.

**Evidence**

- Backend: 5 new tests failed on the original code (expiry, no-store, routes,
  URL format, frame-src constant). Items 4, 5 and 11 pin existing behavior,
  so they were mutation-checked instead, each red once: drop the
  `issubclass(model, BlogPostPage)` half; serve the preview through the
  parent's cached `detail_view`; strip the pk-less draft's categories.
  `pytest apps/blog/tests/test_page_preview.py`: 18 passed.
  `pytest apps/blog apps/core --create-db`: 1679 passed, 7 skipped after the rename
  (the 4 `test_r2_storage` failures were `csp.E001` from the first name).
- Web (items 6, 8, 9): type-check and lint clean; full `npx vitest run`
  1417 passed. Fail-before: the new profile tests fail 9/9 on the old
  service. Mutations: item 6 (3 red), item 8 (2 red), item 9 CSRF retry
  (3 red).

### 2026-09-24 - Review round 1 (bundled /code-review, PR #817): 5 repaired

- **Item 2's check could take production down.** It raised
  `ImproperlyConfigured` at settings import, so a stale Railway value would
  have crash-looped the backend and `forum-prune-cron` over an editor-only
  feature. `validate_preview_client_url` now returns a problem string, and
  `validate_environment()` logs it as a startup warning. It also now catches
  a value with no scheme or host (CSP origin `://`).
- **Non-JSON 2xx bodies resolved as strings under axios** (fetch's
  `response.json()` rejected them), so the unread badge could show
  `undefined`. Both services reject a non-object body again.
- `PREVIEW_TOKEN_MAX_AGE` moved to `apps/blog/constants.py` (no magic
  numbers).
- The item-4 test's comment claimed the signed token got past a signature
  check. The model guard runs first; comment corrected.
- The expiry test patched `time.time` process-wide; it now stamps only
  `TimestampSigner.timestamp`.
- Tests: 2 new web tests (non-JSON body rejects), the settings test now
  asserts return values plus the `validate_environment` wiring (warnings,
  never `critical_errors`). Mutations red: both web guards (2), dropping
  `max_age` (expiry test).
- Deferred to todo 434: unread-count polls now log through the client's
  error interceptor (Sentry noise), expiry lives in the viewset rather than
  the model, two near-identical AxiosError translators, and axios's
  "Network Error" text reaching the profile banner.
