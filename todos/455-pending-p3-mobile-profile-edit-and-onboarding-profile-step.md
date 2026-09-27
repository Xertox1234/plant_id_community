---
status: pending
priority: p3
issue_id: "455"
tags: [mobile, flutter, onboarding, profile]
dependencies: []
source_review: "todos/archive/412-completed-p3-wire-up-onboarding-and-fix-demo-seeder.md"
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

- [ ] A mobile user can set a bio and an avatar
- [ ] The checklist's profile step ticks once either is set, and links to the edit screen

## Work Log

### 2026-09-26 - Filed from the todo 412 review (PR #851)
