---
status: pending
priority: p2
issue_id: "448"
tags: [forum, backend, link-preview, review-follow-up]
dependencies: ["428"]
---

# Link preview slice A: non-blocking review findings

Filed from todo 428 slice A's review round 1 (bundled `/code-review` plus
`code-review-orchestrator`, 2026-09-25). Neither reviewer found a blocking
issue. Items 1–3 are **latent** while `WAGTAILFORUM_LINK_PREVIEW_FETCHER` is
unset. **Fix them before slice C turns the fetcher on.** Item 4 is live now
but rare.

## Findings

1. **The fetch queue can back up (gate for slice C).**
   - Where: `wagtail_forum/link_previews.py::fetch_snapshots`.
   - Futures still queued when the window closes are never cancelled. The
     pool is 8 threads with an unbounded queue, and one host fetch can
     take well over 5 s (2 s DNS plus 4 s per request, up to 4 requests).
   - A burst of posts with 5 slow links each fills the pool. Later posts'
     fetches then time out before they start, so their links save as plain
     links while the backlog lasts.
   - Fix: `future.cancel()` for pending futures that have not started, and/or
     a bounded submit.
2. **A code sample posted on its own becomes a card (gate for slice C).**
   - Where: `api/sanitize.py::_sole_url`.
   - It strips all markup, so `<p><code>https://api.example.com/v1/x</code></p>`
     counts as a link on its own, is fetched and is replaced by a card. The
     auto-linker deliberately skips `<code>`; the card path should too.
3. **Moderator save can fail on a card (gate for slice C).**
   - Where: the `LinkPreviewBlock.url` field versus `is_card_url`.
   - `is_card_url` accepts hosts that the block's `URLBlock` (Django
     `URLValidator`) rejects, for example `https://my_site.example.com/`. The
     API only runs `to_python`, so such a card saves. After that, a moderator's
     `/cms/` save of the post fails with "Enter a valid URL" on a block they
     never touched.
   - Fix: make `url` a `CharBlock`, or run `URLValidator` inside
     `is_card_url`.
4. **Auto-linking can push a body over `MAX_BODY_CHARS` (live, low).**
   - Where: `api/sanitize.py`. The 100k check runs before auto-linking,
     which adds about 50 characters per bare URL.
   - A body near the limit with many bare URLs stores at more than 100k.
     Resending it unchanged on edit is then refused as "Post body is too
     large".
   - Fix: re-check the size after auto-linking and refuse on create, or check
     the pre-link size on edit.
5. **A slow-dripping origin can hold a pool thread (pre-existing, PR #709).**
   - Where: `apps/forum_host/link_preview.py`. `timeout=4` is per `recv`,
     not a wall clock, so an origin dripping bytes can hold a thread for a
     long time while it reads up to 512 KB.
   - Slice A's bounded pool contains the damage. A wall-clock deadline in
     `_read_document` would remove it.
6. **A stored image name is carried without validation (cosmetic).**
   - Where: `link_preview_snapshots`, which carries the stored `image`
     unchecked. The read envelope gates it, so nothing is served.
   - Validate it there too for symmetry.
7. **A sole link with trailing punctuation (cosmetic).**
   - `https://example.com.` as a paragraph's only content becomes a card
     candidate with the dot kept. `_trim_url` could apply before the card
     check.

8. **`test_spam.py` fails when run on its own (pre-existing).**
   - Where: `test_spam.py`. Its non-DB tests call `get_setting`, and the
     host override provider (`apps/forum_host/forum_settings.py::_load_values`)
     reads the DB whenever its cached values are cold.
   - Run alone with a cold cache, 10 of 14 fail with "Database access not
     allowed". Run after any DB test, they pass. The full suite is unaffected.
   - Fix: give those tests the `db` mark, or stub the provider for non-DB
     tests.

## Acceptance Criteria

- [ ] Items 1–3 are fixed and pinned by tests (each mutation-checked) before
      the host setting is turned on in todo 428 slice C.
- [ ] Items 4–7 are fixed or closed with a reason.

## Work Log

### 2026-09-25 - Filed from todo 428 slice A review round 1

- Neither reviewer found a blocking issue, so round 2 was not needed. Findings
  above were copied from both reports and checked against the code.
