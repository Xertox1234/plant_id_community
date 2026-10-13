---
status: completed
priority: p4
issue_id: "452"
tags: [django, testing, dependencies]
dependencies: []
source_review: "todos/364-pending-p3-mailers-migration-and-warning-gate.md"
triage: ready
triaged: 2026-10-12
owner_decision: "Unblocked by owner: land it with local shims instead of waiting for upstream. Remove both ignore: lines from backend/pytest.ini; add a narrow, version-guarded compat shim for django-taggit's ExtraJoinRestriction.as_sql (no quote_name_unless_alias) and route Wagtail's admin mail sending through the MAILERS connection instead of get_connection(); each shim with a test, and a test that fails loudly when an upgraded taggit/wagtail no longer needs it (2026-10-12)"
---

# Remove the two third-party RemovedInDjango70Warning ignores from pytest.ini

## Problem

Todo 364 made `RemovedInDjango70Warning` fail the test run
(`backend/pytest.ini`, `error::`), with two narrow third-party exemptions
(message + module). Both must go before the Django 7.0 upgrade, which
removes the APIs they call:

1. **django-taggit**: `taggit/managers.py` `ExtraJoinRestriction.as_sql`
   calls `compiler.quote_name_unless_alias()`. Django deprecated it in
   ticket #36795, and 7.0 removes it. Seven `test_topic_tags.py` tests hit it
   through the forum tag filter.
2. **Wagtail**: `wagtail/admin/mail.py` `send_emails` calls
   `get_connection()` for workflow and moderation notifications
   (`test_topic_approval.py`). It works under `MAILERS` in 6.x, because
   `get_connection()` returns the default mailer, but 7.0 removes it.

No upstream issue for either could be found on 2026-09-26.

## Recommended Action

On each dependency bump of django-taggit or Wagtail, delete that `ignore:`
line and run the backend suite. If the suite is green, the upstream fix
shipped. If neither has shipped before a Django 7.0 bump is planned, file
an upstream issue or PR, or pin behind a patched fork.

## Acceptance Criteria

- [x] Both `ignore:` lines are removed from `backend/pytest.ini`, and the full
      backend suite passes with the `error::` gate on

## Work Log

### 2026-09-26 - Filed from todo 364 (MAILERS migration + warning gate)

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-2358)

- Removed both third-party `ignore:` lines from `backend/pytest.ini`; the
  `error::django.utils.deprecation.RemovedInDjango70Warning` gate now has no exemption.
- Added `backend/apps/core/django70_compat.py`, installed from `CoreConfig.ready()`:
  taggit's `ExtraJoinRestriction.as_sql` now calls `compiler.quote_name()` (same SQL),
  and `wagtail.admin.mail.get_connection` returns `mailers.default` for Wagtail's bare and
  `username=None, password=None` calls; any other call shape still reaches Django's
  deprecated function, so the gate keeps catching it.
- Each shim is guarded by Django < 7.0, a version ceiling (taggit 6.1.0, Wagtail 8.0) and
  a source check that upstream still calls the deprecated API.
- `backend/apps/core/tests/test_django70_compat.py` covers both shims (taggit SQL equals
  upstream; a Wagtail notification reaches the outbox with the gate on, since
  `OpenedConnection.__exit__` swallows errors) and fails loudly once an upgrade fixes a
  call site or passes a ceiling. Removing `install()` fails 9 tests (mutation check).

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-2358)

- AC 1: `bash -c "cd backend && echo 'ignore: lines in pytest.ini:' && ! grep -nE '^[[:space:]]*ignore:' pytest.ini && grep -n 'error::django.utils.deprecation.RemovedInDjango70Warning' pytest.ini && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest --create-db -q -p no:cacheprovider"` — evidence `.sweep-evidence/g1/452-ac0.txt` (not committed), last lines:

  ```text
  Call stack:
    File "backend/apps/plant_identification/services/combined_identification_service.py", line 121, in _cleanup_executor
      logger.info("[SHUTDOWN] ThreadPoolExecutor cleanup complete")
  Message: '[SHUTDOWN] ThreadPoolExecutor cleanup complete'
  Arguments: ()
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-2358)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-12 - Review round 1: low findings fixed by hand or declined (owner decision: no new todos)

Round 1 found nothing blocking. These were fixed before round 2:

- **A compat probe could stop the app from starting** (raised by 2 reviewers). `inspect.getsource` raises
  `OSError`/`TypeError` on a bytecode-only install, and `install()` runs in `CoreConfig.ready()`. Both source
  probes now go through `_source()`, which logs and returns `""`, so the shim is skipped and boot continues. New
  test `test_unreadable_source_skips_the_shim_instead_of_failing_startup`. It fails without the guard (mutation
  check).
- **The Django guard had no lower bound.** Before 6.1, `quote_name_unless_alias()` left aliases unquoted, so the
  taggit shim would change the SQL there. The guard is now `(6, 1) <= django.VERSION < (7, 0)`. New test.
- **The Wagtail probe matched the substring `get_connection(`**, so `mailers.get_connection(` or a docstring
  would keep the shim after upstream fixed the call. It is now a regex for a bare call. New test.
- The log messages now carry the `[COMPAT]` prefix.
- Declined:
  - Sharing `mailers.default` across calls. Under MAILERS, Django 6.1's `get_connection()` already returned
    that same default mailer, so nothing changes.
  - A Django 7.0 bump silently skipping the shims. On 7.0 `install()` does nothing, and the "still needs its
    shim" tests are the signal: the 7.0 bump must re-check taggit and Wagtail, as the module docstring says.
  - The AC evidence above quotes executor-shutdown log noise as its last lines. The suite's summary line in the
    evidence file is `5139 passed, 8 skipped`, and the verifier re-ran it.

Tests: `test_django70_compat.py` plus the forum tag and topic-approval tests pass (83 passed). `apps/core/tests`,
`apps/forum_host` and `apps/blog/tests` pass (1202 passed, 7 skipped).

### 2026-10-12 - Review round 2: the 7.0 upper bound dropped, the rest declined (owner decision: no new todos)

Round 2 found nothing blocking.

- **Fixed:** the shims turned themselves off on Django 7.0. That is where taggit 6.1.0's `quote_name_unless_alias()`
  and Wagtail's `get_connection()` stop existing, so it is exactly where the shims matter. The "still needs its
  shim" tests would then have told the 7.0 bump "upstream fixed, delete the shim". `_django_needs_shims()` is now
  `VERSION >= (6, 1)`. `quote_name()` and `mailers.default` both exist on 7.0, and the source probes switch each
  shim off once upstream stops calling the removed API. The version test asserts 7.0 → on.
- Declined:
  - **A shared `mailers.default`** (raised by 3 reviewers). In Django 6.1, `MailersHandler.default` is a
    property that returns `self[alias]`, which is `create_connection(alias)`: a new connection on every access,
    the same as the deprecated `get_connection()`. Nothing is shared.
  - **Source probing at every boot.** It is one file read per process, and it is what lets a fixed upstream
    switch its shim off.
  - **The idempotency test could capture the originals more tightly.** It is a test-strength nit, and the
    `current is shim` guard already short-circuits a second install.

Tests: `test_django70_compat.py` plus the forum tag and topic-approval tests pass (83 passed).
