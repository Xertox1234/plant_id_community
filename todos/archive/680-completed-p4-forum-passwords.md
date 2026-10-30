---
status: completed
priority: p4
issue_id: "680"
tags: [forum, forum-categories, backend, web, security]
dependencies: ["676"]
triage: ready
triaged: 2026-10-30
owner_decision: "Locked (password) forums are hidden from the Flutter app until it gets an unlock UI. (owner, 2026-10-30)"
---

# Forum categories slice 14: password-protected forums

## Problem

phpBB can protect a forum with a password, unlocked per session. phpBB's own ACP recommends permissions instead; the owner wants parity.

## Findings

- `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (forums_access per session; last-post subject hidden while locked).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Field `password_hash` (Django hasher); unlock endpoint stores the unlocked forum id in the session (rate-limited, 429 on abuse).
2. While locked: forum row visible with a lock, topics/last-post subject hidden, search/digest/notifications exclude it for that user.
3. Staff and forum moderators bypass.

## Technical Details

- Hooks into the `visible_forums(user)` helper from slice 11b; rate limiting per `backend/docs/patterns/architecture/rate-limiting.md`.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: locked forum hides topics until unlocked; wrong password counts toward the rate limit and returns 429 when exceeded.
- [x] Test: unlock lasts for the session only.
- [x] Test: search, digest and notifications exclude a locked forum.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Locked (password) forums are hidden from the Flutter app until it gets an unlock UI.

### 2026-10-30 - Implemented by the todo sweep (run 2026-10-30-1108)

- `Forum.password_hash` (Django hasher) set through a write-only password field on the General tab, with a remove checkbox.
- `POST /forum/boards/{slug}/unlock/` (signed-in members only, so no anonymous edge-cached page carries an unlock) stores the forum id in the session with the member's id; wrong passwords are counted per member per forum and answer 429 past `WAGTAILFORUM_FORUM_UNLOCK_MAX_FAILURES`; the host adds a `forum_unlock` throttle.
- Locked: the categories row shows `is_locked` with no last-post time or unread mark, the topic list is 403 `forum_locked`, topics 404, and search, digest and notifications leave it out. `/forum/boards/` (Flutter) omits locked forums (owner decision). Staff and moderators bypass.
- Web: lock badge on `ForumCard`, and `ThreadListPage` shows `ForumUnlockForm` for a locked forum.
- Tests: `tests/test_forum_passwords.py`.

### 2026-10-30 - Verified by the todo sweep (run 2026-10-30-1108)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_passwords.py::test_a_locked_forum_hides_its_topics_until_unlocked packages/wagtail_forum/wagtail_forum/tests/test_forum_passwords.py::test_wrong_passwords_count_toward_the_limit_and_return_429 --create-db` — evidence `.sweep-evidence/g1/680-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 2 passed, 3 warnings in 21.52s ========================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_passwords.py::test_the_unlock_lasts_for_the_session_only --create-db` — evidence `.sweep-evidence/g1/680-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 3 warnings in 20.18s ========================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_passwords.py::test_search_digest_and_notifications_exclude_a_locked_forum --create-db` — evidence `.sweep-evidence/g1/680-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 3 warnings in 20.41s ========================
  ```

### 2026-10-30 - Completed by the todo sweep (run 2026-10-30-1108)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-30 - Repaired by the todo sweep (run 2026-10-30-1108)

- Round-1 review: `Forum.password_hash` (added by 0047) now has `db_default=""` in the model and the migration, so the previous release can insert forums while this one migrates.
- No behaviour change to forum passwords; every criterion was re-run.

### 2026-10-30 - Review round 1: non-blocking findings (hand fixes)

- Fixed (medium): a stored unlock was only {user, forum ids}, so a new password (a leaked one rotated) did not re-lock sessions that had unlocked the old one. Each unlock now stores an HMAC of the forum's `password_hash` (sha256 `salted_hmac`; the session never holds the hash), and `unlocked_forum_ids` accepts it only while the hash is unchanged. Test: `test_a_new_password_relocks_every_session_that_unlocked_the_old_one`. Mutation-checked.
- Fixed (medium): the web locked-forum flow had no tests. New tests: `ThreadListPage.test.tsx` (an unlock form instead of threads, never fetching them; after the unlock it re-reads the forum and lists its threads) and `ForumUnlockForm.test.tsx` (the 400/429/401/403/500 messages, and an empty password is not sent). Mutation-checked on the `is_locked` early return and the cache reset.

### 2026-10-30 - Review round 2: non-blocking findings (hand fixes)

Round 2 came back clean (nothing blocking, nothing refuted).
- Fixed (medium, raised twice): the quote check (write) and the quote map (read) used the guest-or-user view with no request. A member who had unlocked a password forum got a 400 when quoting a post there, and quotes in it read `available: false`. `visible_quoted_posts`, `resolve_quotable_posts`, `validate_forum_body` and `build_forum_quote_map` now take `request`.
- Fixed (low, raised twice): the Saved list did the same, so a bookmark saved in an unlocked forum never appeared in it. It now passes `request`. Test for both: `test_a_member_who_unlocked_the_forum_may_quote_and_bookmark_in_it`. Write, read and list were each mutation-checked.
- Fixed (low): a locked row on `/forum/categories/` (possibly the cached guest response) still carried the forum's topic template. It is now blanked with `last_post_at` and `has_unread`. Covered in `test_a_locked_forum_hides_its_topics_until_unlocked`. Mutation-checked.
- Fixed (low): an unlock body had no length cap, so every attempt hashed whatever was sent. `FORUM_PASSWORD_MAX_LENGTH` (128) now caps both the admin field and the unlock serializer. Test: `test_an_overlong_password_is_refused_before_it_is_hashed`. Mutation-checked.
- Fixed (low): the admin offered a password on category and link rows. A category ignores it, and a link with one could never be unlocked. `ForumAdminForm.clean` now refuses it. Test: `test_a_link_cannot_be_given_a_password`. Mutation-checked.
- Declined (low): the wrong-password cap is check-then-increment, so parallel requests can try a few more passwords than the limit. It is still bounded by the host's 20/min `forum_unlock` throttle. P3.
- Declined (low): the web shows "Sign in to open this forum." for any 403, including a signed-in reader's rarer CSRF or permission 403. That is a wording issue, not a behaviour one. P4.
