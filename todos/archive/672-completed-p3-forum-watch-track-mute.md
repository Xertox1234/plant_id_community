---
status: completed
priority: p3
issue_id: "672"
tags: [forum, forum-categories, backend, web, notifications]
dependencies: ["665"]
triage: ready
triaged: 2026-11-01
blocked_on: "The owner needs to define the levels and the delivery channels for a new-topic notification."
owner_decision: "Discourse four levels: watching = every post (auto-subscribe each new topic), watching_first_post = new topics only, tracking = unread counts only, muted = hidden from Recent. New-topic alerts go to in-app + push, following the existing notification preference matrix; no new email. (owner, 2026-10-30) Tracking: store and select the level AND show per-forum unread badges on forum rows, built on the per-forum read markers from #1226 (todo 671). (owner, 2026-10-31) New-topic alert gets its OWN new_topic row in the push/in-app preference matrix (push on, in-app on, email off; also shown on the mobile settings card), not the reply row. A tracked forum's badge shows an unread COUNT, not just the has_unread dot. (owner, 2026-11-01)"
---

# Forum categories slice 8: Watch / Track / Mute per forum

## Problem

Discourse lets a member watch, track or mute a category; phpBB lets members subscribe to a forum. We only have per-topic subscriptions.

## Findings

- Exists: topic-level `TopicSubscription` — `backend/packages/wagtail_forum/wagtail_forum/models/subscriptions.py:13`.
- Notification fan-out and digest: `notifications.py`, `digest.py`.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Model `ForumSubscription(user, forum, level)` with levels watching (notify on every new topic), watching_first_post, muted.
2. New-topic notifications fan out to forum watchers (respecting blocks/mutes, quiet hours and preferences); muted forums are excluded from the digest and the recent-topics feed for that user.
3. Web: a level picker on the forum page.

## Technical Details

- `models/subscriptions.py`, `notifications.py`, `digest.py`, recent-topics view in `api/views.py`.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: a watcher gets one notification per new topic; the author does not notify themselves.
- [x] Test: a muted forum's topics are absent from that user's digest and recent feed.
- [x] Test: fan-out query count is bounded.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Discourse four levels: watching = every post (auto-subscribe each new topic), watching_first_post = new topics only, tracking = unread counts only, muted = hidden from Recent. New-topic alerts go to in-app + push, following the existing notification preference matrix; no new email.

### 2026-10-31 - owner decision

- Owner answered the re-triage question: tracking is stored and selectable and also shows per-forum unread badges.

### 2026-11-01 - Implemented by the todo sweep (run 2026-11-01-0035)

- `ForumSubscription(user, forum, level)` with Discourse's four levels (migration 0051) and `GET/PUT/DELETE /forum/boards/{slug}/subscription/` (throttled in the host as `forum_subscription_update`).
- New-topic fan-out in `apps/forum_host/notifications.py` (`topic_created`): watchers at `watching` and `watching_first_post`, minus the author, readers the forum's grants exclude, blocked/muted pairs and anyone already mentioned or quoted, get one `new_topic` bell row and one push batch; `watching` members are also subscribed to the topic in one insert. Five queries whatever the watcher count.
- `new_topic` has its own preference row (owner decision 2026-11-01): push on, no email cell; copy in `notification_copy.py`, shown in web Settings, the bell and the mobile settings card and notification list (a small Flutter change the owner decision asks for, despite the todo's "web only").
- Muted forums are left out of that member's `/forum/topics/recent/` and digest (both sections). Forum rows carry `watch_level` and, for tracked or watched forums, `unread_count` (correlated subqueries, no added query); the web shows the count as a badge in place of the unread dot, and a level picker on the forum page.
- Two `test_notification_preferences.py` literals gained the `new_topic` row; the matrix change is the owner's.

### 2026-11-01 - Verified by the todo sweep (run 2026-11-01-0035)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/forum_host/tests/test_new_topic_fanout.py::test_a_watcher_gets_one_notification_per_new_topic_and_the_author_none apps/forum_host/tests/test_new_topic_fanout.py::test_watchers_who_cannot_read_or_are_blocked_are_skipped --create-db` — evidence `.sweep-evidence/g1/672-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 2 passed, 2 warnings in 20.42s ========================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_subscriptions.py::test_a_muted_forums_topics_are_absent_from_that_members_digest_and_recent_feed --create-db` — evidence `.sweep-evidence/g1/672-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 3 warnings in 20.06s ========================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/forum_host/tests/test_new_topic_fanout.py::test_fan_out_query_count_is_bounded --create-db` — evidence `.sweep-evidence/g1/672-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 2 warnings in 20.26s ========================
  ```

### 2026-11-01 - Completed by the todo sweep (run 2026-11-01-0035)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-01 - Review round 1: non-blocking findings

Round 1 (PR #1232) was clean, with no blocking findings. Each non-blocking finding is fixed by hand with a test, or declined with a reason:

- **Fixed** (medium) `apps/forum_host/notifications.py`: a `watching` member mentioned or quoted in the opening post got the mention but no TopicSubscription. Every watcher is now subscribed; the mention or quote replaces only the new_topic alert. Test: `test_a_watcher_mentioned_in_the_opening_post_still_follows_the_topic`, mutation-checked.
- **Fixed** (medium) `apps/forum_host/pacing.py`: `new_topic` was missing from `PACED_EVENTS`, so quiet hours did not hold it. Test: `test_a_new_topic_push_is_held_by_quiet_hours`, which failed before the fix.
- **Fixed** (low) `apps/forum_host/eligibility.py`: the send-time recheck now drops a held `new_topic` push for a member who no longer watches the forum. This matters now that quiet hours hold it for hours. Test: `test_a_held_new_topic_push_is_dropped_once_the_watcher_mutes_the_forum`, mutation-checked.
- **Fixed** (medium) the `forum_subscription_update` throttle had no 429 test. Test: `test_a_forum_watch_level_change_is_throttled[put|delete]`; removing the DELETE decorator fails it.
- **Fixed** (low) the watch-level PUT/DELETE schema now documents 429.
