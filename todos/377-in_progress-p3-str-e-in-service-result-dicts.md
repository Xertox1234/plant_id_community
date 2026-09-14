---
status: in_progress
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

- [x] Each of the five sites is either converted or recorded as unreachable
      with the trace that proves it
- [x] If the guard is extended, a planted-violation test pins the new shape the
      way `test_the_guard_flags_a_planted_violation` pins the logger shapes

## Notes

p3: no live exposure — the two reachable sites were closed by todo 354, and
these five sit behind no anonymous view today. This is about the class not
being structurally closed, which is the same reason todo 358 existed.

### 2026-09-13 - All five converted; guard extended (PR pending review)

**Reachability traced first, for all five.** None is reachable from a client
today -- and all five were converted anyway, because "unreachable" is a property
of today's wiring and three of these are live code paths a future view would
expose:

| Site | Trace | Verdict |
| --- | --- | --- |
| `plant_health_service.py:396` | only caller is `DiseaseDiagnosisService.get_service_status` (:517), which has no view and no URL | unreachable today |
| `disease_diagnosis_service.py:545` | same method, same absence of a view | unreachable today |
| `disease_diagnosis_service.py:350` | `diagnose_disease_from_request` **is** called, from `views.py:676` and `:755` -- but **neither passes `progress_cb`**, so the callback is `None` and the branch never runs | unreachable today, one argument away |
| `plant_image_service.py:303` | `batch_process_plants` has **zero callers** repo-wide | dead code |
| `blog/ai_integration.py:444` | `BlogAIIntegration` is referenced nowhere outside its own module and its tests | dead code |

Each now logs the detail and returns a constant. `plant_health_service` uses the
`isinstance(exc, requests.RequestException)` branch that `plantnet_service.py:588`
and `trefle_service.py:527` already use, so a non-HTTP error keeps its traceback.

**The guard was extended, and the todo's design tension turned out not to
exist.** The worry was that a dict-literal sink rule would fire on every
internal-only service result. Measured before deciding: across **582 files**
under `ROOTS`, the predicate "exception bound name reaching a dict value under an
error-ish key, inside an `except` handler" matched **exactly 5 sites -- the same
5 this todo names -- and 0 in test files**. After the conversions it matches 0.
Narrowing the sink to an *error-ish key* rather than any dict value is what buys
that precision.

`test_no_response_dict_carries_its_exception` parametrises over **every** backend
file, not only those catching a `requests` exception: all five real sites were
`except Exception`, which catches a `RequestException` perfectly well, so
restricting by handler type would have caught none of them.

The rule is **strict -- no allowlist at all**, unlike the logger guard.
`type(e).__name__` leaks an internal class name and `e.response.text` leaks the
provider's body; neither belongs in a payload, and nothing in the tree now needs
an exception in a response. The planted specimen pins both as violations.

Verification:

| Check | Result |
| --- | --- |
| sites matching the predicate, before / after | **5 / 0** |
| `pytest test_requests_exception_drift.py` | **605 passed** |
| mutation: re-plant `"error": str(e)` in `plant_health_service.py` | guard **FAILED**, naming `line 408: str(e)` |
| file restored (`cp` from backup, then grep) | constant back: 1 occurrence; `str(e)`: 0 |
| `pytest apps/plant_identification apps/blog` | **395 passed, 7 skipped** |

Four pre-existing `F401` unused imports in `disease_diagnosis_service.py`
(`Tuple`, `Union`, `ContentFile`, `PlantSpecies`) were cleaned rather than
bypassed with `SKIP=flake8`. pre-commit lints the whole file that appears in a
staged diff, so touching one line surfaced them; each was confirmed to have zero
other references in the file before removal, and the module still imports and
its 122 tests still pass.

Left deliberately: `ai_integration.py:429` still interpolates `str(e)` into its
*log* line alongside `exc_info=True`. That is a log, not a response, and this
todo is about response dicts -- noted rather than swept.

## Review round 1 — the class was not closed

No defect in the five conversions: review confirmed no `except` clause was
narrowed (three dropped only the `as e` binding), the `error` key and its type
survive at every site, `success`/`status` still signal failure, and every site
still logs the real exception server-side. Caller contracts were traced and no
reader of `result["error"]` can KeyError.

But the PR's claim to close the class was **false**, in two ways.

**A sixth site, two branches above one that was converted.**
`plant_health_service.py:388` returned
`"error": f"HTTP {response.status_code}: {response.text[:100]}"` -- up to 100
characters of the provider's raw body, reaching the same merged `error` key that
`DiseaseDiagnosisService.get_service_status` returns. It is structurally
invisible to the drift guard: the value references `response`, not the bound
exception, so no `Name` node matches and `ast.walk` never triggers. Converted;
the status code stays (safe and useful), the body goes to the log.

**The guard now sees that shape.** `_provider_body_in_response_dicts()` scans
every response dict -- not only those inside an except handler, because this
leak sat in a plain `else:` branch -- for a `.text`/`.content`/`.body` attribute
on a `resp*` name under a response error key. Mutation-checked: restore the old
line and the new test fails on exactly that file; restore the fix and 1196 pass.

**And it no longer false-positives on structured logging.** The original walked
every dict inside the handler, including `logger.error(..., extra={...})` --
where exception detail *belongs*. `blog/ai_integration.py:438` already carries
that shape and escaped only because `error_type` is not in
`RESPONSE_ERROR_KEYS`; renaming it to `error` would have turned a correct commit
red. `_logging_extra_dicts()` now excludes them. Verified old vs new on the same
input: old FIRES, new quiet.

Discrimination check on five shapes -- logging `extra` quiet, `str(e)` in a
response fires, `response.text` in a response fires, `response.text` in a log
quiet, status-code-only quiet.

**The guard does not key on the receiver's name.** The first draft required
`"resp" in root.id.lower()`, which is a heuristic on variable naming -- `r.text`
or `http_result.text` walks straight past it. That is the same
correct-by-accident-of-today's-data shape this review round found three times
elsewhere, so it did not survive its own lesson. Any `.text`/`.content`/`.body`
under a response error key now counts. Measured: the whole backend still passes
(1196), so the wider rule costs no false positives, and it catches the two names
the heuristic missed.
