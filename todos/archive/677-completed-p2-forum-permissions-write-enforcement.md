---
status: completed
priority: p2
issue_id: "677"
tags: [forum, forum-categories, backend, web, permissions, security]
dependencies: ["676"]
triage: ready
triaged: 2026-11-01
owner_decision: "Enforce f_attach both ways: reject image blocks in post bodies for principals without f_attach, AND accept a forum id on image upload that is checked against f_attach. (owner, 2026-10-31) forum_id on POST /forum/images/ is OPTIONAL: checked against f_attach when sent; when absent the upload is accepted and the body image-block check still enforces f_attach. The Identify upload and shipped Flutter builds keep working. (owner, 2026-11-01)"
---

# Forum categories slice 11c: enforce post/reply/poll/attach permissions and reflect them in the web UI

## Problem

Write permissions per forum (phpBB f_post, f_reply, f_poll, f_attach) must be enforced on every write path and reflected in the UI.

## Findings

- Write paths: topic create (`api/views.py` `_create_topic`), post create, poll create (`api/polls.py`), image upload (`api/image_management.py`).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Enforce each flag server-side (403 with a stable error code when the forum is visible but the action is not allowed).
2. API returns the viewer's capabilities per forum (`can_post`, `can_reply`, `can_poll`, `can_attach`).
3. Web hides/disables the composer, reply box, poll and attachment controls accordingly.

## Technical Details

- `api/views.py`, `api/polls.py`, `api/image_management.py`, web composer components.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test per flag: denied returns 403 with the error code; allowed succeeds.
- [x] Web Vitest: controls hidden/disabled from capabilities.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-31 - owner decision

- Owner answered the re-triage question: enforce f_attach both ways (reject image blocks in the body and require a checked forum id on upload).

### 2026-11-01 - Implemented by the todo sweep (run 2026-11-01-0035)

- Write flags enforced (`api/views.py` `_enforce_forum_write`): topic create needs `post` (+ `poll` with a poll, `attach` with an image block), a reply needs `reply` (+ `attach`), an edit that adds an image needs `attach`; each refusal is 403 `forum_post_denied` / `forum_reply_denied` / `forum_poll_denied` / `forum_attach_denied` (`api/exceptions.py`). Hidden forums stay 404.
- `POST /forum/images/` takes an optional `forum_id` (owner decision 2026-11-01): checked against `attach` when sent (403, or 404 for a forum the caller cannot see); absent, the upload is accepted as before, so the Identify upload and shipped Flutter builds keep working.
- Forum rows of `/forum/categories/` carry `can_post`, `can_reply`, `can_poll`, `can_attach` as SQL annotations (`services/forum_permissions.capability_annotations`), so the endpoint adds no query. Web: the composer link, reply box, poll section and TipTap image controls hide from those flags; uploads send the forum id.
- Product consequence for the owner: the members' no-grant default is *Standard*, which has no `poll` (675 matrix). After this lands, on every forum without an explicit members grant only staff can add polls (the web hides "Add a poll"). Remedy: grant *Standard + polls* per forum, or an owner call to change the default. `tests/api/test_polls_api.py` now grants *Standard + polls* on the boards whose tests create polls.

### 2026-11-01 - Verified by the todo sweep (run 2026-11-01-0035)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_write_permissions.py --create-db` — evidence `.sweep-evidence/g1/677-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 9 passed, 3 warnings in 24.99s ========================
  ```

- AC 2: `cd web && npx vitest run src/components/forum/TipTapEditor.test.tsx src/pages/forum/ThreadListPage.test.tsx src/pages/forum/ThreadDetailPage.test.tsx src/pages/forum/NewThreadPage.test.tsx` — evidence `.sweep-evidence/g1/677-ac1.txt` (not committed), last lines:

  ```text

   Test Files  4 passed (4)
        Tests  254 passed (254)
     Start at  19:52:33
     Duration  4.75s (transform 1.05s, setup 503ms, import 3.29s, tests 9.33s, environment 2.29s)
  ```

### 2026-11-01 - Completed by the todo sweep (run 2026-11-01-0035)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-01 - owner decision: members' poll default

- The worker flagged that the members' no-grant default (*Standard*, no `poll`) would make every ungranted forum staff-only for polls once this todo enforced the flag, which contradicts 675's "existing forums keep working with no setup". The owner chose to make the fallback *Standard + polls* (2026-11-01). `DEFAULT_ROLES[MEMBERS]` is now `STANDARD_POLLS`; an explicit *Standard* grant still has no `poll`. Tests: `test_a_forum_with_no_grant_is_standard_polls_for_members_and_read_only_for_guests`, `test_an_explicit_standard_grant_still_has_no_poll`, `test_a_member_adds_a_poll_on_a_board_with_no_grant`. A mutation back to `STANDARD` fails 3 tests. wagtail_forum + forum_host: 2518 passed.

### 2026-11-01 - Review round 1: non-blocking findings

Round 1 (PR #1232) was clean, with no blocking findings. Each non-blocking finding is fixed by hand with a test, or declined with a reason:

- **Fixed** (medium) `api/views.py` topic create: an `identification.image_id` photo skipped `attach`. It now needs `attach` like an image block. Test: `test_attach_denied_for_an_identification_photo_without_the_attach_flag`. A mutation removing the check fails it.
- **Fixed** (low ×2) the upload `forum_id` check applied the closed rule, while an edit in a closed forum may still add an image. The upload now checks `attach` only. Test: `test_upload_to_a_closed_forum_checks_attach_only`, mutation-checked.
- **Declined** (low, same finding) the web hides image/alt-text controls in a closed forum because `can_attach` folds in the closed rule. Only staff and moderators post there, and the server still accepts an edit, so this is a UI nicety, not a wrong result.
