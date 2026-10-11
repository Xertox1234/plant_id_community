---
status: completed
priority: p4
issue_id: "392"
tags: [code-quality, logging, backend, tech-debt, forum, garden]
dependencies: []
source_review: "todos/archive/388-completed-p3-backend-log-prefix-sweep.md"
triage: ready
triaged: 2026-10-10
owner_decision: "Convert the forum_host forum.<event> log names to the bracketed [FORUM] prefix; record it in docs/rules/api.md (2026-09-28; reconfirmed by the owner 2026-10-10)"
---

# The last 7 unprefixed log calls, in two apps todo 388 did not scope

## Problem

Todo 388 swept `core`, `blog`, `users` and `plant_identification` to 0 and took
`backend/apps/` from **339 of 769 non-compliant (44.1%) to 7 of 773 (0.9%)**.
Its acceptance criteria named those four apps, so the remaining 7 calls were
left alone rather than folded in on the last day of the sweep.

They are not a fifth mechanical slice. **Each of the two files raises a
question the sweep's per-file token table cannot answer**, which is exactly why
they were not guessed at.

## Findings

Measured on `main` after todo 388's final slice:

```
python3 scripts/check_log_prefixes.py
7 unprefixed of 773 judgeable (0.9%), 3 files
6 call(s) undeterminable (first arg not a literal), excluded
```

### `backend/apps/forum_host/` — 3 calls, and a competing convention

This is the interesting half. `notifications.py` already has **10** bracketed
calls and `tasks.py` has **31**, so the convention is not missing here — these
three deliberately use a *different* one:

| Line | Call |
| --- | --- |
| `notifications.py:447` | `logger.info("forum.topic_created topic=%s (no author to auto-subscribe)", topic_id)` |
| `notifications.py:501` | `logger.warning("forum_host.notifications: unknown event %r", event)` |
| `tasks.py:71` | `logger.info("%s (task=%s)", line, self.request.id)` |

- The first two use a **dotted event/module name** (`forum.topic_created`,
  `forum_host.notifications:`) where the rest of the file uses `[ERROR]` and
  `[EMAIL]`. Four lines below :447, the same function logs
  `"[ERROR] forum_host: failed to process topic_created topic=%s"`. So the file
  greps two ways, and picking one is a forum decision about what
  `forum.<event>` names are for — they may be a deliberate machine-readable
  event key rather than a prose prefix that someone forgot to bracket.
- `tasks.py:71` is the genuinely awkward one. It re-emits **another command's
  captured stdout, one line at a time** (`for line in out.getvalue()...`).
  Prefixing it stamps a token onto output this module did not write, and the
  inner management command may already prefix its own lines — so the naive fix
  risks producing a double prefix that `check_log_prefixes.py` would call
  compliant, since it only inspects the literal.

### `backend/apps/garden_calendar/signals.py` — 4 calls, and a smell

| Line | Call |
| --- | --- |
| `:58` | `Failed to send community event notifications: {e}` |
| `:85` | `Failed to send RSVP notification: {e}` |
| `:133` | `Failed to send weather alert notifications: {e}` |
| `:152` | `Error cleaning up deleted community event: {e}` |

This half *is* mechanical — but the file has **zero** prefixed calls, so it was
simply never reached by the convention, and all four sit in `except` blocks
that each **re-`import logging` and rebuild `logger` inside the handler**
rather than using a module-level logger. Worth fixing in the same pass; it is
the reason a reader might assume this file has no logging at all.

Likely tokens: `[NOTIFY]` for the three notification failures and `[GARDEN]`
(1 existing use) for the cleanup — but confirm against
`apps/core/services/notification_service.py`, which already owns `[NOTIFY]`.

### The 6 excluded calls are one wrapper, and are correctly excluded

All six are `backend/apps/core/utils/structured_logger.py:169-261`, which calls
`logger.<level>(message)` with a **variable**. The checker reports them as
undeterminable and drops them from both numerator and denominator, which is
right: the prefix belongs at this wrapper's *call sites*, not inside it.
Recorded here so the next person does not re-investigate them.

## Recommended Action

1. Do `garden_calendar/signals.py` first — mechanical, 4 calls, plus hoisting
   the repeated in-handler `import logging` to module level.
2. Then decide the `forum_host` convention question with someone who owns the
   forum: is `forum.<event>` a machine-readable event key that should stay, or
   prose that should be `[FORUM]`? Record the answer in
   `docs/rules/api.md` either way, since the file currently teaches both.
3. `tasks.py:71` last, and only after checking what the inner command emits.
   If it already prefixes, leave it alone and say so in a comment — a token in
   front of someone else's output is worse than none.

Use `scripts/add_log_prefixes.py` (message-keyed table) and verify with
`scripts/check_log_prefixes.py --app <name> --fail-over 0`, the same way todo
388's four slices were verified. Expect pre-existing flake8 violations in these
files to block the commit: 62 were cleared across todo 388's four slices for
that reason alone.

## Acceptance Criteria

- [x] `python3 scripts/check_log_prefixes.py` reports **0 unprefixed** across
      `backend/apps/`, or each remaining call carries an in-code comment saying
      why it is deliberately exempt
- [x] The `forum.<event>` vs `[FORUM]` question is decided and the answer is
      written into `docs/rules/api.md`, so the next reader is not taught two
      conventions by the same file
- [x] `tasks.py:71` is resolved without stamping a prefix onto output the
      module did not write — verified by running the digest task and reading a
      real emitted line, not by reasoning about it
- [x] `garden_calendar/signals.py` uses a module-level logger rather than
      re-importing `logging` inside each `except`
- [x] No log message reworded, proven the way todo 388 proved it: every
      `logger.*` message AST-reconstructed as constant chunks plus
      `ast.unparse` of each interpolation, before and after, and compared
- [x] Backend suite green

## Notes

**Priority rationale: p4.** 0.9% non-compliance is not a real operational
problem, and the `unprefixed-logger-call` trigger in `docs/rules/triggers.json`
now stops new violations at write time, so this debt no longer grows. It is
filed so the last 7 are not rediscovered and re-measured by somebody in a year
— which is the exact failure todo 388 was created to end, when the unmeasured
"5%" claim in GitHub issue #186 turned out to be 46%.

The forum question is the part worth a person's time. The rest is twenty
minutes.

Related: todo 388 (the sweep), todo 361 (which measured the gap and re-scoped),
`docs/rules/api.md:13-14` (the binding rule).

## Work Log

### 2026-10-10 - Owner reconfirmed the decision

- The owner reconfirmed the 2026-09-28 decision, so the blocked-owner triage is lifted and the todo is ready.

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0401)

- `backend/apps/garden_calendar/signals.py`: one module-level logger replaces the four in-`except` `import logging` blocks; the three notification failures take `[NOTIFY]` and the cleanup `[GARDEN]`. The stray mid-file `BaseCommand` import moved to the top (flake8 E402 blocked the commit).
- `backend/apps/forum_host/notifications.py`: per the owner decision, `forum.topic_created` and `forum_host.notifications:` became `[FORUM] topic_created` and `[FORUM] notifications:`; `docs/rules/api.md` now says the dotted form is not a second convention.
- The relay loops in `backend/apps/forum_host/tasks.py` and (found since filing, same shape) `backend/apps/blog/tasks.py` keep no prefix: both commands already write `[EMAIL] ...`. They carry a `# log-prefix: exempt` comment, which `scripts/check_log_prefixes.py` now reports in its own column. A new test runs the real `send_forum_digest` through the task and asserts each relayed line has exactly one `[EMAIL]`.
- No message reworded: 50 logger calls in the four files AST-reconstructed at the merge-base and now, identical apart from the added token (and the two owner-decided dotted names).

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0401)

- AC 1: `python3 scripts/check_log_prefixes.py --root backend/apps --list --fail-over 0` — evidence `.sweep-evidence/g1/392-ac0.txt` (not committed), last lines:

  ```text
  2 call(s) marked `# log-prefix: exempt`, not counted as unprefixed

  backend/apps/blog/tasks.py:78  info      %s (task=%s)  [exempt]
  backend/apps/forum_host/tasks.py:76  info      %s (task=%s)  [exempt]
  exit=0
  ```

- AC 2: `bash -c "grep -n -A10 'Bracketed log prefixes' docs/rules/api.md; echo '--- forum_host logger calls using a dotted forum name:'; grep -rnE 'logger\.[a-z]+\(\s*\"forum(_host)?\.' backend/apps/forum_host || echo none; echo '--- [FORUM] calls:'; grep -rn -A1 'logger\.' backend/apps/forum_host/notifications.py | grep '\[FORUM\]'"` — evidence `.sweep-evidence/g1/392-ac1.txt` (not committed), last lines:

  ```text
  --- forum_host logger calls using a dotted forum name:
  none
  --- [FORUM] calls:
  backend/apps/forum_host/notifications.py-470-                        "[FORUM] topic_created topic=%s (no author to auto-subscribe)",
  backend/apps/forum_host/notifications.py:523:        logger.warning("[FORUM] notifications: unknown event %r", event)
  ```

- AC 3: `bash -c "cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest backend/apps/forum_host/tests/test_tasks.py::test_weekly_digest_relays_the_real_command_output_with_one_prefix --create-db -s -q"` — evidence `.sweep-evidence/g1/392-ac2.txt` (not committed), last lines:

  ```text
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 2 warnings in 18.44s ========================
  exit=0
  ```

- AC 4: `grep -n 'import logging\|logger = logging.getLogger\|logger\.' backend/apps/garden_calendar/signals.py` — evidence `.sweep-evidence/g1/392-ac3.txt` (not committed), last lines:

  ```text
  17:logger = logging.getLogger(__name__)
  60:            logger.error(f"[NOTIFY] Failed to send community event notifications: {e}")
  84:            logger.error(f"[NOTIFY] Failed to send RSVP notification: {e}")
  129:            logger.error(f"[NOTIFY] Failed to send weather alert notifications: {e}")
  145:        logger.error(f"[GARDEN] Error cleaning up deleted community event: {e}")
  ```

- AC 5: `python3 .sweep-evidence/g1/compare_log_messages.py . 1bd2d0fac1afc270937424ed631a38d3a0b6fe7f` — evidence `.sweep-evidence/g1/392-ac4.txt` (not committed), last lines:

  ```text
  == backend/apps/forum_host/tasks.py: 31 before, 31 after
  == backend/apps/blog/tasks.py: 3 before, 3 after

  50 logger calls compared, 0 reworded
  exit=0
  ```

- AC 6: `bash -c "cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest --create-db -q -p no:cacheprovider"` — evidence `.sweep-evidence/g1/392-ac5.txt` (not committed), last lines:

  ```text
    File "backend/apps/plant_identification/services/combined_identification_service.py", line 121, in _cleanup_executor
      logger.info("[SHUTDOWN] ThreadPoolExecutor cleanup complete")
  Message: '[SHUTDOWN] ThreadPoolExecutor cleanup complete'
  Arguments: ()
  exit=0
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0401)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
