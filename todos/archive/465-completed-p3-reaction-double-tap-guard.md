---
status: completed
priority: p3
issue_id: "465"
tags: [web, mobile, forum, bug]
dependencies: []
source_review: "todos/archive/394-completed-p3-triage-the-grandfathered-archived-todos.md"
triage: ready
triaged: 2026-09-30
---

# A fast double tap on a forum reaction adds it and removes it again

## Problem

Found by the todo 394 triage of archived todo 004 (reaction toggle race).
The server keeps the data consistent (a unique constraint, a locked
recount), but neither client guards against a second tap while the first
toggle is in flight:

- Web: `web/src/pages/forum/ThreadDetailPage.tsx` `handleReact` (about
  623–646) has no in-flight flag.
- Mobile: `forum_providers.dart` `toggleReaction` (about 525–528) mints a
  fresh idempotency key per tap. It lacks the `_bookmarkInFlight` /
  `_solutionInFlight` guard its sibling methods use.

So two quick taps send two toggles: a create, then a delete. The user's
reaction silently undoes itself.

## Acceptance Criteria

- [x] Web and mobile ignore a reaction tap on a post while that post's
      toggle is in flight, for the same reaction type.
- [x] A test on each client fires two taps before the first resolves and
      asserts one request.

## Work Log

### 2026-09-30 - Implemented by the todo sweep (run 2026-10-01-0121)

- Web: `ThreadDetailPage.handleReact` now keeps a `useRef<Set<string>>` of
  `postId:type` keys in flight; a tap whose key is already in the set
  returns without a request, and the key is released in `finally`, so a
  failure does not lock the button.
- Mobile: `TopicPosts.toggleReaction` gained the same per-(post, type)
  guard (`_reactionsInFlight`, released in `finally`), matching its
  `_bookmarkInFlight` / `_solutionInFlight` siblings; the request body
  moved unchanged into `_toggleReactionOnce`.
- The guard is per reaction type, as the criterion says: a different type
  on the same post, or another post, still sends.
- Tests: the web test and the mobile provider test hold the first toggle
  open, tap twice and assert one request, then show a different type
  still sends and the guard releases once settled. `FakeForumApi` gained
  `reactionCalls` and a `reactionGate`. Removing either guard line fails
  its test (checked by hand).

### 2026-09-30 - Verified by the todo sweep (run 2026-10-01-0121)

- AC 1: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_010041ec-ccf-2/web && npx vitest run --reporter=verbose src/pages/forum/ThreadDetailPage.test.tsx -t "reaction" && cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_010041ec-ccf-2/plant_community_mobile && flutter test test/features/forum/providers/forum_providers_test.dart --plain-name "TopicPosts.toggleReaction"` — evidence `.sweep-evidence/g2/465-ac0.txt`, last lines:

  ```text
  00:00 +0: TopicPosts.toggleReaction success writes the fresh reaction counts back to the post
  00:00 +1: TopicPosts.toggleReaction a failed toggle does not throw and leaves state unchanged
  00:00 +2: TopicPosts.toggleReaction a second tap on the same reaction while the first is in flight is dropped (todo 465)
  00:00 +3: TopicPosts.toggleReaction the guard releases after a failed toggle (todo 465)
  00:00 +4: All tests passed!
  ```

- AC 2: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_010041ec-ccf-2/web && npx vitest run --reporter=verbose src/pages/forum/ThreadDetailPage.test.tsx -t "todo 465" && cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_010041ec-ccf-2/plant_community_mobile && flutter test test/features/forum/providers/forum_providers_test.dart --plain-name "todo 465"` — evidence `.sweep-evidence/g2/465-ac1.txt`, last lines:

  ```text
  Try `flutter pub outdated` for more information.
  00:00 +0: loading /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_010041ec-ccf-2/plant_community_mobile/test/features/forum/providers/forum_providers_test.dart
  00:00 +0: TopicPosts.toggleReaction a second tap on the same reaction while the first is in flight is dropped (todo 465)
  00:00 +1: TopicPosts.toggleReaction the guard releases after a failed toggle (todo 465)
  00:00 +2: All tests passed!
  ```

### 2026-09-30 - Completed by the todo sweep (run 2026-10-01-0121)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-09-30 - Repaired by the todo sweep (run 2026-10-01-0121)

- Review round 1 found `forum_providers.g.dart` stale: `TopicPosts` gained
  `_reactionsInFlight` and `_toggleReactionOnce`, so riverpod_generator's
  `_$topicPostsHash` changed and CI's generated-code gate would fail.
- Regenerated it with build_runner; the only change is the
  `_$topicPostsHash` line. A full unfiltered build afterwards changed no
  other generated file.
- Re-ran both criteria; web and mobile tests pass (evidence in
  `.sweep-evidence/g2/`).
