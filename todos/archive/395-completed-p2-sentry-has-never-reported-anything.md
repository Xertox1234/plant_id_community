---
status: completed
priority: p2
issue_id: "395"
tags: [observability, ops, production, security, tech-debt]
dependencies: []
source_review: "todos/393-pending-p2-plant-id-provider-failure-is-silent.md"
---

# A local stub shadows sentry-sdk, so nothing has ever reached Sentry

## Problem

`backend/sentry_sdk.py` is five lines:

```python
# Minimal test stub for sentry_sdk to avoid hard dependency during local tests


def init(*args, **kwargs):
    return None
```

`backend/` is the Django project root and therefore on `sys.path`, so
`import sentry_sdk` resolves to **this file**, not to the real
`sentry-sdk==2.68.1` that `requirements.txt` pins and that is installed in the
venv. Every knob in `settings.py:1183-1199` — DSN, `traces_sample_rate`,
`profiles_sample_rate`, `environment`, `release` — is passed to a function whose
entire body is `return None`.

**No error, trace or profile this project has ever produced has reached Sentry.**
The stub predates almost everything else: it arrives in `763028fa`, the initial
backend commit.

There is no missing dependency to avoid. The real package is declared and
installed.

## Findings

Verified 2026-09-14 under Django's own entrypoint, not by reading:

```text
$ DJANGO_SETTINGS_MODULE=plant_community_backend.settings python -c "
  import django; django.setup(); import sentry_sdk; print(sentry_sdk.__file__)"
/Users/.../backend/sentry_sdk.py
has capture_message: False
init() returns: None
```

### Deleting the stub, on its own, breaks production startup

This is the part that makes the fix non-obvious, and it is why the stub must not
simply be removed. `settings.py:1195` passes `request_bodies="medium"`. That
option **was removed in sentry-sdk 2.x** (renamed `max_request_body_size`), and
the real SDK rejects an unknown option rather than ignoring it:

```text
$ python -c "import sentry_sdk; sentry_sdk.init(dsn='https://public@example.invalid/1',
                                                request_bodies='medium')"
TypeError: Unknown option 'request_bodies'
```

`sentry_sdk.init()` runs at import time inside `settings.py`, guarded only by
`if SENTRY_DSN and not DEBUG`. So removing the stub while `SENTRY_DSN` is set in
production means **Django fails to start**. The stub has been masking a config
incompatibility for as long as it has been masking Sentry.

### `SENTRY_DSN` is not set in production, so the fix alone changes nothing

Checked 2026-09-14 against the Railway `plant_id_community` service — variable
**names** only, no values. The service has 40 variables and `SENTRY_DSN` is not
among them.

Two consequences, and they reorder this todo:

- Deleting the stub, by itself, changes **nothing at runtime**. `init()` is
  guarded by `if SENTRY_DSN and not DEBUG`, so it is never reached. The real
  question is not "fix the stub" but **"do we want error reporting at all?"** —
  which is a spend-and-privacy decision, not a code cleanup.
- The startup-crash landmine is therefore **not armed today**, and arming it is
  a one-variable action by someone who will have no idea. Setting `SENTRY_DSN`
  *now* is a harmless no-op; setting it *after* the stub is removed but before
  the `request_bodies` fix **crashes Django at boot**. Do steps 1 and 2 in the
  same commit, never separately.

### `request_bodies="medium"` contradicts the setting two lines above it

`send_default_pii=False` is set deliberately, with the comment *"Don't send
personally identifiable information"*. Shipping POST/PUT bodies sends login and
registration payloads to a third party, which is the same data by another route.
The replacement should be `max_request_body_size="never"`, or the option should
be dropped — not mechanically renamed.

### Consequence for todo 393

Todo 393 AC 4 asks that a sustained primary-provider failure "raise something a
human sees". The alert is written and wired
(`circuit_monitoring._alert`, fired when the circuit OPENS after `fail_max`
consecutive failures) but it is **guarded and currently inert**, because the
stub has no `capture_message` and calling it would raise AttributeError inside a
circuit-breaker listener — turning "the provider is down" into "the provider is
down and the listener crashed". Until this todo lands, AC 4 is satisfied by a
threshold **log line** only. `test_the_stub_shadows_the_real_sentry_package`
pins the diagnosis so it cannot be closed on a guess.

## Recommended Action

1. Delete `backend/sentry_sdk.py`.
2. In `settings.py`, replace `request_bodies="medium"` with
   `max_request_body_size="never"` (decide deliberately — see above; do not just
   rename it).
3. Confirm `SENTRY_DSN` is actually set on the Railway `plant_id_community`
   service. If it is not, this todo changes nothing at runtime and the real
   decision is whether to configure Sentry at all.
4. Verify the way this was found — under `django.setup()`, asserting
   `sentry_sdk.__file__` lands in `site-packages`, not in `backend/`.
5. Trigger one real error in a non-production environment with a DSN set and
   confirm the event arrives. A green startup proves only that `init()` did not
   raise.
6. Update `test_the_stub_shadows_the_real_sentry_package` in
   `apps/plant_identification/tests/test_provider_failure_visibility.py` — it is
   written to FAIL when this is fixed, deliberately, so the fix cannot go
   unnoticed. Remove the `_alert` guard in the same change.

## Acceptance Criteria

- [x] `backend/sentry_sdk.py` is gone and `import sentry_sdk` resolves into
      `site-packages` under `django.setup()`, asserted by a test
      — **2026-09-14.** Deleted. Under `django.setup()` the import now resolves
      to `venv/lib/python3.13/site-packages/sentry_sdk/__init__.py`
      (2.68.1, `capture_message` present). Asserted from two directions so a
      convenience stub cannot come back:
      `apps/core/tests/test_sentry_options_drift.py::test_no_local_module_shadows_the_real_sentry_sdk`
      and `test_provider_failure_visibility.py::test_no_local_stub_shadows_the_real_sentry_package`.
      Both assert the *resolved module is outside the project root* rather than
      that one known path is absent — the failure mode is "a local file shadows
      an installed package", not "this particular file exists".
- [x] `settings.py` passes only options the installed SDK accepts, and Django
      starts with `SENTRY_DSN` set and `DEBUG=False` — verified by actually
      starting it, not by reading the signature
      — **2026-09-14, booted both ways:**
      `manage.py check` with `SENTRY_DSN` unset → *System check identified no
      issues*. With `DEBUG=False SENTRY_DSN=https://public@example.invalid/1` →
      *System check identified no issues*, **and** urllib3 logged three retries
      of `POST /api/1/envelope/` to `example.invalid`. That envelope attempt is
      the real evidence: the SDK initialised and tried to transmit, which the
      stub could never do. Counterfactual checked in the same session — putting
      `request_bodies="medium"` back while the stub is gone raises
      `TypeError: Unknown option 'request_bodies'` at import time inside
      settings, confirming the two changes must ship in one commit.
      A drift guard now parses the `sentry_sdk.init()` call out of `settings.py`
      with `ast` and asserts every keyword is in
      `sentry_sdk.consts.DEFAULT_OPTIONS` (73 options), so the next SDK major
      cannot re-arm this quietly. It reads the source rather than calling
      `init()`, which would need a DSN and a live transport.
- [x] The request-body decision is explicit: bodies are either off
      (`max_request_body_size="never"`) or on with a stated reason that
      reconciles with `send_default_pii=False`
      — **Off, deliberately.** `max_request_body_size="never"`. POST/PUT bodies
      carry login and registration payloads, which is the same data
      `send_default_pii=False` exists to keep out of a third party; shipping
      them would have contradicted the comment two lines above. Both halves are
      pinned by `test_request_bodies_are_off_and_stay_off`, which fails if
      either the body size or the PII flag is flipped — the decision is
      asserted, not left to the next reader.
- [x] One deliberately-triggered error is confirmed **received** in the Sentry
      project, with the date and what was seen recorded here
      — **2026-09-14 (event 2026-09-15T02:41Z UTC): RECEIVED.** Project `houseplant-md-backend` created in the
      `ocrecipes-wx` org (Django platform, team `#ocrecipes`), DSN set on Railway,
      deploy `a8c2e634` SUCCESS. Trigger: `POST /api/v1/security/csp-report/`
      with a JSON **array** body, so `request.data.get()` raises `AttributeError`
      inside `csp_report_view`'s `try`. Chosen deliberately over adding a debug
      route — it is anonymous, CSRF-exempt, writes nothing, returns 400, and
      needed no code shipped to production to test production.
      Confirmed at all three layers rather than just the last:
      **HTTP** 400; **Railway log** `[CSP] Report parsing error: 'list' object
      has no attribute 'get'` at `apps/core/views.py:170`, severity `error`;
      **Sentry** issue `HOUSEPLANT-MD-BACKEND-1`, event `05c67f83`, the first
      event this project has ever received — `level: error`, `handled: --`,
      transaction `/api/v1/security/csp-report/`, full stack trace,
      **`environment: production`** and **`release: 1.0.0`**, CPython 3.13.15.
      Those last two matter: they are `settings.py` values arriving intact, so
      this proves the real SDK config reached Sentry, not merely that *something*
      did. The issue is left unresolved in Sentry as the audit trail.
      Note the capture path was the **logging integration** (`logger.error` in an
      `except`), not an unhandled exception — which is also the path
      `circuit_monitoring._alert()` depends on, so todo 393's alert now has a
      live destination.
- [x] Whether `SENTRY_DSN` is set in production is recorded here (boolean only,
      never the value)
      — **2026-09-14: NOT set.** Railway `plant_id_community`, production,
      40 variables, no `SENTRY_DSN`. Read as names-only; no value was fetched.
      — **2026-09-14: IT IS NOW SET.** Same service and environment, alongside
      `SENTRY_TRACES_SAMPLE_RATE=0` and `SENTRY_PROFILES_SAMPLE_RATE=0`. Both
      sampling rates default to `0.1` in `settings.py`, so setting the DSN alone
      would have started shipping 10% of transactions as traces *and* profiles
      into a quota shared with `ocrecipes-mobile` — operator chose error-only,
      raiseable later with one variable and no code change. Still recorded as a
      boolean: the value was written, never read back or printed.
- [x] A decision is recorded on whether this project wants Sentry at all. If
      not, delete the stub AND the `settings.py` block AND the `sentry-sdk`
      pin, rather than leaving dead configuration that reads as working
      observability
      — **2026-09-14, operator decision: keep Sentry wired, do not enable it
      yet.** The `settings.py` block and the `sentry-sdk==2.68.1` pin stay. The
      alternative on the table was ripping all three out; it was declined
      because the circuit-open threshold alert wants a destination. This is
      explicitly *not* "Sentry is on": with no DSN, `init()` is never called and
      `capture_message` is a no-op, so no data leaves the service and there is
      no spend. What changed is that setting the DSN is now a one-variable
      action that works, instead of one that crashes Django at boot.
- [x] Todo 393's `_alert` guard is removed and its two stub-pinning tests are
      updated, so AC 4 of that todo becomes genuinely met
      — **Done, with one deliberate deviation.** The `getattr(sentry_sdk,
      "capture_message", None)` check is gone; it existed only because the stub
      lacked the attribute. The *protection* is kept as a `try/except`, because
      the invariant it enforces is permanent and independent of which SDK is
      imported: `_alert` runs inside a circuit-breaker listener, so an
      exception there turns "the provider is down" into "the provider is down
      and the listener crashed", taking the circuit-open log line with it. Only
      the exception **type** is logged — a Sentry exception message can quote
      the DSN, which carries a key. Both tests were inverted rather than
      deleted, so the same lines that proved the bug now prove it is gone.
      **Todo 393 AC 4 is still not checked** — see the note added there. The
      gap moved from "the SDK is fake" to "no DSN is configured", which is
      smaller and is an operator action, but it is still nobody being reached.

## Verification

- `pytest apps/core/ apps/plant_identification/` → **1562 passed** (75s).
  App-scoped runs are a false green here; the repo-wide guards live in
  `apps/core/tests/`.
- `scripts/check_log_prefixes.py --app plant_identification --fail-over 0` →
  0 unprefixed of 276.
- `scripts/check_archived_todo_status.py --fail-over 0` → green.
- **Mutation check: 8 mutants, 8 caught.** Re-add the stub; restore
  `request_bodies="medium"`; turn request bodies on; flip `send_default_pii`;
  hardcode `traces_sample_rate`; drop the `_alert` guard; swallow the alert
  failure silently; log the exception message instead of its type. The two that
  first reported a bare exit code were re-run and confirmed to fail on the real
  assertion, not on a SyntaxError or ImportError standing in for one.

## Notes

**Priority p2.** Nothing is broken *right now* in the sense of user-visible
behaviour — but every alerting and error-reporting assumption anyone has made
about this project for its entire history is false, including todo 393's, and
the fix carries a startup-crash landmine that will look like an unrelated deploy
failure to whoever trips it.

Found 2026-09-14 while implementing todo 393 AC 4, by trying to `patch.object`
`sentry_sdk.capture_message` in a test and getting `AttributeError: module
'sentry_sdk' from '.../backend/sentry_sdk.py' does not have the attribute`.
The stub announced itself only because a test reached for an attribute the real
package has and the stub does not.

Related: todo 393, `backend/plant_community_backend/settings.py:1183-1199`,
`backend/apps/plant_identification/circuit_monitoring.py`.
