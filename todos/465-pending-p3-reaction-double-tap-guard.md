---
status: pending
priority: p3
issue_id: "465"
tags: [web, mobile, forum, bug]
dependencies: []
source_review: "todos/archive/394-completed-p3-triage-the-grandfathered-archived-todos.md"
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

- [ ] Web and mobile ignore a reaction tap on a post while that post's
      toggle is in flight, for the same reaction type.
- [ ] A test on each client fires two taps before the first resolves and
      asserts one request.
