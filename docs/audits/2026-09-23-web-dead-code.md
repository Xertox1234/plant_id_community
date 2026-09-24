# Audit: Web dead and half-wired code

> **Date:** 2026-09-23
> **Trigger:** The owner keeps finding unused variables, and code that exists but
> is not wired (todo 398/403's "decorative" sites). This is a sweep of `web/src`
> for dead code, and for half-built features that were never connected.
> **Domains:** react-typescript (dead-code focus only)
> **Baseline:** vitest 1414 passed (101 files) | tsc 0 errors | eslint 0 errors

## Method

- **knip 5, twice.** The default run treats test files as entry points, so it
  misses a component that only its own test imports. The `--production` run
  catches those: `ClayButton`, `GrainOverlay`, `streamFieldBlocks`,
  `diagnosisService`.
- **`react-typescript-reviewer`** looked for what knip cannot see: props no
  caller passes, stub handlers, controls that look interactive but do nothing,
  and dangling routes.
- **`general-purpose`** mapped every web API call to a backend route with
  `django.urls.resolve()`, not just grep. It also mapped backend endpoints
  that no client calls.
- **Verification.** Every row below was re-checked in the current code by the
  auditor (file read or grep). Agent severities were calibrated down where
  noted.

Classification: **remove** (truly dead) or **wire up** (half-finished and
apparently intended).

## Findings

### High

| ID | Finding | Class | Agent | File(s) | Research | Status | Verification |
| -- | ------- | ----- | ----- | ------- | -------- | ------ | ------------ |
| H1 | The whole diagnosis-card and reminder feature (7 files plus its service) calls 16 backend endpoints that no longer exist. Migration 0025 deleted the `DiagnosisCard` and `DiagnosisReminder` models, and no route or viewset remains. The pages are also unrouted, so nothing reaches them. Routing them (todo 400 item 2) could not bring the feature back. | remove | knip + general-purpose | `src/pages/diagnosis/Diagnosis{List,Detail}Page.tsx`, `src/components/diagnosis/{DiagnosisCard,ReminderManager,SaveDiagnosisModal,streamFieldBlocks}.tsx`, `src/services/diagnosisService.ts`, `src/utils/diagnosisDisplay.ts` | — | verified | `8d44b097`: Deleted 10 files (8 dead + 2 tests) and pruned the card/reminder types. tsc clean; `web/CLAUDE.md` diagnosisService mention dropped. Todo 400 item 2 closed with this evidence. |
| S1 | **Security (new, found while fixing M3):** `UserProfileSerializer` leaves `email` writable, so `PATCH /auth/user/update/` changes a signed-in user's email with no current-password check and no re-verification. | security (backend) | auditor | `backend/apps/users/serializers.py:129-175` | — | deferred | CSRF-protected and IsAuthenticated, so not cross-site; it is a missing re-auth step. Backend auth-contract change, out of a web dead-code PR: todo 404 (p2). |

### Medium

| ID | Finding | Class | Agent | File(s) | Research | Status | Verification |
| -- | ------- | ----- | ----- | ------- | -------- | ------ | ------------ |
| M1 | The notification bell has no `solution` case, so "your answer was accepted" notifications render as "X replied to …". `ForumNotificationVerb` also omits `'solution'`. | wire up | react-typescript-reviewer (agent: High; calibrated to Medium because it is wrong copy and the link still works) | `src/components/layout/NotificationBell.tsx:25-35`, `src/types/notifications.ts:27` | — | verified | `e3ba3bcd`: `'solution'` added to ForumNotificationVerb and to the bell's switch: "X accepted your answer in …". The new test failed first (TDD). |
| M2 | Wagtail's "Preview" button links to `/blog/preview/:content_type/:token`, which is a "coming soon" stub. The backend has `wagtail_headless_preview` installed, but no preview API route is registered. | wire up (web + backend) | react-typescript-reviewer (agent: High; calibrated to Medium because it affects editors only) | `src/pages/BlogPreview.tsx`, `backend/plant_community_backend/settings.py:214` | — | verified | `c487c328`: Broken at 4 hops, all fixed. (1) The REMOVED `HEADLESS_PREVIEW_CLIENT_URLS` made every library settings read raise RuntimeError; a probe confirmed it, and the setting moved to `WAGTAIL_HEADLESS_PREVIEW`. (2) Query params vs a path-param route: the route is now `/blog/preview`. (3) No draft API: `GET /api/v2/page_preview/`, signed-token, BlogPostPage-only, cache-bypassing. (4) CSP `frame-src`. 9 backend + 3 web tests; the guard and cache mutants are both caught. Production checks are todo 406. |
| M3 | `/profile`, linked from the user menu, shows "Coming Soon: Profile editing…". Meanwhile `PATCH /api/v1/auth/user/update/` works and only mobile calls it. | wire up | react-typescript-reviewer | `src/pages/ProfilePage.tsx:57-63` | — | verified | `66f6ac7a`: profileService + editable ProfilePage (first and last name, bio, location, website; only changed fields sent). Email is read-only on purpose (see S1). No refreshUser(), which nulls the user on a failed fetch (todo 310). 9 tests; the send-whole-form mutant is caught. kimi-review skipped as an auth surface (commit gate only). |
| M4 | "Forgot your password?" is a permanently disabled `<button>` with a `hover:` style, so it reacts to hover and does nothing. The backend has no password-reset flow. | remove | react-typescript-reviewer | `src/pages/auth/LoginPage.tsx:233-241` | — | verified | `e3ba3bcd`: Button removed; a test pins its absence. kimi-review skipped (auth page). |

### Low

| ID | Finding | Class | Agent | File(s) | Research | Status | Verification |
| -- | ------- | ----- | ----- | ------- | -------- | ------ | ------------ |
| L1 | `BlogPage.tsx` is a "Blog posts coming soon" placeholder that `BlogListPage` replaced. It is unrouted. | remove | knip | `src/pages/BlogPage.tsx` | — | verified | `8d44b097`: Deleted. |
| L2 | `App.css`: nothing has imported it since the initial commit. | remove | knip | `src/App.css` | — | verified | `8d44b097`: Deleted. |
| L3 | `useHandlePageChange` was extracted for ThreadList and Search (#367). Both have since stopped paginating by `?page`. | remove | knip | `src/hooks/useHandlePageChange.ts` | — | verified | `8d44b097`: Deleted. |
| L4 | `utils/constants.ts` holds forum upload limits that nothing imports. | remove | knip | `src/utils/constants.ts` | — | verified | `8d44b097`: Deleted. |
| L5 | `ClayButton` and `GrainOverlay` are imported only by their own tests; `HomePage.test` asserts they are *not* rendered. | remove | knip --production | `src/components/ui/{ClayButton,GrainOverlay}.tsx` (+ tests) | — | verified | `8d44b097`: Deleted with their tests; HomePage.test's vacuous grain-overlay assertion removed. |
| L6 | `plantIdService.getHistory` calls `/api/v1/plant-identification/history/`, which has no route, and nothing calls it. | remove | general-purpose | `src/services/plantIdService.ts:75,216` | — | verified | `8d44b097`: getHistory, its type and its 4 tests removed; a stale comment reference fixed. |
| L7 | Unused aliases: `forumService.fetchCategoryTree` (a duplicate of `fetchCategories`) and the exported `authService` object (`AuthContext` imports the namespace instead). | remove | knip | `src/services/forumService.ts:149`, `src/services/authService.ts:421-429` | — | verified | `8d44b097`: Both aliases removed. |
| L8 | Unused devDependencies `autoprefixer` and `postcss`. There is no PostCSS config; Tailwind 4 runs through `@tailwindcss/vite`. | remove | knip | `package.json` | — | verified | `8d44b097`: `npm uninstall autoprefixer postcss`; `check:classes` builds clean. |
| L9 | `TipTapEditor`'s `editable={false}` read-only mode (~8 branches) is exercised only by tests. | remove or adopt (decide) | react-typescript-reviewer | `src/components/forum/TipTapEditor.tsx` | — | verified | `b1f3e12d`: `editable` prop and 7 guarded branches removed; the 2 read-only tests dropped; 58 editor tests pass. |
| L10 | `ThreadCard`'s `compact` mode (~6 branches) is exercised only by tests. | remove | react-typescript-reviewer | `src/components/forum/ThreadCard.tsx:11,30` | — | verified | `b1f3e12d`: `compact` removed with its 3 tests; the ForumSkeleton comment updated. |
| L11 | `Avatar`'s `presence` prop has no caller. `CommunityExpertsModule` (#554, after #536) re-implements the online dot inline with different tokens. | wire up (consolidate) | react-typescript-reviewer | `src/components/ui/Avatar.tsx:7-32`, `src/components/forum/rail/CommunityExpertsModule.tsx:55-66` | — | verified | `dd931dbf`: The rail renders `<Avatar size="sm" presence>`. Shipped dot tokens kept (`bg-ok`, ring), so no colour change; expert avatars gain the standard 1px border-line-2. |
| L12 | `RequestContext` / `useRequestId` has no reader. Every real consumer calls `getOrCreateRequestId()` directly, yet the provider still re-renders the app subtree on every `rotateRequestId()`. | remove | react-typescript-reviewer + knip --production | `src/contexts/RequestContext.tsx`, `src/main.tsx:78` | — | verified | `b1f3e12d`: Provider, hook and listener plumbing removed; utility behaviour re-pinned in the new `utils/requestId.test.ts` (8 tests). |
| L13 | Backend endpoints that no client calls: forum AI summary and similar-topics, most of the blog v1/v2 read API, plant CMS v2, most of plant-ID v1, `users/me/*` onboarding, reminders and dashboard, and all of `/garden/*` and `/calendar/*`. The legacy unversioned `/api/` mount carries a "remove after 2025-07-01" TODO, and its only web user was `diagnosisService` (H1). | triage (product) | general-purpose | `backend/**/urls.py` | — | deferred | Product triage; see todo 405 |
| L14 | `BlogPostPage.preview_modes` offers "Mobile (Flutter)", but wagtail-headless-preview 0.9 calls `get_client_root_url(request)` without the mode, so it opens the web preview and the `plantid://` branch is unreachable. | wire up or remove | auditor (advisor) | `backend/apps/blog/models.py` (`preview_modes`) | — | deferred | Read `HeadlessPreviewMixin.get_preview_url`: no mode argument. Folded into todo 405. |

## Deferred Items

| ID | Todo | Rationale |
| -- | ---- | --------- |
| S1 | todo 404 (p2) | Backend auth-contract change. Mobile uses the same endpoint, so check what it sends first. |
| L13 | todo 405 (p3) | A product decision per API family (wire up, mobile roadmap, or remove); cannot be fixed mechanically. |
| L14 | todo 405 (p3) | Belongs with the preview-mode and endpoint triage. |
| M2 (production) | todo 406 (p3) | The code is verified; the Railway `HEADLESS_PREVIEW_CLIENT_URL` value and live preview-panel framing can only be checked in production. |

## Summary

| Severity  | Found | Verified | Deferred | False-positive | Open  |
| --------- | ----- | -------- | -------- | -------------- | ----- |
| Critical  | 0     | 0        | 0        | 0              | 0     |
| High      | 2     | 1        | 1        | 0              | 0     |
| Medium    | 4     | 4        | 0        | 0              | 0     |
| Low       | 14    | 12       | 2        | 0              | 0     |
| **Total** | 20    | 17       | 3        | 0              | **0** |

**Found vs. fixed (dead code):** knip `--production` "Unused files" went from 20
to 6. The 6 left are test helpers, e2e setup and CI scripts, which production
mode does not treat as entry points, so there are 0 unused production source
files.

**Close baseline:**

- web: vitest 1364 passed (100 files); tsc, eslint and prettier clean;
  `check:classes` passes (131 files).
- backend: `apps/blog` plus `apps/core` 1698 passed, 7 skipped; `manage.py
  check` and `makemigrations --check` clean.

## Fix Commits

| Commit | Description |
| ------ | ----------- |
| `8d44b097` | Delete dead code (H1, L1–L8) |
| `b1f3e12d` | Drop unused component modes and RequestContext (L9, L10, L12) |
| `e3ba3bcd` | Solution notification label; remove dead forgot-password (M1, M4) |
| `dd931dbf` | Experts rail via Avatar presence (L11) |
| `66f6ac7a` | Editable /profile (M3) |
| `c487c328` | Blog Preview end to end (M2) |

## Codification (Phase 8)

| Finding | Destination | Note |
| ------- | ----------- | ---- |
| —       | —           | —    |

## Finding Status

- [ ] #S1 profile update changes email without verification → todo 404
- [x] #L13 backend endpoints no client calls → todo 405 (completed 2026-09-23)
- [x] #L14 dead "Mobile (Flutter)" preview mode → todo 405 (completed 2026-09-23)
- [ ] #M2 production preview checks → todo 406
- [ ] #review-r1 non-blocking review findings → todo 407
