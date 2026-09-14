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

`services/monitoring_service.py` already tracks API dependency health, so there
is somewhere obvious for this to live.

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
- [ ] A Plant.id failure is visible: a distinct log line (bracketed prefix, per
      `docs/rules/api.md`) that names WHY the provider returned nothing —
      credit-blocked, auth-rejected, timeout — rather than the current silence
- [ ] Sustained primary-provider failure raises something a human sees, wired
      into `services/monitoring_service.py`'s existing API-dependency tracking.
      A threshold, not a per-request alert
- [ ] The response makes provider degradation legible to the client: when
      `source` is absent or `disease_detection` is null because the provider
      failed (not because the plant is healthy), the API says so rather than
      returning a quietly thinner payload

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
