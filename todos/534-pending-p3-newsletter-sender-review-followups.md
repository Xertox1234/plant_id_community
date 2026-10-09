---
status: pending
priority: p3
issue_id: "534"
tags: [backend, blog, email, celery]
dependencies: ["409"]
---

# Non-blocking review findings from PR #969 (todo 409, slice B)

## Problem

Round 1 of the review on the weekly newsletter sender found nothing blocking.
These are the findings it left.

## Findings

1. **Excerpt words run together** (`apps/blog/newsletter_digest.py`, `_excerpt`).
   `strip_tags` adds no whitespace between block tags, so `<p>One.</p><p>Two</p>`
   (Draftail's normal output) becomes "One.Two" in the email; `<br/>` does the
   same. The test uses a single paragraph. This is the most visible one: fix it
   before the first real newsletter goes out.
2. **A DB outage while building one email is swallowed**
   (`send_blog_newsletter.py`, the build `except Exception`). An `OperationalError`
   there is counted as `failed`, so `autoretry_for` never fires and every
   subscriber waits a week. Re-raise `OperationalError` before the generic
   except; nothing has been claimed yet, so a retry is safe.
3. **`_release` raising leaves the claim in place.** If the release after a failed
   send hits `OperationalError`, the row stays stamped with nothing sent, and
   that reader misses a week. Wrap the release in its own try/log.
4. **Soft limit after delivery means a possible double send.** If
   `SoftTimeLimitExceeded` lands after `message.send()` handed the mail over,
   the claim is released and the continuation mails that reader again. The
   window is milliseconds; the forum digest has the same property. At least
   add a comment.
5. **A Redis outage reads as "another run holds the lock".** The cache has
   `IGNORE_EXCEPTIONS: True`, so `cache.add` returns falsy and the run exits
   without a retry until next week. The forum digest behaves the same way.
6. **Prune versus re-signup race.** The M2M blocks fast delete, so
   `.delete()` selects and then deletes by pk. A stale row re-stamped by
   `request_confirmation` in between is deleted anyway, and the link just
   emailed comes back invalid. Also: `request_confirmation` raises
   `DoesNotExist` if the row vanishes between `get_or_create` and
   `select_for_update`.
7. **Hard kill / SIGKILL** strands the one row claimed at that moment (its
   posts are never sent) and holds the lock for its 2 h TTL.
8. **Test gaps:**
   - a lost claim (`_send_one` returns None);
   - `_release` refusing to overwrite a later stamp;
   - a pinned `retry_backoff` countdown (`docs/rules/celery.md`).
9. **Style:** f-strings in logging calls (the forum task uses `%s`).
10. **Web, low:** `focus:outline-none` on the programmatically focused signup
    status line. It is `tabIndex={-1}` and non-interactive, so this is
    defensible.

## Acceptance Criteria

- [x] Items 1 and 2 fixed with tests (multi-paragraph excerpt; a build
  `OperationalError` propagates).
- [ ] Items 3–10 fixed, or each declined here with a reason.

## Work Log

### 2026-10-09 - Filed from PR #969 review round 1

### 2026-10-09 - Items 1 and 2 fixed (before the first send)

- Item 1: `_excerpt` replaces `<br>`, `<hr>` and the end of each block
  (`p`, `div`, `li`, `h1`–`h6`, `blockquote`, `pre`, `ul`, `ol`) with a space
  before `strip_tags`; inline tags still add none ("Moss, ferns.").
  Test: `test_paragraphs_and_line_breaks_keep_words_apart`.
- Item 2: the build step re-raises `OperationalError` with the soft limit,
  so the task's `autoretry_for` fires; nothing is claimed at that point.
  Test: `test_a_database_outage_while_building_reaches_the_task_retry`.
- Mutation check: reverting either fix fails exactly its own test.
- Items 3–10 remain open.
