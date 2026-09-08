---
status: completed
priority: p3
issue_id: "358"
tags: [security, backend, testing]
dependencies: []
source_review: "todos/354-pending-p3-codeql-alert-backlog-triage.md"
---

# Widen the requests-exception drift guard to the whole service layer

## Problem

`test_no_requests_handler_interpolates_its_exception`
(`backend/apps/plant_identification/tests/test_error_body_exposure.py`) is an
AST guard that fails when an `except requests...` handler interpolates its own
exception into a logger call. It earned its keep immediately — it found three
leak sites in Trefle's `retry_on_failure` decorator that a manual read had
missed — but it is deliberately scoped to two files:

```python
KEYED_IN_QUERY_STRING = [
    "apps/plant_identification/services/plantnet_service.py",
    "apps/plant_identification/services/trefle_service.py",
]
```

Those are the two services that authenticate with a **query parameter**, where
`requests`' prepared-URL exception message carries the key. The scope was
narrowed on purpose during todo 354: running it across `apps/*/services/*.py`
failed on files that PR did not own, and one of those failures was a real leak
being fixed on a sibling branch at the time.

## Findings

Widening it to `apps/*/services/*.py` fails on exactly four files. Measured by
running the guard function over every service on a tree with all six todo-354
PRs merged together, so this is the post-merge state, not a prediction:

| File | Line | Why it fails | Real leak? |
| --- | --- | --- | --- |
| `plant_identification/services/plant_health_service.py` | 166 | `{str(e)}` | No — `Api-Key` **header** auth, so the URL carries no credential |
| `plant_identification/services/plant_id_service.py` | 311 | `{e}` | No — `Api-Key` header |
| `plant_identification/services/unsplash_service.py` | 92 | `{str(e)}` | No — `Authorization: Client-ID` header |
| `plant_identification/services/pexels_service.py` | 85 | `{str(e)}` | No — `Authorization` header |

All four are **header-authenticated and safe today**. Both weather services and
both query-string services are already clean on that tree, so there is no live
leak left to chase — this todo is purely about making the property structural.

They are not harmless, though: the exception message still writes the full
request URL into the log, so the day someone adds a query parameter to one of
these clients, the leak is silent and the guard is what would catch it.

`packages/wagtail_forum/wagtail_forum/embeds.py:89` also interpolates, into an
`EmbedNotFoundException` message rather than a log; the URL there is the user's
own embed URL, not a credential.

## Recommended Action

1. Flip the parametrisation from `KEYED_IN_QUERY_STRING` to
   `sorted(pathlib.Path("apps").glob("*/services/*.py"))`.
2. Convert the four header-authenticated services to
   `log_safe_api_error(exc)` — mechanical, one line each, and it makes the
   safety structural rather than contingent on where the key happens to sit.
3. Decide `embeds.py` separately: it is a package, not an app, and the message
   is raised rather than logged. Either widen the glob to cover
   `packages/**/wagtail_forum/*.py` or record why it stays out.
4. Consider promoting the guard out of `test_error_body_exposure.py` into a
   shared `apps/core/tests/` module — it is a repo-wide invariant that happens
   to live in the plant_identification suite for historical reasons.

## Technical Details

- The guard follows aliases (`last_exception = e`) across the enclosing
  function, and is scoped per-handler so a later `except Exception as e` — which
  a `RequestException` can never reach — is not a false positive. Keep both
  properties when moving it; each was added in response to a real false result.
- `log_safe_api_error()` lives in `apps/core/utils/pii_safe_logging.py`.
- The matching JIT trigger is `requests-exception-interpolated` in
  `docs/rules/triggers.json`; the rule is in `docs/rules/security.md`.

## Acceptance Criteria

- [x] The guard is parametrised over every `apps/*/services/*.py`, with no
      hardcoded file list
- [x] Every service it now covers uses `log_safe_api_error()` in its
      `requests` handlers
- [x] `embeds.py` is either covered or has a written reason it is not
- [x] Mutation check: reintroducing a raw `{e}` in any covered file fails the
      guard

## Work Log

### 2026-09-08 - Completed

Shipped wider than the AC asked, and the AC's own prescribed implementation was
not used. Both deviations are deliberate.

**Scope: the whole backend code tree, not `apps/*/services/*.py`.** Measured
before choosing: running the guard over `apps/` + `packages/` +
`plant_community_backend/` takes 0.8s and returns the same four offenders this
todo's table lists — no fifth file, so the "no live leak remains" premise held.
Since a wider sweep cost nothing and matches the JIT trigger's own
`backend/**/*.py` glob, a `requests` handler written in a view or a Celery task
is now covered too, not just one under `services/`.

**The AC's prescribed `pathlib.Path("apps").glob("*/services/*.py")` fails
open** — it is CWD-relative, pytest never chdirs, and from the repo root it
returns `[]`, which makes `parametrize` collect one *skipped* test and the guard
report green having read nothing. The hardcoded list it replaced would have
raised `FileNotFoundError`; the "structural" version traded a loud failure for a
silent pass. Anchored on `Path(__file__).resolve().parents[3]` instead, with
`test_the_sweep_is_not_vacuous` asserting >400 files walked, that plantnet and
trefle are still in the discovered set, and that the collapse case
(`roots=("no-such-directory",)`) really yields nothing. Recorded in
`docs/LEARNINGS.md`.

**Widening to `packages/` surfaced a second trap the todo did not predict:**
`packages/wagtail_forum/build/` holds **120 stale gitignored `.py` copies** of
the package. Scanning them means the sweep covers a different file set locally
than in a fresh CI checkout, and a violation already fixed in the real source
could fail from its stale twin. Added an artefact filter (588 files scanned, not
708) plus `test_the_sweep_scans_no_build_artefact`, which cross-checks against
`git check-ignore` rather than against the filter list — so a future `.tox/` or
a second package's `build/` fails loudly instead of being silently swept.
Untracked-but-not-ignored stays legal; a peer agent's uncommitted work lives in
this checkout.

**Guard hardening:** it read `call.args` only, so
`logger.error("failed", extra={"err": str(e)})` escaped. Now reads keywords too.
Re-ran across all 588 files with the fix applied first — still exactly four
offenders, so this is hardening, not a new finding.

**Home:** split into `apps/core/tests/test_requests_exception_drift.py`, next to
`test_pii_safe_logging.py`, which tests the helper it prescribes. Only the AST
helper and its test moved; the four plant_identification-specific tests and the
`capture()` contextmanager stayed in `test_error_body_exposure.py` with a
pointer comment. Nothing outside that file referenced `KEYED_IN_QUERY_STRING`.

**`embeds.py`: written reason, not coverage (AC 3).** Widening the glob to
`packages/` would have made it pass *vacuously* — `logger_calls()` only inspects
calls prefixed `logger.`, so `raise EmbedNotFoundException(f"Request failed:
{e}")` is structurally invisible and green there means "audited nothing". The
reason it stays out is evidence-based, not assumed: the oEmbed request's params
are `url`/`format`/`maxwidth`/`maxheight` (no credential), and
`test_an_unreachable_provider_still_saves_the_post_as_a_link_card` shows the
caller swallows the exception into a plain link card, so the message reaches no
response body. Recorded in the new module's docstring alongside its other three
blind spots.

**Four services converted** to `log_safe_api_error(e)` with the auth mechanism
named in a comment at each site, following the precedents already in the tree
(`plantnet_service.py:168-169` for keeping the `Response status`/`Response body`
pair, `trefle_service.py:233` for keeping the bare `{url}`). No test anywhere
asserts on these four services' log text.

Touching those four files put them under the pre-commit `flake8` gate for the
first time, which failed on nine **pre-existing** findings. Root `setup.cfg`'s
per-file-ignores block says in as many words "do not widen these suppressions",
so the sanctioned path was to clean rather than suppress. Every deletion is
provably dead and behaviour-neutral: four unused imports (`cache`, `time`,
`List`, `default_storage`), two `f` prefixes on f-strings with no placeholders,
an unused `as e` on `except CircuitBreakerError`, and two `attribution` locals
that were built and dropped. The last two were checked rather than assumed --
attribution is genuinely produced elsewhere
(`plant_image_service.get_attribution_text`, and `attribution_url` in both
services' search results), and `photographer`, which the dead line read, is
still used two lines later for image tags. This cleanup was gate-required, not
volunteered.

**Verification.** The guard module is 12 tests: 9 parametrised node ids (not one
skip) plus the three above. Mutation check ran **both** shapes against
`plant_id_service.py` — positional `{e}` and `extra={"err": str(e)}` — each
failing the guard and naming the file in the node id, restored from a `cp`
backup rather than `git checkout --`.

Full backend suite: **2335 passed, 24 failed, 8 skipped, 1 error** (4m27s).
None of the 24 are mine, and that is measured rather than argued: the same four
suites fail standalone at **24 failed / 34 passed**, and re-running that exact
command with my six files restored to HEAD gives **24 failed / 34 passed**
again. They are `test_image_rendition_formats` (WEBP/AVIF, see todo 371),
`apps/blog/tests/test_analytics.py`, and the forum image-management +
`test_host_api_routes_match_package` failures belonging to a peer agent's
uncommitted work in this shared checkout.

Two process notes. `isort --profile black` run from `backend/` classifies
`apps.*` as **first-party** and moves the new import below the django block;
pre-commit runs it from the **repo root**, where `apps/` is not a top-level
directory, so it sorts as third-party — which is why the existing
plantnet/trefle imports sit where they do. Run it from the repo root or you
will commit churn the hook then reverses. And the first full-suite run launched
with the Bash tool's background flag died silently (0-byte log, no process),
exactly as `project_background_pytest_detach_macos` records; the run above used
`Popen(start_new_session=True)` with a pid file.

One thing worth knowing for anyone touching this: `manage.py test` cannot run
this guard at all. The tests are module-level `def test_*` with no `TestCase`,
so Django's runner collects none of them. CI's `python -m pytest` from
`backend/` is the only thing that executes it.

### 2026-09-08 - Review round 1

Two independent reviewers found the same HIGH, and it was the guard's own
predicate — the thing this PR promotes to a repo-wide guarantee.

`interpolates()` marked as safe **every** `Name` under **any** attribute
access, not just the approved `e.response.status_code`. Confirmed empirically,
not just traced: `e.response.url`, `e.request.url` and `e.args[0]` all passed
the guard unflagged. The first two *are* the prepared URL; the third *is* the
string `str(e)` returns. So the guard permitted the exact leak it exists to
stop, in three shapes that look like the approved one.

Fixed by replacing the blanket rule with an explicit `APPROVED_SHAPES`
allowlist (`type(e).__name__`, `e.response.status_code`, `e.response.text`,
`log_safe_api_error(e)`); everything else is reported. Verified both
directions: no regression across all 589 files, and all three leak shapes now
flagged. The allowlist matters beyond these three — it fails closed on the
shape nobody has thought of yet, which a denylist cannot.

The second HIGH was the reason the first shipped: the planted specimen only
exercised shapes the buggy code also passed, so the self-test could not
discriminate the intended policy from the implemented one. The specimen now
carries all three leak shapes, each pinned by its own assertion, and a mutation
check confirms it: restoring the old blanket whitelist fails
`test_the_guard_flags_a_planted_violation` on `resp url`. An anti-vacuity test
that only tests the shapes you thought of is itself vacuous.

`docs/rules/security.md` gained the corrected rule — "not `str(e)`" is not the
same as "any attribute of `e`" — since the blind-spot list this PR wrote was
narrower than what the code allowed.

Also fixed: the `git check-ignore` skip guard claimed to cover "git
unavailable", but a missing binary raises `OSError` and never reaches the
`returncode > 1` branch. Now caught explicitly.

Deferred, with reasons:

- **Response-body `str(e)`** (MEDIUM). Five sites return `str(e)` in a result
  dict, which the guard structurally cannot see. Traced the live anonymous
  `/status/` endpoint: it merges only trefle and plantnet, both closed by todo
  354, and `plant_health`'s is reachable from no view. Fixing one of five
  arbitrarily is worse than tracking all five, so this is **todo 377** with the
  reachability trace attached. Recorded as a fifth blind spot in the guard's
  docstring.
- **git-unavailable still skips rather than fails** (LOW). CI always runs
  against a full checkout, proven by the job log.
- **Membership floor rather than a count floor** (INFO). Deliberate, already
  explained in the code.

The bundled deep pass returned **no findings on this branch**. Every finding it
did report belongs to a peer agent's uncommitted forum-image work in this
shared checkout and was left alone.

Residue swept after the reviews: no `MUTANT` markers, working tree unchanged
apart from this PR's own files.

### 2026-09-06 - Filed

Split out of todo 354, which narrowed the guard to two files mid-PR because
widening it failed on files that PR did not own.

## Notes

p3: no known live leak remains after todo 354 — the four that existed are
closed. This is about making the guarantee structural instead of resting on
"the key happens to be in a header today".
