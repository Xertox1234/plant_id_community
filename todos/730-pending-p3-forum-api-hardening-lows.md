---
status: pending
priority: p3
issue_id: "730"
tags: [forum, api, performance, security, privacy]
dependencies: []
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
6. L19: ask the owner whether counts are allowed to be public. If not, zero them for locked rows and sum only unlocked rows.

## Acceptance Criteria

- [ ] L2: a lookup that times out for a host is not retried for that host within the negative-cache TTL (a test).
- [ ] L14: a reply to a forum the member may not post in returns 403 without calling the link-preview fetcher (a test).
- [ ] L15: two anonymous readers with different client IPs behind the same proxy both count (a test).
- [ ] L17: an answer unpublished between the check and the write leaves `solved_post` null (a test).
- [ ] L18: the inbox query count and plan do not grow with message history (a query-count test).
- [ ] L19: the owner's decision is recorded with its date, and the code matches it.

## Work Log

### 2026-11-21 - Filed from the forum backend audit

- Deferred from `docs/audits/2026-11-21-forum-backend.md` L2, L14, L15, L17, L18 and L19.
