---
status: pending
priority: p3
issue_id: "380"
tags: [security, tooling, backend]
dependencies: []
source_review: "todos/378-pending-p2-local-venv-drift-invalidates-test-results.md"
---

# `safety`, `bandit` and `nltk` are still installed in `backend/venv` months after being removed

## Problem

`pip install -r requirements.txt` installs and upgrades. It does **not**
uninstall anything the file stopped pinning. So a package removed from
`requirements.txt` stays in every venv that already had it, indefinitely, and
no existing check looks for it.

Measured 2026-09-08, immediately after a clean
`pip install -r backend/requirements.txt` that brought mismatches and
not-installed to zero:

| Package | Status |
| --- | --- |
| `safety` | 3.6.2 installed, not pinned |
| `bandit` | 1.9.4 installed, not pinned |
| `nltk` | 3.9.2 installed, not pinned |

All three were deliberately removed on 2026-09-05 (todo 355, slice 1). The
stated reason in `backend/requirements-dev.txt` is explicit: both were "declared
and invoked by nothing — no workflow, no pre-commit hook, no script — while
safety alone dragged in nltk, which carried 18 published advisories."

Those 18 advisories are therefore still present locally. They are not in CI, not
in the Docker image, and not in production — `pip install -r requirements.txt`
into a *fresh* environment is correct. This is a local-developer-environment
issue only, which is why it is p3 and not p2.

## Why it is worth a todo rather than a shrug

Todo 378's acceptance criterion was "zero version mismatches and zero
not-installed, proven by re-running the comparison". That criterion **passes
with all three still installed** — it only ever looked at the pinned set. A
green check that cannot see the thing you care about is the same false-green
shape as todo 356 (root npm manifest) and todo 379 (a hook that never fires).

`backend/conftest.py` now reports the count (`43 unpinned`) in its header, but
deliberately does not gate on it: `flake8`, `isort`, `pip-audit` and
`detect-secrets` are also in that bucket and are legitimately in use.

## Recommended Action

1. Decide the policy. Three options, in increasing strictness:
   - **Report only** (status quo). The count is visible; a human notices.
   - **Name the known-removed set.** Keep a small explicit list of packages that
     *were* pinned and were removed on purpose, and have the banner name them
     when they are still installed. Cheap, targeted, no false positives.
   - **Full sync semantics** (`pip-sync`, or `uv pip sync`). Correct, but it
     would uninstall the four legitimately-used dev tools above unless they are
     first added to `requirements.txt` — which is a real decision, not a
     mechanical one.
2. Whatever the policy, uninstall the `safety`/`bandit`/`nltk` subtree from
   `backend/venv` locally. Note the subtree is larger than it looks: the 2026-09
   work measured safety's real dependency subtree at **21 packages, not 6**, so
   uninstall by measuring what becomes orphaned rather than by naming three.
3. Consider whether the same question applies to `web/node_modules` — `npm ci`
   *does* prune, so probably not. Confirm rather than assume.

## Acceptance Criteria

- [ ] A decision recorded on which of the three policies applies
- [ ] `safety`, `bandit` and `nltk` absent from `backend/venv`, proven by
      re-running the `env_integrity` comparison
- [ ] If a check is added, it distinguishes "removed on purpose" from
      "legitimately unpinned dev tool" — a check that flags `flake8` will be
      switched off within a day

## Notes

Found while verifying todo 378's install, by the environment stamp built for
todo 379. The stamp reported `43 unpinned` on a venv that had just been declared
clean, which is exactly the kind of question the stamp exists to raise.
