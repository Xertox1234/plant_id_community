---
status: pending
priority: p3
issue_id: "366"
tags: [security, dependencies, suppressions, backend]
dependencies: []
---

# Re-assess the two dormant pip-audit suppressions at their 2026-11-16 expiry

> **Sweep agents: do NOT run this todo through `completing-todos`, `todo-next`,
> or `todo-batch`.** Those skills flip `pending` → `in_progress` and `git mv` the
> filename at the *start* of a run, then archive at the end. All three discover
> via `grep -l "^status: pending" todos/*.md`, so `in_progress` is as invisible to
> them as `blocked` is — a half-run would drop this todo out of every later sweep
> while leaving the suppressions pointing at it.
>
> **Archiving this todo fails `Harness CI` until both entries in
> `.github/security-suppressions.yml` are repointed or deleted.** That is by
> design, not a bug — see `scripts/test_check_suppressions.py`'s
> `test_real_file_tracked_by_todos_are_all_open`. Do the repoint/delete in the
> same commit as the archive, or the required check goes red on every open PR.

## Problem

Two entries in `.github/security-suppressions.yml` need a dated re-assessment
they cannot get on their own. Both were inherited from todo 355 (the dependency
epic) when it closed on 2026-09-07; 355 was archived, and a suppression whose
`tracked_by` points at a closed todo is the todo-089 failure this whole
mechanism exists to prevent.

Neither entry currently suppresses anything — `pip-audit` reports neither id —
but they were deliberately kept rather than deleted, because one day's OSV/
pip-audit data is not grounds for dropping a written assessment. They carry
`expires: 2026-11-16`; this todo is the thing that has to exist on that date.

## Findings

The two entries, verbatim from `.github/security-suppressions.yml`:

| id | package | pinned | `added` | `expires` | Currently reported by pip-audit? |
|---|---|---|---|---|---|
| `PYSEC-2026-89` | Markdown | 3.8.1 | 2026-05-20 | 2026-11-16 | **No** |
| `PYSEC-2025-183` | PyJWT | 2.13.0 | 2026-05-20 | 2026-11-16 | **No** |

- `PYSEC-2026-89` — no upstream fix (OSV: all versions affected); `markdown` is
  not imported by app code and the DoS path is unreachable.
- `PYSEC-2025-183` — supplier-disputed; mitigated by `JWT_SECRET_KEY` (the
  `SIMPLE_JWT` `SIGNING_KEY` PyJWT signs with), validated `>=50` chars fail-fast
  at settings import in **all** environments
  (`backend/plant_community_backend/settings.py:658`).
- Both `added`/`expires` windows sit at **exactly** the 180-day
  `policy.max_expiry_days` ceiling. Pushing `expires` out alone trips
  `--validate`; a renewal must move `added` forward too.
- `--recheck` cannot flag a suppression that matches no advisory — it only fires
  when the id **is** in the report with a fix. So nothing will surface these
  before `expires`. That is what the date is for.

## Recommended Action

On or before **2026-11-16**, for each of the two entries:

1. Query OSV at the pinned version and run the local audit:

   ```bash
   cd backend && pip-audit -r requirements.txt \
     ${=$(python3 ../scripts/check_suppressions.py --emit-flags)}
   ```

   (The `${=...}` is required — zsh does not word-split an unquoted `$VAR`, and
   without it pip-audit gets one argument and silently audits nothing.)
2. Decide one of three outcomes and record which, with evidence:
   - **A fix shipped** → bump the pin, delete the entry.
   - **Still no fix and still unreachable** → renew, moving **both** `added` and
     `expires` (the 180-day ceiling), and refresh `reason` with that day's data.
   - **The advisory is withdrawn, or the package is gone** → delete the entry.
3. If any entry is deleted, check whether this todo still has a job. If both go,
   archive this todo **in the same commit** — otherwise `Harness CI` goes red.

## Technical Details

- Suppression data: `.github/security-suppressions.yml` (`:47`, `:63` carry
  `tracked_by: "366"`).
- Checker: `scripts/check_suppressions.py` — `--emit-flags` (generates the
  workflow's `--ignore-vuln` flags), `--validate` (schema/policy, PR-safe),
  `--recheck` (expiry + shipped-fix + closed-`tracked_by`, schedule/dispatch only
  via `.github/workflows/security-scan.yml:86`).
- Tests: `scripts/test_check_suppressions.py`, run at
  `.github/workflows/harness-ci.yml:78` — a **required** check with no path
  filter on `pull_request`.
- The guard that makes archiving loud rather than silent:
  `test_real_file_tracked_by_todos_are_all_open`.

## Acceptance Criteria

- [ ] Each of `PYSEC-2026-89` and `PYSEC-2025-183` is bumped, renewed with a
      fresh dated rationale, or deleted — with the command output that justified
      the choice recorded in the Work Log
- [ ] `python3 scripts/check_suppressions.py --validate` passes
- [ ] `python3 scripts/test_check_suppressions.py` passes, including the
      `tracked_by`-is-open guard
- [ ] If both entries are removed, this todo is archived in the same commit and
      `Harness CI` is green on the PR

## Work Log

### 2026-09-07 - Filed during todo 355 slice 6 (closeout)

- Todo 355 was archived, so its two surviving suppressions needed a live owner.
  Repointed `tracked_by: "355"` → `"366"` at `.github/security-suppressions.yml`
  `:47` and `:63`. No other field changed — not `added`, not `expires`, not
  `reason`.
- Keeping rather than deleting follows 355's 2026-09-06 *Decisions locked* block:
  "left in place and re-assessed at their `expires: 2026-11-16` … that is one
  day's data, not grounds for deletion."

## Notes

p3: neither suppression hides an advisory today, so there is no live exposure —
the cost of ignoring this is a stale assertion in a security file, not an open
CVE. The `expires: 2026-11-16` date is the real deadline; `--recheck` hard-fails
the scheduled scan the day after.

Related: todo 355 (dependency epic — archived 2026-09-07), todo 089 (the
closed-tracking-pointer failure this mechanism exists to prevent).
