---
status: pending
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

- [ ] `backend/sentry_sdk.py` is gone and `import sentry_sdk` resolves into
      `site-packages` under `django.setup()`, asserted by a test
- [ ] `settings.py` passes only options the installed SDK accepts, and Django
      starts with `SENTRY_DSN` set and `DEBUG=False` — verified by actually
      starting it, not by reading the signature
- [ ] The request-body decision is explicit: bodies are either off
      (`max_request_body_size="never"`) or on with a stated reason that
      reconciles with `send_default_pii=False`
- [ ] One deliberately-triggered error is confirmed **received** in the Sentry
      project, with the date and what was seen recorded here
- [x] Whether `SENTRY_DSN` is set in production is recorded here (boolean only,
      never the value)
      — **2026-09-14: it is NOT set.** Railway `plant_id_community`, production,
      40 variables, no `SENTRY_DSN`. Read as names-only; no value was fetched.
- [ ] A decision is recorded on whether this project wants Sentry at all. If
      not, delete the stub AND the `settings.py` block AND the `sentry-sdk`
      pin, rather than leaving dead configuration that reads as working
      observability
- [ ] Todo 393's `_alert` guard is removed and its two stub-pinning tests are
      updated, so AC 4 of that todo becomes genuinely met

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
