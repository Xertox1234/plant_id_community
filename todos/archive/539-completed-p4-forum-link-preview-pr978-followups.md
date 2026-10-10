---
status: completed
priority: p4
issue_id: "539"
tags: [backend, forum, link-previews, follow-ups]
dependencies: []
source_todo: "537"
triage: ready
triaged: 2026-10-10
---

# Forum link previews: follow-ups from PR #978 (todo 535)

## Problem

PR #978 shipped link-preview follow-ups. Its review rounds reported seven non-blocking findings, which todo 537
parked. The owner promoted them here on 2026-10-10.

## Findings

1. **`backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py:377/820`** (low, perf). `_stored_without_cards`
   runs `autolink_rich_text` on every rich-text block before the fetch, and the cleaned loop repeats it. With the
   200k raw ceiling, worst-case sanitize CPU per write rises roughly 2–4x. Suggested: autolink once and reuse.
2. **`sanitize.py:590/826`** (low). The pre-fetch check measures a resent card as an auto-linked paragraph, not as
   its URL. A near-cap body stored under the old rule, or whose card came from a bare-URL paragraph (mobile sends
   no `<p>`), can 400 when resent unchanged. Suggested: measure resent cards as their URL in the pre-fetch check.
3. **`sanitize.py:562/827`** (low). The "a refused body costs no fetch" claim has two holes. Legacy bare-PK image
   normalisation is not applied in `_stored_without_cards`. Video oEmbed `warm_embeds` runs before the pre-fetch
   check. Suggested: normalise images there, and move the check before the embed conversion.
4. **`sanitize.py:511` `_ANCHOR_START_TAG`** (low, unverified). The pattern ends at the first `>`, so a raw `>` in an
   href (if nh3 leaves one) skips the target/rel discount. Suggested: use an attribute-aware pattern and add a test.
5. **`backend/apps/forum_host/link_preview.py:463`** (low). Any `InvalidPreviewURL` on a redirect hop is relabelled
   `deadline` once the deadline has passed, including a private-IP or bad-port refusal whose lookup finished late.
   It then goes uncached. Suggested: flag the timed-out lookup itself rather than checking the clock.
6. **`backend/packages/wagtail_forum/wagtail_forum/link_previews.py:731` `log_host`** (low). A printable host with
   spaces or `=` passes through unquoted, so a rejected URL can fake `key=value` text in a log line. Suggested:
   pass a host through unquoted only when it matches a hostname/IP charset, and `repr()` it otherwise.
7. **Timing tests** (medium, flake risk). `test_link_preview.py:361` and `test_link_preview_images.py:477` use real
   sleeps against `elapsed < 0.9`, with ~0.1–0.3 s of slack. `test_link_previews.py:932` depends on thread
   scheduling. `test_link_preview.py:335` imports the private `_loopback_drip` from a sibling test module.
   Suggested: widen the margins or assert the socket timeout passed, use an Event handshake, and move the helper to
   a conftest.

## Acceptance Criteria

- [x] Each of findings 1–7 is fixed (with a test where the finding names one), or closed with a dated reason
      in the Work Log.

## Work Log

- 2026-10-10: Promoted out of todo 537 (run 2026-10-10-1537 triage) by owner decision. Line numbers are as of the
  source PR's merge; re-check each finding against main before acting on it.

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-10-2307)

- Items 1-3 (`sanitize.py`): auto-link is memoised per write and shared by the pre-fetch check and the cleaned
  pass. The card plan (`_card_plan`) is computed once, and a block that will be a REUSED stored card is measured
  as its URL before the fetch. Bare-PK images are normalised in that check. `warm_embeds` now runs after it. The
  embed conversion stays before the check, because moving the check above it would refuse near-cap video posts
  that save today. A web-shape resend (`<p><a>`) is still refused by the raw-size check, which is out of scope.
- Item 4: confirmed that nh3 keeps a raw `>`/`<` in a quoted attribute. `_ANCHOR_START_TAG` is now quote-aware
  and linear. The old pattern was quadratic on raw input, about 4 s for 200k characters of `<a `.
- Items 5-6: the resolver raises `_LookupTimedOut`, and only that becomes `deadline` (or `timeout`). A late
  refusal stays `redirect refused` and is cached. `log_host` logs a host bare only when it is in `[a-z0-9._:%-]`.
- Item 7: the slow-connect tests assert the handshake timeout handed to the socket. The pool tests wait on an
  Event before the window opens. `_loopback_drip` is now the `loopback_drip` fixture in
  `apps/forum_host/tests/conftest.py`. The item-4 redirect test now raises `_LookupTimedOut`.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-10-2307)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py 3 -- backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py apps/forum_host/tests/test_link_preview.py apps/forum_host/tests/test_link_preview_images.py --create-db -p no:cacheprovider -rA` — evidence `.sweep-evidence/g3/539-ac0.txt` (not committed), last lines:

  ```text
  PASSED apps/forum_host/tests/test_link_preview_images.py::test_a_racing_duplicate_is_dropped_for_the_canonical_name[False]
  PASSED apps/forum_host/tests/test_link_preview_images.py::test_item8_no_time_left_for_an_image_logs_the_host_only
  PASSED apps/forum_host/tests/test_link_preview_images.py::test_item8_an_image_not_downloaded_logs_the_host_only
  PASSED apps/forum_host/tests/test_link_preview_images.py::test_item6_an_image_after_a_slow_connect_ends_at_the_deadline
  ======================= 180 passed, 3 warnings in 27.71s =======================
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-10-2307)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
