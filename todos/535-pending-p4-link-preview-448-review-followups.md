---
status: pending
priority: p4
issue_id: "535"
tags: [forum, backend, link-preview, review-follow-up, testing]
dependencies: []
triage: ready
triaged: 2026-10-10
owner_decision: "Item 2: measure the 100k cap with a tolerance for server-added markup (e.g. target=_blank/rel), so a near-cap post stays editable (2026-10-10)"
---

# Link preview: non-blocking findings from todo 448's reviews (PRs #971, #972)

Filed from PR #971's round-1 review (todo 448, PR 1 of 2). The round's one
blocking finding was fixed in that PR: a stored card whose URL ends in
punctuation now survives an edit. The findings below did not block it.

## Findings

1. **The stored-size re-check runs after the card fetch.**
   - Where: `validate_forum_body` in
     `backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py`. Item 4's
     re-check of `MAX_BODY_CHARS` runs on the cleaned body, after
     `_convert_link_previews`.
   - Effect: a body refused there has already paid for its page fetches. Any
     preview image those fetches stored stays unreferenced until the nightly
     prune deletes it after its 24 h grace period. This contradicts the
     comment "cards last, so a refused body never costs a fetch".
   - Only a body within a few hundred characters of 100k can reach this.
   - Possible fix: check the auto-linked size before the card conversion,
     and allow the bounded card growth (5 cards × the stored field caps)
     separately.
2. **An existing near-cap post can stop accepting edits.**
   - Every body `<a>` now gains `target="_blank"` (16 characters) when
     re-cleaned. A post stored just under 100k characters with many links can
     therefore go over the cap when resent unchanged, and every edit is then
     refused.
   - No real posts exist yet: only the owner and test accounts. Decide
     whether to measure the cap with a tolerance for server-added markup.
3. **`test_bookmarks_list_query_count_is_pinned` is flaky locally.**
   - Where: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_bookmarks_api.py`.
   - Run alone, it fails with `assert 3 == 4`: it sees one query fewer than
     pinned. It fails 4 of 4 runs on a tree without PR #971's changes, and
     passes inside the full suite.
   - Hypothesis, not verified: a cache that persists in the local Redis
     across runs (for example a page view-restriction lookup) is already
     warm. CI's Redis starts empty.
   - Fix: clear the relevant cache in the test, or pin the count with the
     cache cold.

4. **(PR #972) A deadline failure on a redirect is cached as "redirect refused".**
   - Where: `apps/forum_host/link_preview.py::_fetch_html`. The redirect's
     `_target_for_url` gets a DNS timeout capped at the time left. With
     almost no time left, the lookup times out, raises `InvalidPreviewURL`,
     and becomes `_FetchFailed("redirect refused")`, not `deadline`, so the
     failure is cached for 60 s.
   - Fix: in that `except`, check `time.monotonic() >= deadline` (as the
     `OSError` branch does) and raise `_DEADLINE`.
5. **(PR #972) The composer never caches a deadline failure.**
   - The "our budget ran out" reasoning is true only for snapshots. The
     composer's 8 s budget is fixed, so its deadline failure means the site
     was slow.
   - A site that drips a byte a second is fetched again on every composer
     request, each holding a worker for about 8 s. Only the per-user
     throttle bounds it.
   - Fix: skip caching a deadline failure only when the caller passed a
     deadline.
6. **(PR #972) An HTTPS fetch can overrun its deadline by up to the connect timeout.**
   - The TCP connect and the TLS handshake are each bounded by
     `min(4, remaining)`, and the watchdog starts only after both. So the
     worst case is about the deadline plus the time that was left when
     connecting.
   - `_fetch_image` has the same shape. A fix would start the watchdog
     before `connect()` (it needs the socket), or wrap the socket ourselves.
7. **(PR #972) `_host_of` logs the host of a URL that failed validation.**
   - `urlsplit` strips only `\t\r\n`, so the host of a rejected URL can
     carry control characters and has no length cap: minor log injection.
   - Fix: `repr()` and truncate it.
8. **(PR #972) Pre-existing: some link-preview logs still name the full URL.**
   - `link_preview_snapshot`'s image warning, `_cache_preview_image`'s info
     lines, and the package's `fetch_snapshots`/`_log_late` log full URLs,
     path and query included.
   - Fix: log the host only, as todo 448 item 12 does.

## Acceptance Criteria

- [ ] Items 1–8 are fixed or closed with a reason.

## Work Log

### 2026-10-09 - Filed from PR #971 review round 1

### 2026-10-09 - Items 4–8 added from PR #972 review round 1
