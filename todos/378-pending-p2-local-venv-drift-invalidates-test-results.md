---
status: pending
priority: p2
issue_id: "378"
tags: [testing, tooling, harness, backend]
dependencies: []
source_review: "todos/archive/374-pending-p2-forum-image-reuse-delete-ui.md"
---

# `backend/venv` drifts from `requirements.txt`, silently invalidating every local test result

## Problem

Two tests fail locally and pass in CI:

```
apps/core/tests/test_image_rendition_formats.py::test_modern_format_original_keeps_its_format_in_the_rendition[WEBP-rendition-probe.webp]
apps/core/tests/test_image_rendition_formats.py::test_modern_format_original_keeps_its_format_in_the_rendition[AVIF-rendition-probe.avif]
E   AssertionError: assert 'png' == 'webp'
```

Neither is a bug. `backend/venv` is stuck on the pre-#710 dependency set, so
those tests assert Wagtail **8.0** behaviour against an installed Wagtail
**7.4.3**. Wagtail 8.0 dropped `webp`/`avif` from `Filter.run()`'s
`default_conversions`; 7.4.3 still converts them to PNG. The test is right and
the environment is wrong.

Measured 2026-09-08 by comparing all 210 pinned packages against `pip freeze`:

| Package | Pinned | Installed |
| --- | --- | --- |
| `wagtail` | 8.0 | **7.4.3** |
| `draftjs-exporter` | 7.1.0 | **5.2.0** |
| `modelsearch` | 1.3.2 | **1.3.1** |
| `django-ninja` | 1.7.0 | **not installed** |
| `swapper` | 1.5.0 | **not installed** |

All five are the Wagtail 8 upgrade (PR #710). The venv was never reinstalled
after it merged.

## Why this is p2 and not a chore

**Every local test result is evidence about a tree CI does not run.** During the
todo 358 and 374 sessions the whole suite was executed repeatedly against
Wagtail 7.4.3 while CI ran 8.0, and that produced two concrete wrong calls:

1. 14 failures were reported to the user as "pre-existing and unrelated,
   local-env only". Twelve of them were a real bug (a `post_migrate` receiver
   raising on a flush-truncated collection tree — todo 374), and CI caught what
   local runs had normalised into background noise.
2. The remaining two — these — were reported as "local Pillow, green in CI",
   which named the wrong cause. Pillow is at its pinned version; Wagtail is not.

A drifted venv does not fail loudly. It produces a plausible-looking failure
list that a reader learns to skip, which is worse than a crash.

This has bitten before: the OSV/pip-audit work already recorded that
`backend/venv` "had already drifted" and had to be verified in a scratch venv.
That was treated as a one-off. It is not.

## Recommended Action

1. **Fix the immediate drift**: `pip install -r backend/requirements.txt` in
   `backend/venv`, then confirm `test_image_rendition_formats.py` passes 4/4
   and the full suite matches CI's count.
2. **Add a drift guard as a Claude Code hook.** The available hook events were
   confirmed against the settings schema; both options below use real ones.

   **Option A — `PreToolUse` on `Bash`, filtered to test commands.** Fires at
   the exact moment drift would produce a misleading result, not before:

   ```json
   {
     "matcher": "Bash",
     "hooks": [{
       "type": "command",
       "command": ".claude/hooks/check-venv-drift.sh",
       "if": "Bash(python -m pytest*)",
       "timeout": 10
     }]
   }
   ```

   The `if` field takes permission-rule syntax, so the hook only spawns for
   pytest invocations instead of on every shell command. Emit
   `hookSpecificOutput.additionalContext` so the drift lands in the model's
   context rather than only on screen — the failure mode being fixed is a
   *reader* discounting failures, so the warning has to reach the reader.

   **Option B — `SessionStart`.** One check per session, cheapest, but it warns
   long before any test runs and is easy to scroll past. Consider `async: true`
   so it never delays startup.

   A also catches drift introduced mid-session (a `git pull` that moves
   `requirements.txt`), which B cannot. Recommend A, optionally both.
3. **Make the check cheap and exact**: parse `requirements.txt` for `name==ver`
   and compare against `pip freeze` from `backend/venv` — the comparison in the
   table above ran in well under a second over 210 packages. Report mismatches
   AND not-installed separately; the two `not installed` rows here are what a
   naive "compare versions of what's installed" check would have missed.
4. Consider whether the same guard belongs on `web/node_modules` vs
   `package-lock.json`. Out of scope until someone measures whether it drifts.

## Technical Details

- Available hook events (from the settings schema): `PreToolUse`,
  `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Notification`,
  `UserPromptSubmit`, `SessionStart`, `SessionEnd`, `Stop`, `SubagentStart`,
  `SubagentStop`, `PreCompact`, `PostCompact`, `PermissionRequest`, `Setup`,
  and others. `SessionStart` and `PreToolUse` are the two that fit here.
- Useful hook fields for this: `if` (permission-rule filter, avoids spawning on
  every Bash call), `async` / `asyncRewake`, `once`, `timeout`, and
  `hookSpecificOutput.additionalContext` (injects text into model context).
- `.claude/` is committed, so a project-level hook reaches every worktree only
  after a rebase — existing worktrees keep their old setup.
- Existing hooks live in `.claude/hooks/` with a `test-*.sh` beside each; follow
  that convention and extend `.claude/hooks/test-inject-patterns.sh`'s sibling
  pattern with a `test-check-venv-drift.sh`.

## Acceptance Criteria

- [x] `backend/venv` matches `requirements.txt`: zero version mismatches and
      zero not-installed, proven by re-running the comparison (2026-09-08:
      `pip install -r requirements.txt` installed wagtail 8.0, draftjs-exporter
      7.1.0, modelsearch 1.3.2, django-ninja 1.7.0, swapper 1.5.0; the
      comparison now reports `210 pinned, 0 mismatched, 0 not installed`)
- [ ] `test_image_rendition_formats.py` passes 4/4 locally — **still 2/4 after
      the install; see "The install did not fix the rendition tests" below**
- [ ] Decide whether the 43 unpinned-but-installed packages matter → todo 380

The guard itself is **todo 379's**, not this todo's. The three hook criteria
that used to live here were duplicated verbatim there, and whichever todo closed
second would have looked already-done. Shipped 2026-09-08 as
`backend/conftest.py`, `backend/apps/core/env_integrity.py` and
`.claude/hooks/check-test-env.sh`.

## The install did not fix the rendition tests

This todo's stated root cause — "those tests assert Wagtail 8.0 behaviour
against an installed Wagtail 7.4.3" — is **not sufficient**. With the venv now
provably matching `requirements.txt`, both parameterisations still fail
`assert 'png' == 'webp'`. Ruled out on 2026-09-08:

- `wagtail.__version__` is `8.0`, and its `Filter.run()` `default_conversions`
  is `{"bmp": "png", "heic": "jpeg"}` — webp/avif are genuinely absent, so
  `output_format` should fall back to `original_format`.
- `WAGTAILIMAGES_FORMAT_CONVERSIONS` is unset, so nothing re-adds them.
- Willow reports `format_name == "webp"` for the exact buffer the test uploads.
- The image model is stock `wagtail.images.models.Image` with no custom
  `get_rendition`.

So something *after* format selection is rewriting the extension. That is a
real local/CI divergence, not environment drift, and it is now safe to say so:
the environment stamp proves the tree is clean. Likely related to todo 371
(R2 rendition verification after Wagtail 8).

## Notes

p2 because it corrupts the evidence every other task depends on, and because it
already caused two wrong reports to the user in a single day. The fix in step 1
is a one-line install; steps 2–3 are what stop it recurring.

**`pip install -r` does not evict removed pins.** After the install, 43
packages are installed that `requirements.txt` does not pin — including
`safety` 3.6.2, `bandit` 1.9.4 and `nltk` 3.9.2, the subtree deliberately
removed on 2026-09-05 (todo 355 slice 1) because nltk carried 18 advisories.
The original AC above ("zero mismatches and zero not-installed") is blind to
that bucket and would have passed with the advisory-bearing packages still
present. Tracked in todo 380.
