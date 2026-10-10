---
status: pending
priority: p4
issue_id: "539"
tags: [backend, forum, link-previews, follow-ups]
dependencies: []
source_todo: "537"
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

- [ ] Each of findings 1–7 is fixed (with a test where the finding names one), or closed with a dated reason
      in the Work Log.

## Work Log

- 2026-10-10: Promoted out of todo 537 (run 2026-10-10-1537 triage) by owner decision. Line numbers are as of the
  source PR's merge; re-check each finding against main before acting on it.
