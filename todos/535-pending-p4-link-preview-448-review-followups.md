---
status: pending
priority: p4
issue_id: "535"
tags: [forum, backend, link-preview, review-follow-up, testing]
dependencies: []
---

# Link preview: non-blocking findings from todo 448's review (PR #971)

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

## Acceptance Criteria

- [ ] Items 1–3 are fixed or closed with a reason.

## Work Log

### 2026-10-09 - Filed from PR #971 review round 1
