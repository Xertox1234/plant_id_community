---
status: completed
priority: p4
issue_id: "434"
tags: [web, backend, blog, observability]
dependencies: []
source_review: "PR #817"
triage: ready
triaged: 2026-09-28
---

# Follow-ups from moving profile/notification services onto apiClient (todo 407)

## Problem

The bundled `/code-review` of PR #817 raised these as non-blocking.

## Findings

- **Sentry noise from unread-count polling.** `UnreadNotificationsContext`
  polls every 30s per tab. The old fetch path failed silently; now every
  failure goes through `apiClient`'s response interceptor, which calls
  `logger.error('HTTP error')` (a Sentry event in production). A backend
  blip, or an expired cookie (apiClient has no 401 refresh), produces one
  event per tab every 30s. Give polling calls a way to opt out of that log.
- **Preview expiry lives in the viewset, not at the token source.**
  `BlogPostPreviewAPIViewSet` unsigns with `max_age`, then the library
  unsigns again without it. Another caller of
  `BlogPostPage.get_page_from_preview_token` would get tokens that never
  expire. Overriding that method on the model fixes both.
- **Two near-identical AxiosError → Error translators**
  (`profileService.toProfileError`, `notificationService.toNotificationError`)
  with different fallback strings. Share one next to `httpClient`.
- **Network/timeout errors show axios text** ("Network Error", "timeout of
  30000ms exceeded") in the profile banner instead of the page's fallback.

## Acceptance Criteria

- [x] Each finding is fixed with a test, or declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #817 review round 1

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- **Sentry noise — fixed.** `apiClient` takes a `quietErrors` request option
  (axios module augmentation in `web/src/utils/httpClient.ts`); a quiet failure
  is logged with `logger.info` (a breadcrumb) instead of `logger.error` (a
  Sentry event), and still rejects. `fetchUnreadCount` — the 30s poll — sets it;
  user-initiated calls keep `logger.error`. Tests in `httpClient.test.ts` and
  `notificationService.test.ts`.
- **Preview expiry — fixed at the source.** `BlogPostPage.get_page_from_preview_token`
  now unsigns with `max_age=PREVIEW_TOKEN_MAX_AGE` before the library's lookup,
  so every caller gets expiry; the viewset's own unsign is gone. New
  `test_the_model_itself_refuses_an_expired_token` calls the model directly
  (mutation-checked: removing the model's unsign fails it and the viewset test).
- **Two translators — merged.** `toProfileError` and `toNotificationError` are
  replaced by `toHttpError`/`httpErrorMessage` in `web/src/utils/httpError.ts`
  (its own file: `blogService.test` mocks `httpClient` with a default export
  only). One fallback wording, `Request failed (HTTP <status>)`, which still
  satisfies both services' existing tests unchanged.
- **Axios text in the banner — fixed.** `toHttpError` turns a network error or
  timeout into "Could not reach the server. Check your connection and try
  again." (the axios error kept as `cause`); cancellations and non-axios errors
  pass through. Tests in `httpError.test.ts` and `profileService.test.ts`.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `sh -c "cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_4f691fda-f6b-2/backend && python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_4f691fda-f6b-2/scripts/todos/slot_env.py 2 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest apps/blog/tests/test_page_preview.py --create-db -v -p no:cacheprovider && cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_4f691fda-f6b-2/web && ./node_modules/.bin/vitest run src/utils/httpError.test.ts src/utils/httpClient.test.ts src/services/profileService.test.ts src/services/notificationService.test.ts src/contexts/UnreadNotificationsContext.test.tsx && ./node_modules/.bin/tsc --noEmit && ! grep -rn -e toProfileError -e toNotificationError src"` — evidence `.sweep-evidence/g10/434-ac0.txt`, last lines:

  ```text

   Test Files  5 passed (5)
        Tests  64 passed (64)
     Start at  16:20:11
     Duration  1.15s (transform 329ms, setup 817ms, import 505ms, tests 293ms, environment 3.18s)
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
