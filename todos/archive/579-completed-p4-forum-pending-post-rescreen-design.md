---
status: completed
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

- [x] An edit to a never-published opening post is screened (the spam/trust checks run on the edited body),
      proven by a test that a spammy edit is caught.
- [x] That screen never publishes the post or its topic, for a trusted or untrusted author alike, proven by a
      test that the topic stays pending until the moderator approves it.
- [x] A taken-down post (`first_published_at` set, not live) is not re-published by the change.
- [x] `backend/docs/patterns/domain/forum.md` describes the screen as built, replacing the decision-only note.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- Mechanism (owner decision): `submit_edit_for_moderation` sends an edit to a never-published opening post through `_route_revision_by_trust` with trust off, inside `screen_without_publishing()`; `SpamCheckTask` approves a clean verdict but replaces the workflow state's finish action for that run, so nothing is published, and a flagged one is held in NEEDS_CHANGES. A later screen of a post screened before (the admin's Resubmit) is screen-only too; the create path's first screen still publishes.
- Paths: `PostWriteView._get_patchable` lets the author PATCH their own never-published opening post under its never-published topic (anyone else still gets 404, DELETE is not opened), and an `after_edit_snippet` hook screens a plain admin "Save draft" the same way.
- Restricted to `first_published_at is None` (`workflow.screens_without_publishing`): a taken-down post's edit stays an unscreened draft revision.
- Tests in `backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py` (trusted and untrusted, API, admin, Resubmit, taken-down, create path); `forum.md` describes the screen as built.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py -k 'spammy_edit_to_a_pending_opening_post or admin_draft_of_a_pending_opening_post or patch_their_pending_opening_post' --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g2/579-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 3 passed, 31 deselected, 3 warnings in 17.37s =================
  ```

- AC 2: `cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py -k 'clean_edit_to_a_pending_opening_post_never_publishes or resubmitting_a_held_opening_post or patch_their_pending_opening_post or first_screen_of_a_new_opening_post' --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g2/579-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 5 passed, 29 deselected, 3 warnings in 17.70s =================
  ```

- AC 3: `cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py -k 'taken_down_opening_post_is_never_republished or opening_post_under_a_taken_down_topic' --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g2/579-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 2 passed, 32 deselected, 3 warnings in 17.32s =================
  ```

- AC 4: `grep -n -A44 'Re-screening an edit to a pending opening post (todo 579)' backend/docs/patterns/domain/forum.md` — evidence `.sweep-evidence/g2/579-ac3.txt` (not committed), last lines:

  ```text
  1146-
  1147-1. **List the storage prefix first**, then read references. Anything committed
  1148-   before the reference scan is seen.
  1149-2. **References are every body that can still be shown:** every row (no `live`
  1150-   filter) and every Wagtail revision. A revision stores the StreamField as a
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
