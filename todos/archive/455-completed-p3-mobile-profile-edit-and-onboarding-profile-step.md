---
status: completed
priority: p3
issue_id: "455"
tags: [mobile, flutter, onboarding, profile]
dependencies: []
source_review: "todos/archive/412-completed-p3-wire-up-onboarding-and-fix-demo-seeder.md"
triage: ready
triaged: 2026-10-10
owner_decision: "Add profile as a 4th checklist step, keeping save_topic (2026-09-28)"
---

# Mobile profile editing, then restore the onboarding "profile" step

## Problem

The mobile `ProfileScreen`'s edit button only shows a SnackBar reading "Edit
profile coming soon!" (`lib/features/profile/profile_screen.dart`, a TODO).
So a mobile user cannot set a bio or an avatar. Because of that, todo 412's
onboarding checklist replaced the owner's example step "profile filled in"
with "save a topic" (owner decision 2026-09-26, PR #851).

## Recommended Action

1. Build a minimal mobile profile-edit screen: bio and avatar, using the
   existing `PATCH /api/v1/auth/user/update/` and the avatar upload.
2. Add a `profile` step back to `apps/users/onboarding.CHECKLIST_STEPS`
   (done = a non-blank bio or an avatar) and to the mobile
   `onboardingSteps` map, linked to the edit screen.

## Acceptance Criteria

- [x] A mobile user can set a bio and an avatar
- [x] The checklist's profile step ticks once either is set, and links to the edit screen

## Work Log

### 2026-09-26 - Filed from the todo 412 review (PR #851)

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0053)

- New mobile `EditProfileScreen` at `/profile/edit` (auth-protected, top-level): bio field saved with `PATCH /auth/user/update/`, and an avatar picked from the gallery (bounded to 1024 px, 2 MB checked client side) uploaded as a multipart PATCH to the same endpoint via the new `UserProfileService.uploadAvatar`. The Profile tab's pencil now opens it instead of a "coming soon" SnackBar.
- Backend `CHECKLIST_STEPS` gains `profile` as the fourth step, keeping `save_topic` (owner decision 2026-09-28); done = a non-blank bio or an avatar. The mobile `onboardingSteps` map links it to the edit screen (pushed).
- `current_user` and `update_profile` now pass the request to the serializer, so `avatar` is an absolute URL on local storage too and `avatar_thumbnail` is filled; a thumbnail that cannot be generated returns null instead of a 500.
- Two existing onboarding tests (`test_every_step_done_is_complete`, `test_a_finished_checklist_stays_finished_after_a_step_is_undone`) now also fill a bio, because "every step done" includes the new step.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0053)

- AC 1: `sh -c 'cd backend && python3 scripts/todos/slot_env.py 3 -- backend/venv/bin/python -m pytest apps/users/tests/test_profile_update.py --create-db -q -p no:warnings && cd plant_community_mobile && flutter test --reporter expanded test/features/profile/ test/routing/app_router_test.dart'` — evidence `.sweep-evidence/g3/455-ac0.txt` (not committed), last lines:

  ```text
  00:02 +39: plant_community_mobile/test/routing/app_router_test.dart: AppRouter Tests Authentication Guard Tests edit profile redirects a signed-out user to login (todo 455)
  00:02 +40: plant_community_mobile/test/routing/app_router_test.dart: AppRouter Tests Authentication Guard Tests edit profile builds EditProfileScreen for a signed-in user (todo 455)
  00:02 +41: plant_community_mobile/test/routing/app_router_test.dart: AppRouter Tests Authentication Guard Tests Should allow authenticated user to access protected route
  00:02 +42: plant_community_mobile/test/routing/app_router_test.dart: AppRouter Tests Authentication Guard Tests Should redirect authenticated user away from login screen
  00:02 +43: All tests passed!
  ```

- AC 2: `sh -c 'cd backend && python3 scripts/todos/slot_env.py 3 -- backend/venv/bin/python -m pytest apps/users/tests/test_onboarding_checklist.py --create-db -q -p no:warnings && cd plant_community_mobile && flutter test --reporter expanded test/features/onboarding/onboarding_checklist_card_test.dart'` — evidence `.sweep-evidence/g3/455-ac1.txt` (not committed), last lines:

  ```text
  00:00 +7: Dismiss hides the card and tells the server
  00:00 +8: a refused dismiss brings the card back
  [ONBOARDING] Dismiss failed: ApiException: Server error
  00:00 +9: an unknown step key from a newer server is skipped
  00:00 +10: All tests passed!
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0053)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
