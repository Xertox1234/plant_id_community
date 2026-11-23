---
status: completed
priority: p3
issue_id: "730"
tags: [forum, api, performance, security, privacy]
dependencies: []
triage: ready
triaged: 2026-11-22
owner_decision: "L2: negative cache only; per-user concurrent-fetch cap not shipped, noted in Work Log (owner 2026-11-22)"
---

# Forum API hardening: six low findings from the 2026-11-21 audit

## Problem

Six low-severity forum API findings were deferred from the 2026-11-21 audit.
Each is small, bounded by an existing throttle or limited in impact, and none
leaks content. They are grouped here instead of filed one per finding, per the
owner's 2026-10-12 decision.

## Findings

All paths are under `backend/`. Source: `docs/audits/2026-11-21-forum-backend.md`.

- **L2:** the link-preview DNS lookups share a small worker pool (`apps/forum_host/link_preview.py:134-151`, `constants.LINK_PREVIEW_DNS_WORKERS`). A lookup that times out keeps its worker busy, so slow lookups can briefly stop previews for every member. This is feature-level only, and the preview and posting throttles bound it.
- **L14:** creating a topic or reply sanitises the body, and so fetches its link previews, before the forum's write-permission check (`packages/wagtail_forum/wagtail_forum/api/views.py:999-1013, 1408-1415`; `api/sanitize.py:501`). Throttles bound it.
- **L15:** the anonymous view-count dedup key uses raw `REMOTE_ADDR` (`api/views.py:1244-1249`). Behind Cloudflare and Railway that is the proxy address (`settings.py:1628-1652`), so anonymous views undercount. This affects analytics only.
- **L17:** accepting an answer checks `live=True` without a lock, then calls `topic.save(...)`. In a narrow race, that save can re-write a pointer the unpublish signal has just cleared (`api/solutions.py:101-109`).
- **L18:** the DM inbox and conversation detail views run `Count("messages", filter=...)` over every message before the cursor LIMIT (`api/direct_messages.py:238-276`). The unread badge already moved to EXISTS for the same reason.
- **L19:** a password-locked forum's row still returns `topic_count`/`post_count`, and the category totals include those counts (`api/views.py:799-811, 826-827`). This is only a finding if the owner's "name and description only" decision is meant to cover counts.

## Recommended Action

1. L2: add a short negative cache for host lookups that time out, and a per-user concurrency cap on preview fetches.
2. L14: resolve the forum and run `_enforce_forum_write` before body sanitising on both paths.
3. L15: key the anonymous dedup on the same resolver as `apps.core.ratelimit.client_ip_key`, exposed through a host hook so the package stays host-agnostic.
4. L17: write the pointer with a conditional `Topic.objects.filter(pk=…, posts__pk=post.pk, posts__live=True).update(...)`.
5. L18: compute `unread_count` with a correlated subquery on the paginated slice.
6. L19: the owner decided counts may not be public (2026-11-22). Zero `topic_count`/`post_count` on a locked row the reader has not unlocked, and sum only the rows the reader can see in the category totals.

## Acceptance Criteria

- [x] L2: a lookup that times out for a host is not retried for that host within the negative-cache TTL (a test).
- [x] L14: a reply to a forum the member may not post in returns 403 without calling the link-preview fetcher (a test).
- [x] L15: two anonymous readers with different client IPs behind the same proxy both count (a test).
- [x] L17: an answer unpublished between the check and the write leaves `solved_post` null (a test).
- [x] L18: the inbox query count and plan do not grow with message history (a query-count test).
- [x] L19: the owner's decision is recorded with its date, and the code matches it.

## Work Log

### 2026-11-21 - Filed from the forum backend audit

- Deferred from `docs/audits/2026-11-21-forum-backend.md` L2, L14, L15, L17, L18 and L19.

### 2026-11-22 - Owner decision on L19

- Asked whether a password-locked forum's topic and post counts may be public, the owner answered "No". The counts are hidden like the forum's contents.

### 2026-11-23 - Implemented by the todo sweep (run 2026-11-22-1957)

- L2 (owner decision 2026-11-22: negative cache only): a host whose lookup ran out the full DNS timeout is not looked up again for 60 s (`backend/apps/forum_host/link_preview.py`). A lookup cut short by a caller's smaller budget, or one that timed out still queued for a worker, is not remembered. The per-user cap on concurrent preview fetches was not shipped.
- L14: topic create and reply resolve the forum and check `post` / `reply` before the body is validated; the body-dependent flags (`poll`, `attach`) are still checked after. A topic create with an invalid body on a missing forum now answers 404 instead of 400.
- L15 and L18: new package setting `WAGTAILFORUM_VIEW_COUNT_CLIENT_RESOLVER` (documented in the package README), which the host points at `apps.core.ratelimit.request_client_id`, the rate limiter's resolver. The inbox `unread_count` is a correlated subquery, so the outer query has no join to messages and no GROUP BY.
- L17: accepting an answer locks the post row, then writes the pointer with a conditional `update()` that requires the post to be a live reply on the topic. A lost race answers 422 and frees the idempotency key. `updated_at` is set by hand because `update()` skips `auto_now`.
- L19 (owner decision 2026-11-22: counts may not be public): a locked forum row reports `topic_count` and `post_count` 0 and adds nothing to its category's totals. The decision is recorded with its date in `backend/packages/wagtail_forum/wagtail_forum/api/views.py`.

### 2026-11-23 - Verified by the todo sweep (run 2026-11-22-1957)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/apps/forum_host/tests/test_link_preview.py::test_a_host_whose_lookup_timed_out_is_not_looked_up_again_within_the_ttl backend/apps/forum_host/tests/test_link_preview.py::test_the_negative_cache_expires_after_its_ttl backend/apps/forum_host/tests/test_link_preview.py::test_a_lookup_that_timed_out_waiting_for_a_worker_is_not_remembered --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/730-ac0.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 3 passed, 3 warnings in 0.64s =========================

  exit code: 0
  ```

- AC 2: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py::test_a_reply_the_member_may_not_post_is_403_before_any_link_is_fetched --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/730-ac1.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 1 passed, 3 warnings in 20.68s ========================

  exit code: 0
  ```

- AC 3: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/apps/forum_host/tests/test_view_count_client_ip.py backend/packages/wagtail_forum/wagtail_forum/tests/api/test_views_count.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/730-ac2.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 6 passed, 3 warnings in 20.73s ========================

  exit code: 0
  ```

- AC 4: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/packages/wagtail_forum/wagtail_forum/tests/api/test_solutions.py::test_an_answer_unpublished_between_the_check_and_the_write_is_not_accepted backend/packages/wagtail_forum/wagtail_forum/tests/api/test_solutions.py::test_accepting_locks_the_answers_row_before_it_writes_the_pointer --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/730-ac3.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 2 passed, 3 warnings in 20.28s ========================

  exit code: 0
  ```

- AC 5: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/packages/wagtail_forum/wagtail_forum/tests/api/test_direct_messages_api.py::test_inbox_query_count_and_shape_do_not_grow_with_message_history --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/730-ac4.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 1 passed, 3 warnings in 20.63s ========================

  exit code: 0
  ```

- AC 6: `/bin/sh -c "grep -n -A4 'Owner decision 2026-11-22' backend/packages/wagtail_forum/wagtail_forum/api/views.py && grep -n -A3 'Owner decision on L19' todos/archive/730-completed-p3-forum-api-hardening-lows.md && python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/packages/wagtail_forum/wagtail_forum/tests/test_forum_passwords.py::test_a_locked_forum_hides_its_counts_and_adds_nothing_to_the_category --create-db -v -p no:cacheprovider"` — evidence `.sweep-evidence/g11/730-ac5.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 1 passed, 3 warnings in 20.84s ========================

  exit code: 0
  ```

### 2026-11-23 - Completed by the todo sweep (run 2026-11-22-1957)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-23 - Repaired by the todo sweep (run 2026-11-22-1957)

- Round-1 review (medium, regression) on L2: while slow lookups held every DNS worker, a healthy host's lookup could leave the queue just before its caller gave up. It had started, so `cancel()` answered False and the host was negative-cached for 60 s in every process sharing the cache.
- Fix in `backend/apps/forum_host/link_preview.py`: the worker stamps when the lookup starts, and a timeout is remembered only when the lookup itself ran the full limit (within `LINK_PREVIEW_DNS_START_GRACE_SECONDS`, new in `backend/apps/forum_host/constants.py`). A lookup that never started, or started late, is not remembered.
- Tests in `backend/apps/forum_host/tests/test_link_preview.py`: new `test_a_lookup_that_started_late_is_not_remembered` (fails against the old `cancel()` check). The existing worker-wait test now fills the pool by counting lookups that really started (`_fill_the_dns_pool`): run with the whole file, a worker still finishing an earlier test's slow lookup made it fail by timing. No assertion was weakened.
