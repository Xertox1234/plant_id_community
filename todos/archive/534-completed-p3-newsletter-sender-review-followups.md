---
status: completed
priority: p3
issue_id: "534"
tags: [backend, blog, email, celery]
dependencies: ["409"]
triage: ready
triaged: 2026-10-10
owner_decision: "Items 5-7: fix in the blog newsletter here; file a follow-up todo for the same fixes in the forum digest (2026-10-10)"
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
- [x] Items 3–10 fixed, or each declined here with a reason.

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

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0053)

- Items 3, 4 and 7 (claim): `_send_one` now claims and sends inside one
  `transaction.atomic()`; a failed send calls `set_rollback(True)`, so there is
  no separate `_release` left to fail (item 3), and a hard kill rolls the
  uncommitted claim back (item 7). The comment there states the cost (item 4):
  a kill, soft limit or failed commit after the hand-over mails that reader
  again, as owner-accepted at-least-once for the forum digest (todo 541).
- Items 5 and 7 (lock): `cache.add` answering `None` (a Redis outage under
  `IGNORE_EXCEPTIONS`) now logs a warning and sends without the lock; only
  `False` exits. `NEWSLETTER_RUN_LOCK_SECONDS` is the hard time limit plus
  5 min instead of 2 h.
- Item 6: `newsletter_digest.prune_stale_unconfirmed` locks the stale rows
  (`select_for_update`) before deleting them, so a signup's re-stamp is
  re-checked and spared; `request_confirmation` makes the row again when the
  prune deleted it between `get_or_create` and the lock.
- Item 8: tests for a lost claim, a pinned 60/120/240 s retry countdown, and two
  real-commit tests (the claim is invisible to another connection during the
  send; the prune spares a row re-stamped meanwhile). Item 8's `_release`
  bullet is obsolete: `_release` no longer exists. Item 9: blog newsletter
  logging uses `%s` arguments.
- Item 10 declined: the status line is `tabIndex={-1}`, focused only so screen
  readers announce it, and never keyboard-reachable, so a focus ring would
  mark nothing the user can act on. Items 5 and 7 for the forum digest are
  todo 548 (item 6 has no forum counterpart).

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0053)

- AC 2: `python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest backend/apps/blog/tests/test_newsletter_digest.py backend/apps/blog/tests/test_newsletter.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g7/534-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ============== 63 passed, 3 warnings, 3 subtests passed in 19.70s ==============
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0053)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
