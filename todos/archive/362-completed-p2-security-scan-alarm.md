---
status: completed
priority: p2
issue_id: "362"
tags: [security, ci, dependencies]
dependencies: ["355"]
---

# Scheduled security scan is failing (alarm issue #663)

## Problem

The weekly `security-scan.yml` run is red. The scan hard-fails on schedule by
design, but a scheduled-run failure blocks no PR and appears on no check list —
which is how it once failed 8 consecutive weeks unnoticed. This todo is the
bridge that puts the failure into the normal sweep.

Alarm issue: #663

## Findings

Filed from GitHub issue #663 (opened 2026-09-06) by
`scripts/sync_alarm_todo.py` on 2026-09-06. The issue body at the time:

---

**The scheduled security scan is failing.** This issue is opened and closed
automatically by `.github/workflows/security-scan.yml`.

| Job | Result |
|---|---|
| Backend Python Security Scan | `failure` |
| Frontend npm Security Scan | `success` |
| Flutter Dependency Security Check | `success` |

Latest run: <https://github.com/Xertox1234/plant_id_community/actions/runs/34052476158>
Last updated: 2026-09-06

---

### Alarm issue: #663

That line above is the dedupe key. To pull this failure into the todo sweep so
it gets worked like any other backlog item, run locally:

```
python3 scripts/sync_alarm_todo.py
```

CI cannot write the todo itself: this repo has
`default_workflow_permissions: read` with `can_approve_pull_request_reviews:
false`, so Actions cannot open a PR — and a `GITHUB_TOKEN`-created PR triggers
no workflows, so the required checks would never report and the PR would
deadlock.

### Why this issue exists

The scan is correct and has always hard-failed on schedule. What it lacked was
a consumer: a failed scheduled run blocks no PR and shows on no check list, so
it failed 8 weeks running without anyone seeing it. See
`docs/superpowers/plans/2026-09-05-security-backlog-multi-session.md`.

---

### Root cause — diagnosed 2026-09-06, not inherited from the issue

The alarm body above says only "Backend Python Security Scan: failure". The
actual cause was established by dispatching the workflow manually
(`gh workflow run security-scan.yml --ref main`, run 34052476158) and reading
the log. **It is a single advisory:**

```
Name   Version ID              Fix Versions
django 6.0.7   PYSEC-2026-3717 5.2.17, 6.0.8
```

The frontend npm job, which failed in earlier episodes, is now **green** — it
was cleared by the dependency work merged 2026-09-06 (#681/#683/#684/#686).
Only the backend job remains red, and only on this one package.

**Why Dependabot will never raise it — the part worth remembering.** At the
moment this scan fails, `gh api .../dependabot/alerts` returns **0 open
alerts**, and code scanning returns 0 too. The dashboards are clean while the
gate is red. That is not a bug in either: Dependabot resolves against **GHSA**,
`pip-audit` resolves against **PyPI/OSV**, and `PYSEC-2026-3717` exists in
PYSEC/OSV with no GHSA counterpart. So no Dependabot PR will ever appear for
it, and waiting for one is waiting forever. This is the concrete instance of
the rule already in `docs/rules/security.md` — "two advisory databases, two
answers — keep both scanners". Anyone triaging this by checking the alert count
first will conclude there is nothing to fix.

**It is already scoped.** `Django 6.0.7 → 6.0.8` is listed in
`todos/355-pending-p2-dependency-vulnerability-backlog.md` under **Slice 5 —
Backend transitive re-freeze**, bundled with `Twisted 25.5.0 → 26.4.0` and the
`cryptography` + `pyOpenSSL` pair. This todo therefore does **not** duplicate
that work; it exists so the *alarm* has an owner and cannot be forgotten if
slice 5 slips. Slice 5 landing should close both.

**Two suppressions ride on the same slice.** The workflow currently passes
`--ignore-vuln PYSEC-2026-89 --ignore-vuln PYSEC-2025-183` (Markdown, PyJWT).
Todo 355 notes the Twisted bump in slice 5 also clears the `CVE-2026-42304`
suppression. Re-run `python3 scripts/check_suppressions.py --validate` after
slice 5 so an expired-but-still-listed suppression does not turn the gate red
again for a different reason.

## Recommended Action

0. **Start from the known answer:** the only failing advisory is
   `django 6.0.7 → 6.0.8` (PYSEC-2026-3717), already scoped as todo 355
   Slice 5. Coordinate with that slice rather than bumping Django alone —
   355 pairs it with Twisted and the cryptography/pyOpenSSL pair, and a
   single-package bump in this repo has already failed on a transitive cap
   (`pyOpenSSL` capping `cryptography<49`).
1. If the failure has changed since filing, reproduce locally:
   `cd backend && pip-audit -r requirements.txt ${=$(python3 ../scripts/check_suppressions.py --emit-flags)}`
   and `cd web && npm audit --audit-level=moderate`.
   The `${=...}` matters — this project's shell is zsh, which does not
   word-split an unquoted `$VAR`, so without it pip-audit audits nothing.
2. For each advisory, **try a bump before suppressing** — an empty "Fix
   Versions" column does not mean unfixable (`docs/rules/security.md`).
3. Only if no bump clears it, add an entry to
   `.github/security-suppressions.yml` with `expires`, `owner`, `clears_when`
   and a `tracked_by` naming an OPEN todo. Never hand-add an `--ignore-vuln`
   flag to the workflow — it would bypass the expiry recheck.
4. Verify with `python3 scripts/check_suppressions.py --validate`.

## Technical Details

- Workflow: `.github/workflows/security-scan.yml` (weekly, Mondays 09:00 UTC)
- Suppression data: `.github/security-suppressions.yml`
- Checker: `scripts/check_suppressions.py`
- The alarm issue closes itself on the first green scheduled run.

## Acceptance Criteria

- [x] The scheduled `security-scan.yml` run is green — verified 2026-09-07
      00:04 UTC by `workflow_dispatch` run
      [34068576160](https://github.com/Xertox1234/plant_id_community/actions/runs/34068576160),
      `conclusion: success`. A dispatch takes the identical non-PR branches a
      `schedule` run takes at every decision point — pip enforcement
      (`security-scan.yml:69`), suppression `--recheck` (`:84`), the alarm
      (`:435`) and the gate (`:446`) all key on
      `github.event_name != 'pull_request'` — and `new-vuln-gate` is PR-only
      (`:263`), so it is skipped and cannot colour the result. The cron at
      Mon 2026-09-07 09:00 UTC is the independent confirmation; it will be the
      first green scheduled run since 2026-07-06.
- [x] Alarm issue #663 has auto-closed — `gh issue view 663` →
      `state: CLOSED`, `stateReason: COMPLETED`, `closedAt: 2026-09-07T00:04:19Z`.
      Closed by the machinery, not by hand: the summary job's alarm step logged
      `closed alarm issue #663`. This was the **first production execution of
      `security_alarm.sh`'s close branch (`:84-92`)** — the script shipped
      2026-09-05 and every run since had been a failure, so only the open/update
      branch had ever run.
- [x] Every advisory was fixed by a bump, or suppressed with an expiry and an
      open `tracked_by` todo — the one failing advisory (`PYSEC-2026-3717`) was
      fixed by a bump, not suppressed. `.github/security-suppressions.yml` was
      not touched; its two remaining entries (`PYSEC-2026-89`,
      `PYSEC-2025-183`) both carry `expires: 2026-11-16` and
      `tracked_by: "355"`, which is still `status: pending`.
- [x] `Django` is at `>= 6.0.8` in `backend/requirements.txt` — line 39 reads
      `Django==6.1.1`, landed by PR #695. 6.0.8 was skipped deliberately: the
      advisory patched the 6.1 branch too, and 6.1.1 shipped a day later
      carrying the same four CVE fixes. OSV confirms — `django 6.1.1` → `{}`,
      `django 6.0.7` → `PYSEC-2026-3717`, and PyPI returns 200 for 6.1.1 so the
      empty result is a real clean rather than an unrecognised version.
- [x] `python3 scripts/check_suppressions.py --validate` passes after the bump —
      `check_suppressions validate: OK (2 entries)`, exit 0.

## Work Log

### 2026-09-06 - Filed by scripts/sync_alarm_todo.py from alarm issue #663

- The scheduled scan went red and the alarm opened issue #663.
- Diagnosed the same day rather than left generic: dispatched the workflow
  manually and read the log, isolating a single advisory
  (django 6.0.7 / PYSEC-2026-3717) and confirming the npm job is now green.
- Recorded the Dependabot blind spot (GHSA vs PYSEC/OSV) explicitly, because
  the alert dashboards read 0 while this gate is red, which is actively
  misleading to the next triager.
- Cross-linked to todo 355 Slice 5 rather than duplicating the bump.

### 2026-09-06 - Closed. No dependency change was needed — the fix had already merged.

The bump this todo was waiting on landed **before** the todo was worked. PR #695
(`Django 6.0.7 → 6.1.1`, merged 2026-09-06 23:15 UTC) cleared `PYSEC-2026-3717`,
the single advisory this alarm was firing on. Nothing in `backend/requirements.txt`,
`.github/security-suppressions.yml`, or the workflow was edited by this todo.

**Why the alarm still read red 45 minutes short of a full cron cycle later —
the part worth remembering.** `security-scan.yml:435` gates the alarm step on
`github.event_name != 'pull_request'`. A fix always arrives on a `pull_request`
run, which is exactly the event the alarm skips. So the issue kept asserting
"Backend Python Security Scan: `failure`" against a tree where the advisory no
longer existed, and would have kept doing so until the Monday cron. The alarm was
not broken and not lying by design — it simply had not been given an event it was
allowed to act on. **After merging a security fix, dispatch the scan
(`gh workflow run security-scan.yml --ref main`) rather than waiting for the
cron.** Codified in `docs/LEARNINGS.md`.

This is a second, opposite-direction instance of the disagreement this todo
already documented: earlier, Dependabot read 0 while the gate was red (GHSA vs
PYSEC/OSV); here, the gate's own issue read red while every scanner read clean.
Neither dashboard is self-checking.

**Verification** (all run 2026-09-06/07, output pasted, not paraphrased):

- `gh workflow run security-scan.yml --ref main` → run
  [34068576160](https://github.com/Xertox1234/plant_id_community/actions/runs/34068576160)
- `gh run view 34068576160 --json status,conclusion` →
  `{"conclusion":"success","status":"completed"}`
- Jobs: `Backend Python Security Scan: success` · `Frontend npm Security Scan:
  success` · `Flutter Dependency Security Check: success` ·
  `No new dependency advisories: skipped` · `Security Scan Summary: success`
- Alarm step log → `closed alarm issue #663`
- `gh issue view 663 --json state,stateReason,closedAt` →
  `{"state":"CLOSED","stateReason":"COMPLETED","closedAt":"2026-09-07T00:04:19Z"}`
- `cd backend && ./venv/bin/pip-audit -r requirements.txt ${=$(python3 ../scripts/check_suppressions.py --emit-flags)}`
  → `No known vulnerabilities found` (exit 0)
- `cd web && npm audit --audit-level=moderate` → `found 0 vulnerabilities` (exit 0)
- `python3 scripts/check_suppressions.py --validate` →
  `check_suppressions validate: OK (2 entries)` (exit 0)
- Dependabot open alerts → `0` (124 total, all `state=fixed`); CodeQL open → `0`

**Also settled here:** todo 355's slice ledger had drifted two slices behind the
tree — slices 4 and 5 read `[ ]` while every pin they name was already on `main`,
landed by eight PRs (#675, #676, #677, #681, #683, #684, #686, #695) that never
opened the file. Both are now `[x]` with the PRs that actually shipped them, and
355's next-session stanza points at Slice 6 (closeout). 355 stays
`status: pending` — `in_progress` is invisible to every sweep skill.

**Left open deliberately** (mentioned, not fixed — each is someone else's todo or
harmless):

- Todo 356 — `security-scan.yml` has never audited the root npm manifest.
- `scripts/sync_alarm_todo.py:40` — `ALARM_KEY` is dead code and its
  `^Alarm issue: #(\d+)$` anchor would not match the `### `-prefixed heading
  `security_alarm.sh:45` actually writes. Unreferenced, so nothing is broken.
- The two suppressions stay in place until `expires: 2026-11-16`, per the
  2026-09-05 decision recorded in their own `reason` fields.

Archiving is safe: `sync_alarm_todo.py:54-59` scans `todos/archive/` too, so this
file permanently prevents refiling for episode #663. A future scan failure opens
a **new** issue number and earns its own todo.
