---
status: pending
priority: p4
issue_id: "486"
tags: [mobile, flutter, forum, testing]
dependencies: []
source_review: "PR #878"
---

# Mobile inbox viewer filter: non-blocking findings from PR #878 (todo 463)

## Problem

PR #878 made `AuthorAvatarCluster` leave out the viewer, and the inbox now watches
`userProfileServiceProvider` to learn who that is. Both review rounds were clean. These are the
non-blocking findings.

## Findings

1. **The inbox tests make a real network call.** The shared `_wrap`/`_routed` helpers in
   `forum_conversations_screen_test.dart` and `forum_conversations_group_test.dart`, and
   `test/routing/app_router_test.dart:267`, do not override `userProfileServiceProvider`. Every
   existing inbox test sends a real `GET /auth/user/`, gets flutter_test's mocked 400
   (`[USER_PROFILE ERROR]` in the log), and passes only because the error falls back to a null
   viewer. Riverpod 3 also schedules retries after it.
2. **A reload shows the viewer again.** `asData?.value` is null while the profile reloads, so
   during a refresh the viewer's own avatar comes back into every cluster and the label flips
   from "N other members" to "N+1 members". `.value?.username` keeps the last known value
   (`forum_conversations_screen.dart:29`).
3. **A viewer-only group has no label.** When the viewer is the only member, `others` is empty and
   the widget falls back to the bare group glyph, which has no Semantics label
   (`forum_avatar_cluster.dart:44`).
4. **No narrow-viewport test.** The "+N" disc widens the leading slot from 74px to 95px. No test
   pumps a 5+ member group row at 375pt or narrower (the todo 317 pattern in
   `docs/LEARNINGS.md` 2026-08-28).
5. **The loading invariant is untested.** The doc comment says the profile load "never holds the
   list back". No test pumps `FakeUserProfileService(gate:)` to prove it.
6. **The whole screen rebuilds on any profile edit.** Narrowing the watch with
   `.select((s) => s.value?.username)` avoids that.

## Acceptance Criteria

- [ ] No inbox or router test sends a real profile request. The helpers override the provider,
      and one test pins the null-viewer fallback on purpose.
- [ ] A reload keeps the last known viewer, with a test.
- [ ] A viewer-only group has a Semantics label, with a test.
- [ ] A 375pt pump of a 5+ member group row shows no overflow.
- [ ] A gated-profile test shows the list rendering first, then the viewer dropping out.
- [ ] The inbox watches only the username.

## Work Log

### 2026-09-28 - Filed from PR #878 rounds 1 and 2 (todo sweep run 2026-09-28-2018)
