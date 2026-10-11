---
status: pending
priority: p4
issue_id: "579"
tags: [forum, backend, moderation, needs-design]
dependencies: []
owner_decision: "An edit to a never-published opening post is re-screened through _route_revision_by_trust (2026-09-28, reconfirmed 2026-10-10); for a never-published post the re-screen only screens and never publishes, and the moderator's topic approval stays the gate that publishes it (2026-10-10) Mechanism: start the spam workflow, and for a never-published post stop SpamCheckTask's approve from publishing; topic approval stays the gate. Paths: the author's API edit and the admin edit both reach a pending opening post (open the API edit path), screened the same way. Restricted to first_published_at is None (2026-10-11)"
triage: needs-design
triaged: 2026-10-11
blocked_on: "A chosen mechanism for a non-publishing screen, and a choice of which edit path (API, admin, or both) must reach a pending opening post."
---

# Re-screen edits to a never-published opening post without publishing it

## Problem

Todo 471 (PR #1013) recorded the owner's decision but built only its documentation. Its worker found that
`submit_edit_for_moderation` (`backend/packages/wagtail_forum/wagtail_forum/workflow.py`) routes through
`_route_revision_by_trust` only when the post is live. The spam workflow that route starts publishes clean
content when it finishes, so "screen but never publish" cannot be had by just dropping the live check: for a
trusted author, publishing the post also publishes its still-pending topic and skips the moderator's approval.

## Recommended Action

Design how a never-published post's edit is screened without publishing it. For example, run the spam
screen and record or flag its verdict on the revision, leaving publication to topic approval. Then build it,
restricted to posts with `first_published_at is None` so a taken-down post is never resurrected.

## Acceptance Criteria

- [ ] An edit to a never-published opening post is screened (the spam/trust checks run on the edited body),
      proven by a test that a spammy edit is caught.
- [ ] That screen never publishes the post or its topic, for a trusted or untrusted author alike, proven by a
      test that the topic stays pending until the moderator approves it.
- [ ] A taken-down post (`first_published_at` set, not live) is not re-published by the change.
- [ ] `backend/docs/patterns/domain/forum.md` describes the screen as built, replacing the decision-only note.

## Work Log
