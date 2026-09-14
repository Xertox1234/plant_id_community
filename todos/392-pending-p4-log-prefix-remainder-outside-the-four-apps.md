---
status: pending
priority: p4
issue_id: "392"
tags: [code-quality, logging, backend, tech-debt, forum, garden]
dependencies: []
source_review: "todos/archive/388-completed-p3-backend-log-prefix-sweep.md"
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

- [ ] `python3 scripts/check_log_prefixes.py` reports **0 unprefixed** across
      `backend/apps/`, or each remaining call carries an in-code comment saying
      why it is deliberately exempt
- [ ] The `forum.<event>` vs `[FORUM]` question is decided and the answer is
      written into `docs/rules/api.md`, so the next reader is not taught two
      conventions by the same file
- [ ] `tasks.py:71` is resolved without stamping a prefix onto output the
      module did not write — verified by running the digest task and reading a
      real emitted line, not by reasoning about it
- [ ] `garden_calendar/signals.py` uses a module-level logger rather than
      re-importing `logging` inside each `except`
- [ ] No log message reworded, proven the way todo 388 proved it: every
      `logger.*` message AST-reconstructed as constant chunks plus
      `ast.unparse` of each interpolation, before and after, and compared
- [ ] Backend suite green

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
