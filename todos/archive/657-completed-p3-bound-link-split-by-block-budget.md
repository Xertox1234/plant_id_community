---
status: completed
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

- [x] A body of 99 paragraphs plus `Intro<br>https://example.com/a<br>Outro`
      saves (201) and is stored as 100 blocks with that paragraph whole.
      Pinned by a test that fails on the todo 655 code.
- [x] No body that fits within `MAX_BODY_BLOCKS` is refused because of the
      split. The old "split past the cap is refused" test is replaced by the
      test above.
- [x] The todo 655 link-preview and embed tests still pass, along with the
      full backend suite.

## Work Log

### 2026-10-17 - Filed from PR #1150's review round 2

- The owner chose to merge #1150 (todos 655 and 654) as is and track the
  near-cap refusal here.

### 2026-10-17 - Implemented by the todo sweep (run 2026-10-18-0439)

- `_split_link_paragraphs` in
  `backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py` takes a
  block budget (default `MAX_BODY_BLOCKS - len(value)`). A paragraph whose
  split would exceed it stays whole, and the card/video slots its links
  took are rolled back so a later link can still use them.
- The second "too many blocks" check after the split is gone: the split can
  no longer grow a body past the cap, so it can never refuse one.
- `test_655_a_split_past_the_block_cap_is_refused` is replaced by three
  todo 657 tests in `test_link_previews.py` (99 + link line saves as 100
  blocks whole; 96 + two link lines splits only the first; the budget and
  slot rollback at unit level). All three fail on the todo 655 code (400s,
  and the unit test's budget argument does not exist there).
- The optional clean-ups (trimming blank lines around a split link, the
  untrimmed-token video check) were not done: not needed for any criterion.

### 2026-10-17 - Verified by the todo sweep (run 2026-10-18-0439)

- AC 1: `bash -c "cd backend && python3 scripts/todos/slot_env.py --main-root . 2 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py::test_657_a_near_cap_body_with_a_link_line_saves_whole --create-db -p no:cacheprovider -v"` — evidence `.sweep-evidence/g2/657-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 3 warnings in 20.00s ========================
  ```

- AC 2: `bash -c "cd backend && ! grep -n test_655_a_split_past_the_block_cap_is_refused backend/packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py && python3 scripts/todos/slot_env.py --main-root . 2 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py -k '657 or 655' --create-db -p no:cacheprovider -v"` — evidence `.sweep-evidence/g2/657-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  =============== 32 passed, 109 deselected, 3 warnings in 21.56s ================
  ```

- AC 3: `bash -c "cd backend && python3 scripts/todos/slot_env.py --main-root . 2 -- backend/venv/bin/python -m pytest --create-db -p no:cacheprovider -q"` — evidence `.sweep-evidence/g2/657-ac2.txt` (not committed), last lines:

  ```text
      self.callHandlers(record)
    File "backend/venv/lib/python3.13/site-packages/sentry_sdk/integrations/logging.py", line 171, in sentry_patched_callhandlers
      return old_callhandlers(self, record)
  Message: '[SHUTDOWN] ThreadPoolExecutor cleanup complete'
  Arguments: ()
  ```

### 2026-10-17 - Completed by the todo sweep (run 2026-10-18-0439)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-17 - Review round 1 (PR #1154): clean, non-blocking findings

- AC 3 evidence: the quoted tail above is shutdown logging. The summary
  line is line 481 of `657-ac2.txt`:
  `5549 passed, 8 skipped, 27 warnings in 411.34s (0:06:51)`. The verifier's
  own re-run gave the same 5549 passed, 8 skipped, exit 0.
- Fixed: the package README still said the block cap is checked again
  after the split. It now says the split adds only what `MAX_BODY_BLOCKS`
  leaves.
- Fixed: added `test_657_editing_a_near_cap_post_to_add_a_link_line_saves`
  (PATCH of a 99-paragraph post plus a link paragraph: 200, 100 blocks).
  It fails with a 400 on the todo 655 `sanitize.py`.
- Declined: putting the post-split `MAX_BODY_BLOCKS` raise back. It can't
  be reached: the cap is checked before the split, and the split adds at
  most `MAX_BODY_BLOCKS - len(value)` blocks, which
  `test_657_split_link_paragraphs_never_exceeds_the_budget` pins. Removing
  it is what the todo asks for.
- Declined: splitting part of a paragraph (the first k link lines) when the
  full split would go over the budget. This only happens within the last
  few blocks of a 100-block body, and there the paragraph saves whole
  instead of the 400 it used to get.

### 2026-10-17 - Review round 2 (PR #1154): clean

- Fixed: the edit test now asserts its 99-paragraph create returned 201
  before it sends the PATCH.
- Declined again: putting a post-split cap check (raise or assert) back.
  The reason is the same as in round 1.

## Notes

- Also raised in those reviews, for the owner: `SPAM_MAX_LINKS` 3 → 5 also
  applies to DMs, which never show cards. A separate DM limit would be a new
  setting.
