---
status: pending
priority: p3
issue_id: "657"
tags: [forum, backend, link-preview]
dependencies: []
triage: ready
triaged: 2026-10-17
---

# The link-line split can refuse a post that saved before it

## Problem

Since todo 655, `validate_forum_body` splits each link-only line into its own
paragraph, then checks `MAX_BODY_BLOCKS` (100) again. A post already near
the cap that contains a link line saves unchanged on the old code, but is
now refused with "Post body has too many blocks." Example: 99 paragraphs plus
one `Intro<br>https://example.com/a<br>Outro`. So such a post can no longer
be edited. Todo 655's criterion 4 asked for exactly this 400. Review round 2
of PR #1150 showed the criterion was wrong: the split must never turn a body
that fits into a refusal.

## Findings

- Found by two reviewers in todo 655's review round 2 (PR #1150). The owner
  merged #1150 as is and filed this follow-up, explicitly waiving the
  P0–P2-only follow-up rule (2026-10-17, "Merge as is + new todo").
- `_split_link_paragraphs` and the second block-cap check are in
  `backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py`. The test
  that pins the 400 is
  `test_655_a_split_past_the_block_cap_is_refused` in
  `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py`.

## Recommended Action

1. Pass the remaining block budget (`MAX_BODY_BLOCKS - len(value)`) into
   `_split_link_paragraphs`. Once splitting a paragraph would exceed it,
   leave that paragraph whole; its link stays an auto-linked line. Never
   raise for a split.
2. Replace todo 655's criterion 4 test: a near-cap body with a link line
   saves (201) and its paragraph stays whole.
3. Optional clean-ups from the same reviews (not blocking):
   - drop blank lines at the start or end of a run next to a split-out link
     (`Intro<br>` / `<br>Outro`), keeping the resave tests stable;
   - make the video/card choice in the split use the same untrimmed token as
     `_sole_video_url`, so `https://youtu.be/x.` doesn't use an embed slot
     and then not embed.

## Acceptance Criteria

- [ ] A body of 99 paragraphs plus `Intro<br>https://example.com/a<br>Outro`
      saves (201) and is stored as 100 blocks with that paragraph whole.
      Pinned by a test that fails on the todo 655 code.
- [ ] No body that fits within `MAX_BODY_BLOCKS` is refused because of the
      split. The old "split past the cap is refused" test is replaced by the
      test above.
- [ ] The todo 655 link-preview and embed tests still pass, along with the
      full backend suite.

## Work Log

### 2026-10-17 - Filed from PR #1150's review round 2

- The owner chose to merge #1150 (todos 655 and 654) as is and track the
  near-cap refusal here.

## Notes

- Also raised in those reviews, for the owner: `SPAM_MAX_LINKS` 3 → 5 also
  applies to DMs, which never show cards. A separate DM limit would be a new
  setting.
