---
status: pending
priority: p3
issue_id: "377"
tags: [security, backend, plant-identification, blog]
dependencies: []
source_review: "todos/archive/358-completed-p3-widen-requests-exception-drift-guard.md"
---

# `str(e)` still reaches five service result dicts

## Problem

`docs/rules/security.md` bans `str(e)` in a **response body** as well as in a
log: it reaches the client, and for a `requests` exception it carries the
prepared URL. Todo 354 fixed the two sites an anonymous endpoint actually
reaches. Todo 358's drift guard cannot see the rest, because it only inspects
calls prefixed `logger.` — a `return {"error": str(e)}` is not a logger call,
the same structural gap as `raise SomeError(f"{e}")`.

## Findings

Five surviving sites, found by the todo 358 review (cross-cutting reviewer),
verified on the tree at that PR:

| Site | Shape | Reachable from a view today? |
| --- | --- | --- |
| `plant_identification/services/plant_health_service.py:396` | `"error": str(e)` in `get_service_status`'s `except Exception` | **No** — see reachability below |
| `plant_identification/services/disease_diagnosis_service.py:545` | `"error": str(e)` for a DB exception in `get_service_status` | **No** — same path |
| `plant_identification/services/disease_diagnosis_service.py:350` | `progress_cb("final_status", "failed", {"error": str(e)})` | Needs tracing — goes to a progress callback, not a return |
| `plant_identification/services/plant_image_service.py:303` | `results[name] = {"success": False, "error": str(e)}` | Needs tracing |
| `blog/ai_integration.py:444` | `"error": f"AI content generation failed: {str(e)}"` | Needs tracing |

**Reachability, traced not assumed.** The live anonymous endpoint is
`plant_identification/urls.py:115` → `service_status` (line 64) →
`PlantIdentificationService.get_service_status`
(`identification_service.py:42`), which merges **only** `trefle` and
`plantnet` — both already fixed in todo 354.
`DiseaseDiagnosisService.get_service_status` (line 517), the only caller of
`PlantHealthAPIService.get_service_status`, has no view and no URL. So nothing
in this table is anonymously reachable *today*; the first two become reachable
the moment disease-diagnosis status is wired to a view.

`plant_health` is the one worth noting: it is the sibling of the two that
leaked, in a file todo 358 already edited, and it was left alone deliberately
— fixing one of five arbitrarily is worse than tracking all five.

## Recommended Action

1. Trace the three "needs tracing" rows to a view or confirm they are internal.
2. Convert every site that can reach a client to `log_safe_api_error(e)` (or a
   generic string with the detail logged), matching the shape
   `plantnet_service.py:588` / `trefle_service.py:527` already use — they
   branch on `isinstance(exc, requests.RequestException)` so non-HTTP errors
   keep their traceback.
3. Consider whether the drift guard should grow a second predicate for
   `return`/dict-literal sinks. Note the design tension: the guard's value is
   that it is currently false-positive-free, and a dict-literal sink rule would
   fire on every internal-only service result. Decide deliberately rather than
   by default.

## Acceptance Criteria

- [ ] Each of the five sites is either converted or recorded as unreachable
      with the trace that proves it
- [ ] If the guard is extended, a planted-violation test pins the new shape the
      way `test_the_guard_flags_a_planted_violation` pins the logger shapes

## Notes

p3: no live exposure — the two reachable sites were closed by todo 354, and
these five sit behind no anonymous view today. This is about the class not
being structurally closed, which is the same reason todo 358 existed.
