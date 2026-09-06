---
status: pending
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
narrowed on purpose during todo 354, because running the guard across
`apps/*/services/*.py` failed on seven files and the PR could not own them all.

## Findings

Widening it to `apps/*/services/*.py` today fails on:

| File | Why it fails | Real leak? |
| --- | --- | --- |
| `garden_calendar/services/weather_service.py` | raw `{e}` in a requests handler | **was** — fixed in #670 (todo 354 slice 1); this row should disappear once that merges |
| `plant_identification/services/plant_health_service.py` | raw `{str(e)}` | No — `Api-Key` **header** auth, so the URL carries no credential |
| `plant_identification/services/plant_id_service.py` | raw `{e}` | No — `Api-Key` header |
| `plant_identification/services/unsplash_service.py` | raw `{str(e)}` | No — `Authorization: Client-ID` header |
| `plant_identification/services/pexels_service.py` | raw `{str(e)}` | No — `Authorization` header |

So five of the seven are **header-authenticated and safe today**. They are not
harmless, though: the exception message still writes the full request URL —
including any query string a future change adds — into the log. The guard is
what would catch that change.

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

- [ ] The guard is parametrised over every `apps/*/services/*.py`, with no
      hardcoded file list
- [ ] Every service it now covers uses `log_safe_api_error()` in its
      `requests` handlers
- [ ] `embeds.py` is either covered or has a written reason it is not
- [ ] Mutation check: reintroducing a raw `{e}` in any covered file fails the
      guard

## Notes

p3: no known live leak remains after todo 354 — the four that existed are
closed. This is about making the guarantee structural instead of resting on
"the key happens to be in a header today".
