---
status: completed
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

- [x] A decision recorded on which of the three policies applies
- [x] `safety`, `bandit` and `nltk` absent from `backend/venv`, proven by
      re-running the `env_integrity` comparison
- [x] If a check is added, it distinguishes "removed on purpose" from
      "legitimately unpinned dev tool" — a check that flags `flake8` will be
      switched off within a day

## Notes

Found while verifying todo 378's install, by the environment stamp built for
todo 379. The stamp reported `43 unpinned` on a venv that had just been declared
clean, which is exactly the kind of question the stamp exists to raise.

### 2026-09-13 - Policy chosen and applied (PR pending review)

**Policy: option 2, "name the known-removed set."** Report-only leaves the count
(`43 unpinned`) carrying no signal about which entries are wrong, and full
`pip-sync` semantics would uninstall `flake8`, `isort`, `pip-audit` and
`detect-secrets` unless they are first pinned -- a real decision, not a
mechanical one, and out of scope here.

`REMOVED_ON_PURPOSE` in `apps/core/env_integrity.py` names the three packages
with the reason and the source todo. `removed_but_installed()` reports any that
are still present; `format_lines()` renders one line each, un-truncated, because
"nltk 3.9.2 is installed" prompts nothing without the reason.

**`fix_hints()` was the non-obvious part.** The existing remedy line is
`pip install -r backend/requirements.txt` -- which is the command that *already
failed to help*, since it installs and upgrades but never uninstalls. Printing
it for a removed-on-purpose package sends the reader in a circle. Hints are now
derived from what the report actually contains, and both appear when both
problems do.

The header line gains a separate `N removed-but-installed` count so the
`unpinned` bucket keeps its old meaning.

**Uninstalled by measurement, not by name.** The closure of
`safety + bandit + nltk` over installed packages is 51; subtracting everything
reachable from the 210 names declared across `requirements.txt` and
`requirements-dev.txt` leaves **21 genuinely orphaned** -- the same 21 the
2026-09 OSV work measured, and 30 (including `cryptography`, `httpx`, `rich`,
`pydantic`, `requests`) are shared and were kept.

Removed: authlib, bandit, dparse, filelock, jinja2, joblib, joserfc, markupsafe,
marshmallow, nltk, psutil, regex, ruamel-yaml, ruamel-yaml-clib, safety,
safety-schemas, shellingham, stevedore, tenacity, tomlkit, typer.

Verification:

| Check | Before | After |
| --- | --- | --- |
| `env_integrity --hook` | named all three, hinted *uninstall* | **silent, rc 0** |
| `safety` / `bandit` / `nltk` via `importlib.metadata` | 3.6.2 / 1.9.4 / 3.9.2 | **absent** |
| unpinned count | 43 | **22** |
| mismatched / not-installed | 0 / 0 | 0 / 0 |
| `pip check` | -- | `No broken requirements found` |
| `manage.py check` | -- | `no issues (0 silenced)` |
| `pytest apps/core` | -- | **207 passed** |
| `pytest apps/core/tests/test_env_integrity.py` | -- | **43 passed** (10 new) |

The detector was positive-controlled *before* the uninstall (it fired, named all
three, and printed the uninstall hint rather than the install one) and
negative-controlled after (silent). A detector only ever checked against a clean
environment proves nothing.

**Two existing tests needed real fixes, not accommodation:**

- `test_drift_report_runs_against_the_real_environment` asserted every line
  starts with `"  mismatched:"` or `"  not installed:"`. The set of valid shapes
  grew; it now includes `REMOVED_MARKER`, shared with `format_lines` so the two
  cannot drift.
- `test_main_is_silent_and_zero_when_the_environment_is_clean` passed only
  because the real installed set had no removed packages. It now patches
  `REMOVED_ON_PURPOSE` to `{}`, so it tests `main()` rather than the developer's
  venv -- it would have failed for anyone still carrying nltk.

**`web/node_modules`: confirmed not affected, empirically rather than from the
docs.** In a scratch package, a hand-planted `node_modules/stray-removed-pkg`
survived until `npm ci`, which removed it. `npm ci` deletes `node_modules`
before installing, so the pip failure mode has no npm analogue.
`.github/workflows/web-ci.yml:42` uses `npm ci`.

## Review round 1

`removed_but_installed()` compared the hand-maintained `REMOVED_ON_PURPOSE`
keys **raw** against `installed`, whose keys are PEP 503-normalized. That is
correct only by coincidence: all three current entries (`safety`, `bandit`,
`nltk`) are single lowercase tokens with no separators, so `normalize(k) == k`.
Adding `PyYAML` or `ruamel.yaml` to the dict -- which the module's own comment
invites, since the list is maintained by hand -- would have made the lookup
match nothing, silently. That is the same silent-miss this whole check exists
to prevent, reintroduced one level up in the very function meant to close it.

Fixed by normalizing both sides. Pinned by
`test_a_removed_name_is_matched_after_pep503_normalization`, which was
mutation-checked: reverted to the raw `name in installed` lookup it FAILS,
restored it PASSES (43 passed). The file was restored with `cp` from a saved
copy, never `git checkout --`.

### 2026-09-13 - Archived after PR #746 merged

- Verification: all acceptance criteria checked; shipped in #746.
- Review: round 1 + round 2 (subagent). 0 blocking.
