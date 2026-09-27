---
status: completed
priority: p3
issue_id: "412"
tags: [backend, web, mobile, users]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
source_finding: "owner decision 2026-09-23"
---

# Wire up onboarding (`me/onboarding/*`) and fix the broken demo-data seeder

## Problem

`me/onboarding/*` (4 routes, about 190 LOC) has no client. The owner decided
(todo 405) to wire it up. The adversarial verifier (todo 405, 2026-09-23)
proved the demo-data half is broken three ways:

- `POST me/onboarding/create-demo-data/` returns 500:
  `_create_demo_identifications` imports `apps.common.models` and
  `IdentificationResult`, and neither exists.
- Even with the imports fixed, it would fail again: `is_demo_data` and
  `image_1_url` are not fields (the request model has `image_1`).
- `DELETE me/onboarding/demo-data/` returns 500 on its own, because
  `DemoData.objects.filter(user=…)` uses a field that does not exist (the
  field is `created_by`).

`OnboardingProgress` is created by a live signal (`users/signals.py:56`).

## Findings

Evidence is recorded in todo 405's 2026-09-23 Work Log. It came from a
`get_resolver()` route walk, client greps, and an adversarial verifier that ran
the endpoints against a test DB.

## Recommended Action

1. Decide what onboarding is for in Houseplant MD: steps, and whether demo
   data belongs at all.
2. Rebuild the demo seeder against the real models, or delete it. Fix the
   delete view.
3. Build the onboarding UI on the chosen client(s).

## Technical Details

See the file references above, and todo 405's Work Log.

## Acceptance Criteria

- [x] Both demo-data endpoints return 2xx or are removed. Tests pin them. (removed; `test_the_demo_data_endpoints_are_gone`)
- [x] A client shows onboarding progress. (mobile home `OnboardingChecklistCard`, see Work Log)

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.

### 2026-09-24 - Owner decision: checklist onboarding, no demo data (gate removed)

Decided by the owner: onboarding is a **progress checklist** (e.g. first plant
ID, first forum post, profile filled in) on the existing `OnboardingProgress`
model, shown by a client. **Delete** the demo-data seeder and both demo-data
endpoints (`POST me/onboarding/create-demo-data/`, `DELETE me/onboarding/demo-data/`)
instead of rebuilding them — that satisfies AC 1's "or are removed" branch.
Ready for a sweep.

### 2026-09-26 - Owner decision: the checklist lives on mobile home

The onboarding checklist is shown on the **mobile home screen** (primary
platform) as a dismissible card; there is no web UI. Steps come from
`OnboardingProgress` flags (first identification, first forum post, profile
filled in, and so on). `first_care_reminder_created` refers to a model that
todo 410 deletes (`users.CareReminder`), so re-point that step to "first care
task" or drop it. Deleting the `DemoData` model and the `demo_*` fields is a
migration and a scope call: leave them unless the endpoint removal entails
it, and say so in the PR. Do this todo before todo 410 (shared files).

### 2026-09-26 - Completed (PR #851, P3 sweep)

- **Backend.** `apps/users/onboarding.py` derives three steps from what the
  user did:
  - `identify_plant`: recorded by the identify endpoint on an answer with a
    suggestion, since results are not persisted (todo 411). Pre-405 request
    rows also count.
  - `forum_post`: a live post.
  - `save_topic`: a `TopicBookmark`. This replaced "profile" (owner,
    2026-09-26), because mobile cannot edit a profile yet. **Todo 455**
    restores it.

  Completion is recorded once in `onboarding_completed_at`, so undoing a
  step does not bring the card back (review round 2). PATCH accepts JSON
  booleans only, the derived flags are not client-settable, and a bad
  `onboarding_completed_at` is a 400. The demo seeder and both demo
  endpoints are deleted; the `DemoData` model and the `demo_*` fields stay
  (a migration, out of scope).
- **Mobile.** `OnboardingChecklistCard` on `HomePage` shows "N of 3 done",
  with one semantics node per row. Each step opens its screen: `push` for
  the camera, `go` for the forum tab. The card refreshes when the router
  lands on Home and when the app resumes. Dismiss is optimistic and guarded
  against a sign-out mid-flight. Nothing renders when signed out, complete
  or dismissed.
- **Verified.**
  - pytest `apps/users apps/core apps/plant_identification`: 1923 passed
    before the repairs; `apps/users apps/plant_identification`: 464 after.
    The onboarding tests are 15.
  - `flutter test`: 824 passed. The 9 card tests are mutation-checked: the
    row container, the dismiss rollback, go vs push, and refresh-on-Home
    inside a real `StatefulShellRoute`.
  - Backend mutation checks: the identify hook, boolean validation, live
    posts only, "Unknown" not counting, and stored completion.
  - `spectacular --validate` passes.
- **Reviews.**
  - Round 1: bundled `/code-review` (10 findings), django-drf (10) and
    flutter-dart (7). Fixed in d8ff68ad.
  - Round 2: `/code-review` found 1 (a completed checklist reappeared),
    fixed in this commit.
  - Codified in `flutter.md` and `api.md`.
