---
status: pending
priority: p2
issue_id: "393"
tags: [plant-identification, ops, billing, monitoring, production]
dependencies: []
source_review: "todos/390-pending-p3-plant-id-key-rotation-unverified.md"
---

# A Plant.id outage is invisible: the provider can fail completely and nothing says so

## Problem

The Plant.id key rotated into production on 2026-09-13 (todo 390) authenticates
but **cannot perform a single identification**. Measured directly against the
vendor:

```text
GET https://plant.id/api/v3/usage_info      -> HTTP 200
{
  "active": true,
  "credit_limits":   { "day": null, "week": null, "month": null, "total": 0 },
  "used":            { "total": 0.0 },
  "remaining":       { "total": 0.0 },
  "can_use_credits": { "value": false,
                       "reason": "The specified api key does not have
                                  sufficient number of available credits." }
}
```

The key is valid; the account behind it has no credits attached. This is a
billing/plan action at <https://web.plant.id/>, not a code fix.

## Findings

### Production is degraded, not down — and nothing says so

`apps/plant_identification/services/combined_identification_service.py:217-245`
calls both providers in parallel and merges whatever comes back:

```python
plant_id_results, plantnet_results = self._identify_parallel(image_data)

if plant_id_results:                      # <- silently skipped when Plant.id fails
    results["primary_identification"] = plant_id_results
    results["disease_detection"] = plant_id_results.get("health_assessment")
    results["confidence_score"] = plant_id_results.get("confidence", 0)
    results["source"] = "plant_id"

if plantnet_results:
    results["care_instructions"] = self._extract_care_info(plantnet_results)

results["combined_suggestions"] = self._merge_suggestions(...)
if not results["combined_suggestions"]:   # error ONLY if BOTH providers fail
    results["error"] = "Unable to identify plant. ..."
```

So with Plant.id credit-blocked and PlantNet healthy:

| Feature | State |
| --- | --- |
| `combined_suggestions` | still populated, from PlantNet |
| `care_instructions` | still populated, from PlantNet |
| `primary_identification` | **never set** |
| `confidence_score` | **never set** |
| `source` | **never set** (not `"plant_id"`, not anything) |
| `disease_detection` / health assessment | **never set — Plant.id-only feature** |
| User-visible error | **none** |

Disease diagnosis is a headline feature of this product and it is currently off
in production with no error surfaced to the user and no alert to anyone.

### The detection gap is the durable half

The credits can be topped up in minutes. What should not be left as-is is that
a **total** failure of the primary identification provider produces no signal:
no error, no metric, no log line that distinguishes "Plant.id declined" from
"Plant.id was never asked". The only reason this was caught at all is that the
rotation happened to be verified against `/usage_info` by hand.

~~`services/monitoring_service.py` already tracks API dependency health, so there
is somewhere obvious for this to live.~~ **Wrong — corrected 2026-09-14.** It
tracks Trefle and nothing else: `record_api_call` has exactly one caller
(`trefle_service.py`), and `CACHE_KEYS`/`RATE_LIMITS` have no `plant_id` entry
at all, so `record_api_call("plant_id", ...)` raises `KeyError` today. Building
there would mean a second counter beside an unused one. The real home is
`circuit_monitoring.py`, which already implements a threshold rather than a
per-request signal — see the 2026-09-14 work-log entry.

### A second silent failure, independent of the one above

Found while implementing this. `health_assessment` is a **separate Plant.id
endpoint** (`plant_id_service.py:378-393`) and its failure was caught, logged at
warning, and discarded:

```python
except Exception as e:
    logger.warning(f"[HEALTH] Health assessment failed: {e}, continuing ...")
```

So identification can succeed, `source` can be `"plant_id"`, and disease
detection can still be off — a different path to the same missing feature. Worse,
it made `disease_detection: null` mean two incompatible things at once ("this
plant is healthy" and "nobody answered"), and by the time the combined service
saw the null, the reason was gone. **This changes what AC 2 proves**: a
successful identification does not by itself demonstrate that disease detection
works, which is why AC 2 asks for a non-null `disease_detection` specifically.

### A partial API key was reaching the logs

`CircuitMonitor.failure` logged `str(exception)[:100]`. `requests` builds its
message from the **prepared URL** and PlantNet sends its credential as the
`api-key` query parameter (`plantnet_service.py:251`). Truncating to 100
characters is not redaction — measured against a 22-character key:

| Error | Key characters in the log |
| --- | --- |
| 429 Too Many Requests, `/v2/identify/all` | 3 of 22 |
| 404 Not Found, `/v2/identify/all` | 11 of 22 |
| 401 Unauthorized, `/v2/projects` | 12 of 22 |
| 403 Forbidden, `/v2/projects` | 15 of 22 |

The bound is URL length, not design. `log_safe_api_error` exists for exactly
this and its own docstring describes the hole — *"every 4xx/5xx from either used
to log the key"* — but the hardening was applied to the call sites inside the
services and missed this listener, which sits behind **both** of them. Fixed
here because this todo is about how provider failures get logged.

## Recommended Action

1. **Attach credits to the new key** at <https://web.plant.id/> (or move it onto
   the funded plan the previous key was on). Confirm with:

   ```bash
   python3 - <<'PY'
   import re, json, pathlib, urllib.request
   key = re.search(r'^PLANT_ID_API_KEY=(\S+)',
                   pathlib.Path("backend/.env").read_text(), re.M).group(1)
   req = urllib.request.Request("https://plant.id/api/v3/usage_info",
                                headers={"Api-Key": key})
   d = json.loads(urllib.request.urlopen(req, timeout=30).read())
   print("remaining:", d["remaining"]["total"], "| can_use:", d["can_use_credits"]["value"])
   PY
   ```

   It prints only counts, never the key.

2. **Then** run one real identification through the app and confirm
   `source == "plant_id"` and a non-null `disease_detection`.

3. **Close the detection gap** so this cannot recur silently — see AC 3-4.

## Acceptance Criteria

- [x] `remaining.total > 0` and `can_use_credits.value == true` for the live key
      — recorded in this file with the date and the observed numbers
      — **2026-09-13:** `active: true`, `credit_limits.total: 86`,
      `remaining.total: 86.0`, `can_use_credits.value: true`. Credits were
      reassigned from the old Plant.id project to the new Houseplant MD project.
      This covers production as well as local: both were written from the same
      piped value in one `&&` chain, so they are the same bytes.
- [ ] One real identification through production returns `source == "plant_id"`
      with a non-null `disease_detection`, recorded here
- [x] A Plant.id failure is visible: a distinct log line (bracketed prefix, per
      `docs/rules/api.md`) that names WHY the provider returned nothing —
      credit-blocked, auth-rejected, timeout — rather than the current silence
      — `provider_failures.classify_provider_failure` turns an exception into a
      stable token (`auth-rejected`, `payment-required`, `rate-limited`,
      `timeout`, `connection-error`, `circuit-open`, `response-malformed`,
      `executor-timeout`, `http-<status>`), and a partial failure now emits
      `[DEGRADED] Identification ran with a failed provider: plant_id=<reason>
      | disease_detection=<status>`. **Deliberately NOT "credit-blocked":**
      which status Plant.id returns on credit exhaustion has never been
      observed — the account was funded before any identification ran against an
      empty one — so unmapped statuses become `http-<status>`, always specific
      and never a guess wearing a confident label. Add the mapping when a real
      credit block is seen, and record the observed status here.
- [ ] Sustained primary-provider failure raises something a human sees, wired
      into ~~`services/monitoring_service.py`'s existing API-dependency
      tracking~~ `circuit_monitoring.py`. A threshold, not a per-request alert
      — **Half done, and the honest half is stated rather than claimed.** The
      threshold is built and wired: the circuit opens only after `fail_max`
      consecutive failures, and `state_change` now fires `_alert()` there with
      the service name, the failure count and the last reason. What it cannot
      do yet is reach a person: `backend/sentry_sdk.py` is a five-line local
      stub that shadows the real `sentry-sdk==2.68.1`, so `sentry_sdk.init()`
      has always been a no-op and **nothing this project has ever produced has
      reached Sentry** (todo 395). Until that lands, this AC is satisfied by a
      threshold log line only. The alert call is guarded, because the stub has
      no `capture_message` and an unguarded call would raise AttributeError
      *inside a circuit-breaker listener* — alerting must never be able to break
      the failure path it reports on.
- [x] The response makes provider degradation legible to the client: when
      `source` is absent or `disease_detection` is null because the provider
      failed (not because the plant is healthy), the API says so rather than
      returning a quietly thinner payload
      — four **additive** fields, so the React and Flutter clients are
      unaffected until they choose to read them: `providers`
      (`{status, reason}` per provider, with `not_configured` distinguished from
      `failed` so a single-provider deployment is not permanently "degraded"),
      `degraded`, `disease_detection_status` (`"ok"` means the health assessment
      **ran** — a healthy plant is `"ok"` with `disease_detection: null`) and
      `disease_detection_reason`.

## Notes

**Priority: p2 as of 2026-09-13** (filed p1). Filed p1 because a core feature
was disabled in production at that moment. Credits were restored the same day,
so there is no outage now — but the reason it was p1 was never the billing, it
was the silence, and that is entirely unfixed. Downgraded because nothing is
currently broken, not because the remaining work got smaller.

Found while verifying the todo-390 rotation on 2026-09-13 — specifically by
checking `/usage_info` after swapping the key rather than assuming a valid key
is a usable key. **Sequencing lesson for the next rotation: verify the
replacement credential is usable BEFORE swapping it into production.** Here the
swap came first, so the previous value is no longer recoverable from Railway;
rolling back means fetching the old key from the vendor dashboard.

Related: todo 390 (the rotation and the dead exposed key),
`docs/patterns/domain/plant-identification.md`.

## Work Log

### 2026-09-13 - Credits restored; the billing half is closed

Reassigned from the old Plant.id project to the new Houseplant MD project.
Measured immediately after, against `backend/.env`'s key:

```text
active            : True
credit_limits     : {'day': None, 'week': None, 'month': None, 'total': 86}
used              : {'total': 0.0}
remaining         : {'day': None, 'week': None, 'month': None, 'total': 86.0}
can_use_credits   : True
```

86 rather than 100 because the free-tier month already had usage against the
previous key.

**What this does NOT close.** ACs 3-5 are the reason this was filed p1 and none
of them is affected by the credits: a total failure of the primary
identification provider still produces no error, no metric and no log line that
distinguishes "declined" from "never asked".
`combined_identification_service.py` still only errors when BOTH providers
return nothing. Had the credits not been noticed by hand during the rotation,
production would have run indefinitely with disease detection silently off.
That is the durable defect; the billing was a symptom.

AC 2 still needs one real identification through production confirming
`source == "plant_id"` and a non-null `disease_detection` — it requires an
authenticated request with an image, so it is a human step.

### 2026-09-14 - Detection gap closed (ACs 3 and 5); AC 4 half, AC 2 still human

The billing was the symptom; this is the defect. Four changes, all in
`apps/plant_identification/`:

- **`provider_failures.py` (new)** — `classify_provider_failure(exc)` returns a
  stable, greppable token. The design constraint is honesty: a token may claim
  only what the evidence supports, so only statuses whose meaning is fixed by
  HTTP itself are mapped and everything else becomes `http-<status>`. A wrong
  reason stated with authority is worse than the silence it replaces, because it
  sends the next person somewhere else entirely.
- **`ProviderOutcome`** — carries `(result, reason, configured)` out of
  `_identify_parallel`, which used to return bare `Optional[Dict]`s and throw the
  reason away. `result is None` could not distinguish "declined" from "never
  configured" from "never asked"; that ambiguity *was* the bug.
- **`plant_id_service.py`** — the swallowed `health_assessment` failure now
  travels as `health_assessment_error`, so `disease_detection: null` stops
  meaning two things at once.
- **`circuit_monitoring.py`** — threshold alert on circuit OPEN, and the
  credential leak in `failure()` fixed (see Findings).

**Verification.** 21 new tests; the full `apps/plant_identification` suite is
143 passed. 14 mutants applied to the new logic, all caught — including
"unconfigured counts as failed", "unmapped status guesses credit-blocked",
"credential redaction removed" and "alert guard removed". The caplog assertions
are written against the module logger because `apps.*` sets `propagate=False`.

**What is deliberately not done here.** Deleting the Sentry stub would switch on
live error reporting to a third party in production — an operator's call, not a
side effect of this todo — and it carries a startup-crash landmine
(`request_bodies` was removed in sentry-sdk 2.x; the real SDK raises
`TypeError: Unknown option`). Filed as todo 395 with the evidence.

**AC 2 remains open by choice.** One real identification through production
returning `source == "plant_id"` and a non-null `disease_detection` is the only
proof the rotated key can actually identify a plant — everything verified so far
was `/usage_info`, which only proves the key authenticates. Note the two
findings above: a successful identification and working disease detection are
now known to be *separate* things, so the AC needs both assertions, not one.
