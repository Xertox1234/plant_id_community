# Security backlog: prevention + remediation (multi-session)

## Context

A GitHub cleanup pass on 2026-09-05 found the repo's *hygiene* clean — 0 open PRs, 0
stale remote branches, `main` green on all 5 required checks — but uncovered two
backlogs that had grown invisibly for ten months:

- **51 open CodeQL alerts** (22 high, 29 medium, **0 critical**), oldest 2025-10-23.
- **71 distinct dependency advisories** (4 critical, 49 high) across 115 alert rows,
  visible only once Dependabot was enabled during that pass. It had been **disabled**
  on a public repo.

The instinct is to blame "nobody looked." The evidence says something sharper and far
more fixable: **the alarms were already built, already correct, and already firing —
into a void.**

### Root cause 1 — the weekly gate has been red for 8 weeks and notifies nobody

`.github/workflows/security-scan.yml` runs `pip-audit` and `npm audit`, advisory-only
on `pull_request` (a deliberate, documented choice — blocking every open branch at once
had bitten three times: bleach, PyJWT, pillow) and **hard-failing on `schedule`**. That
design is right.

```
$ gh run list --workflow security-scan.yml --event schedule --limit 40
2026-08-31 failure  … 8 consecutive weekly failures since 2026-07-13
(31 failures / 9 successes across the last 40 scheduled runs; last green 2026-07-06)
```

A failed *scheduled* run blocks no PR, appears on no PR's check list, and surfaces only
in GitHub's default notification stream. It screamed weekly for two months, unheard.

### Root cause 2 — suppressions never expire, and their tracker was already closed

`security-scan.yml` carries 8 `--ignore-vuln` entries, each with a careful rationale.
Its header says:

```
# Revisit and drop the flag whenever a patched release ships (tracked in todo 089).
```

Todo 089 exists — `todos/archive/089-completed-p2-backend-dependency-cves.md`,
**`status: completed`**. It was finished and archived, and the pointer kept reading as
live tracking for months afterward. That is worse than a dangling reference: a broken
link gets noticed, a link to a closed ticket does not. (And 089's own review section had
already prescribed the fix — *"a dated 'review by' note per advisory, or a non-gating
scheduled pip-audit run without the ignore flags to surface when fixes ship."* This plan
implements a recorded follow-up, not a new idea.)

Meanwhile `--ignore-vuln` hides an advisory *unconditionally*, including once it becomes
fixable — so the weekly gate is structurally blind to its own ignore list. Five of the
six suppressed packages have since shipped newer releases; the `Twisted` entry literally
says *"Remove when Twisted >=26.4.0 stable releases."* It did. Nothing was watching.

### Root cause 3 — Dependabot was off, so the broader advisory database was invisible

`pip-audit` reads OSV/PyPI; Dependabot reads the GitHub Advisory Database, which is
substantially broader — 18 `nltk` advisories where the ignore list suppressed 2. No
second opinion existed, and no `.github/dependabot.yml` exists even now.

### Root cause 4 — CodeQL runs but is not required, so nobody triages it

CodeQL here is GitHub **default setup** (`state: configured`, no workflow file), so its
config lives in repo settings, not git. None of its contexts is in branch protection.

### Root cause 5 — the rule that would have prevented this exists, and never fires

`docs/rules/security.md` already says, verbatim:

> **Try a bump before suppressing a vuln.** pip-audit's empty "Fix Versions" column does
> NOT mean unfixable — the advisory's affected range may exclude a newer release … Add
> an `--ignore-vuln` line … only when no bump clears it, with a dated one-line justification.

That is precisely the rule the suppressions broke. It did not fail because it was
unwritten. It failed because **`docs/rules/routing.json` has no rule matching
`.github/**`, `requirements.txt`, or `package.json`** — so editing a manifest or the scan
workflow injects only `_discipline.md`, never `security.md`. And **no trigger in
`docs/rules/triggers.json` (90 entries) has a workflow glob.** The guidance was invisible
at the one moment it mattered.

Note too that write-time triggers **cannot block** — `severity` is a display label and
`match_triggers.py` always exits 0. Triggers raise awareness; enforcement lives in CI.

**The shape common to all five: a correct signal that reaches no one.** Prevention is
therefore not "add more scanning." It is *connect the existing alarms to something that
stops work*, *make suppressions expire*, and *route the existing rule to the files it
governs*.

## Intended outcome

1. Every existing alarm lands where a human or agent will see it.
2. A suppression that outlives its stated reason breaks the build.
3. Both backlogs reach zero, or a written, dated exception.
4. The work survives conversation compaction between every session.

---

## Decisions already made (binding)

| Question | Decision |
|---|---|
| Prevention | Scheduled triage sweep **+** block new alerts in CI **+** make CodeQL required |
| Alarm channel | **Both** — auto-open/update a GitHub issue **and** a todo file |
| Suppressions | **Expiring** — one that outlives its reason fails the build |
| Dependency policy | **Security updates only** — no version-update schedule |
| Wagtail + DRF | **Own session**, full `pytest --create-db` |
| `safety` / `bandit` | **Remove both** — declared, invoked by nothing |
| Freeze method | **Clean re-freeze in a fresh venv** |
| Sequencing | **Prevention first** |

## Corrections this planning pass produced

Four things I asserted earlier in the session were wrong. They are corrected here, and
three must be corrected in the repo.

1. **"Todo 089 does not exist" — wrong.** It exists, archived and completed. The real
   failure mode is a pointer to a *closed* artifact reading as live tracking.
2. **`nltk`/`llm` are NOT dead freeze residue.** `nltk` ← `safety==3.6.2`
   (`Requires-Dist: nltk>=3.9`, sole parent); `llm` ← `wagtail-ai==3.1.0`
   (`Requires-Dist: llm>=0.12`), live in `INSTALLED_APPS`. Deleting either line breaks
   `pip check`. **But** `safety` and `bandit` are invoked by nothing — so removing
   *`safety`* removes nltk. Same outcome, different mechanism. **`todos/355-…md` on
   `main` states the wrong version and must be rewritten.**
3. **The `llm` target is 0.31.1, not 0.34.** `llm 0.32.1` needs `sqlite-utils>=4.0`;
   `0.33`/`0.34` need `openai>3` + `httpx2`. We pin `sqlite-utils==3.38`,
   `openai==2.34.0`, `httpx==0.28.1`. `0.31.1` needs `openai>=2.32.0` and
   `sqlite-utils>=3.37` — satisfied, and it clears the `<= 0.27.1` vulnerable range.
4. **The root `package.json` is not dead.** `web/CLAUDE.md` §Deployment documents
   `npm run deploy` against it. All 14 root rows trace to `wrangler` transitives.

### Corrections from slice 1 (2026-09-05, verified against OSV and PyPI)

- **The `llm` advisory IS fixed by a bump — the suppression's premise was wrong.**
  Both `llm` entries said "No upstream fix per OSV/PyPI advisory." OSV records
  `last_affected: 0.27.1` for GHSA-g76p-4vg5-f4qh, and a query at 0.31.1 returns
  **zero** vulns. `last_affected` with no `fixed` event is precisely the empty
  "Fix Versions" column `docs/rules/security.md` warns is *not* proof of
  unfixability. Todo 355's "Removal is the only fix" is likewise wrong.
- **Twisted 26.4.0 stable shipped 2026-05-11 — nine days BEFORE the suppression
  that says it hadn't.** The entry added 2026-05-20 reads "No stable fix existed
  at suppression time (the fix was RC-only 26.4.0rc2)." It was false when
  written, not merely stale. Session 6 bumps it; there is no permanent residue.
- **`safety`'s exclusive subtree is 21 packages, not 6.** The plan expected
  `nltk, joblib, regex, typer, dparse` (+ eyeball `authlib`). The real closure
  also carries `filelock, Jinja2, joserfc, MarkupSafe, marshmallow, psutil,
  ruamel.yaml, ruamel.yaml.clib, shellingham, stevedore, tenacity, tomlkit`.
  Because `requirements.txt` is a flat freeze that pins transitives as their own
  lines, deleting only the three top-level entries would have left all 18
  children installed — including `nltk` and every one of its 18 advisories.
  The subtree must be computed and deleted explicitly; the freeze diff then
  proves nothing was over-deleted.

---

## Session 1 — Prevention

Delivered as **two PRs** plus settings changes, in a strict order.

### PR 1 — workflow `permissions:` blocks (closes 8 CodeQL alerts)

Add a top-level block to the five workflows lacking one.
`security-scan.yml:11` already has the shape to copy.

| File | Block |
|---|---|
| `backend-ci.yml`, `web-ci.yml`, `harness-ci.yml`, `kimi-review.yml` | `permissions:\n  contents: read` |
| `mobile-ci.yml` | `permissions:\n  contents: read\n  pull-requests: read` |

**`mobile-ci.yml` is a live footgun.** The repo's `default_workflow_permissions` is
`read`, and an explicit top-level block **replaces** that default rather than narrowing
it. `mobile-ci.yml:36` uses `dorny/paths-filter@v4`, which requires `pull-requests:
read`. Omit it and the `changes` job fails → the **required** `mobile-ci-gate` fails →
**every PR is blocked.**

No job `name:` changes, so branch protection is untouched. **Session 1 owns this cluster
— the CodeQL sessions must not also claim it.**

### PR 2 — the alarm, expiring suppressions, and the new-advisory gate

#### 2a. Alarm → GitHub issue, hosted in the existing `security-summary` job

That job's `exit 1` is currently the whole step, so anything appended after it never
runs. Split into three steps: compute verdict → run alarm → fail the gate. Add
job-level `permissions: { contents: read, issues: write }` (explicit, because the repo
default is `read`).

`.github/scripts/security_alarm.sh`, gated `if: always() && github.event_name !=
'pull_request'` so PR runs stay advisory-only:

- `gh label create security-scan-alarm --force` (idempotent; the label doesn't exist yet,
  so this removes a manual prerequisite).
- **One open issue is the dedupe key.** Absent → create. Present → comment + refresh the
  body's streak counter. Week 9 never opens a ninth issue.
- Green run → comment and close. Close → the next failure opens a *new* issue, which is
  the episode boundary the todo binds to.
- The body carries `Alarm issue: #<N>` and the bridge command below.

#### 2b. Alarm → todo file, via a local bridge (CI cannot write it)

**Verified blocker:** `gh api repos/:owner/:repo/actions/permissions/workflow` →
`{"default_workflow_permissions":"read","can_approve_pull_request_reviews":false}`.
Actions cannot create PRs here, and branch protection forbids direct pushes. Even if
enabled, a `GITHUB_TOKEN`-created PR triggers no workflows, so the 5 required checks
would never report — **permanent deadlock**, the exact class this repo hit twice.

So: `scripts/sync_alarm_todo.py`, run locally (the issue body prints the command, and
`todos/README.md` documents it):

- Read open issues labelled `security-scan-alarm`.
- Dedupe on `Alarm issue: #N` grepped across `todos/` and `todos/archive/`.
- If absent, write `todos/NNN-pending-p2-security-scan-alarm.md` in TEMPLATE.md shape
  with `status: pending` — which `completing-todos` discovers with zero skill changes.

One todo per *episode*, never one per week.

*If you want it truly automatic*, the cost is enabling Actions PR creation **plus** a
long-lived fine-grained PAT secret on a public repo. Recommend against.

#### 2c. Expiring suppressions

`--ignore-vuln` is CLI-only with no config-file support, so "suppressions as data" must
be a **generate-the-flags** design.

New `.github/security-suppressions.yml` — one entry per advisory carrying `package`,
`pinned`, `reason` (the existing comment text, verbatim), `clears_when`, `added`,
`expires`, `owner`, and `tracked_by`. **`tracked_by` is a todo `issue_id`, not a path** —
a path breaks on `git mv` to `archive/`, an id resolves through either location. That is
root cause 2 killed structurally.

New `scripts/check_suppressions.py`, three modes:

| Mode | Where | Fails when |
|---|---|---|
| `--emit-flags` | scan job | YAML malformed, or an id fails `^[A-Za-z0-9._-]+$` (also the shell-injection guard) |
| `--validate` | scan job (+ optionally `harness-ci`) | schema violation, duplicate id, missing/unparseable `expires`, window > `max_expiry_days` (180), empty `reason`/`clears_when`, missing `owner`, `tracked_by` resolving to no todo. **Never fails from mere passage of time**, so it is PR-safe |
| `--recheck --report backend/pip-audit-report.json` | schedule/dispatch only | `expires` past; **or** the id (or an alias) appears in the *unsuppressed* report with non-empty `fix_versions`; **or** `tracked_by` resolves to a todo whose status is `completed` |

**Why "`fix_versions` is now non-empty" beats "a newer release exists":**
`docs/rules/security.md` already carries the inverse warning — an empty Fix Versions
column does not mean unfixable. Symmetrically, nltk 3.10.3 *existing* does not prove
`PYSEC-2026-597` is fixed. The authoritative answer is the **unsuppressed** pip-audit
JSON the job already writes, so the recheck is free.

A tier-2 failure fails `backend-security` → `security-summary` → **the alarm fires**.
That closes the loop: a suppression outliving its fix reaches a human within a week.

#### 2d. Block new advisories — merge-base diff, no new permissions

New `new-vuln-gate` job, `if: github.event_name == 'pull_request'`, `contents: read`
only. Audit base and head **in the same run** (identical advisory DB), fail on ids
present in head and absent in base. A newly-published CVE against a static pin cannot
trip it — which is exactly what caused the bleach/PyJWT/pillow "blocked every branch"
incidents. npm half runs only when a lockfile is in the diff, but the job always reports
a status, so it is safe to require.

**Token feasibility:** `GITHUB_TOKEN` gained a `vulnerability-alerts: read` permission on
2026-09-03 — 48 hours old, undocumented caveats. **This design does not use it.** The
merge-base diff needs `contents: read` and sidesteps the 115-alert backlog entirely (a
Dependabot-API gate would be red from its first run).

#### 2e. Route the rule to the files it governs

- `docs/rules/routing.json`: add `{ "globs": [".github/*", ".github/security-suppressions.yml"],
  "domains": ["security"], "mode": "additive" }`, placed after the `backend/*.py`
  fallback. Add a case to `scripts/inject/test_route_domains.py`.
- Two `triggers.json` entries via `python3 scripts/inject/capture_trigger.py` (**never
  hand-edit**): `pip-audit-suppression-needs-expiry` on
  `.github/security-suppressions.yml`, and `ignore-vuln-flag-hand-added` on
  `.github/workflows/*.yml` matching `--ignore-vuln`. Deliberately **no
  `content_absent`** — it tests the *resulting file*, so once any entry has `expires:`
  the trigger would go silent for every future one. Add cases to
  `scripts/inject/test_match_triggers.py`.
- **`docs/rules/security.md` must be updated in this same PR.** Its existing bullet
  names `.github/workflows/security-scan.yml` as where suppressions live; the moment
  the YAML lands that is wrong — **root cause 5 reproduced by its own remediation**, and
  worse than a stale comment because this text is *injected at write time*. Repoint it,
  and add: a ruleset `PUT` replaces the whole `rules` array; a top-level `permissions:`
  block replaces the repo default (with the `dorny/paths-filter` example).
- `docs/rules/_discipline.md` (the always-on floor) gains: *a tracking pointer must name
  an artifact a script can resolve **and** assert is still open — otherwise it is a
  comment, not tracking.*
- One `docs/LEARNINGS.md` entry in the current form (`## YYYY-MM-DD — <lesson>`).

### Settings changes (you must apply or approve)

**Order is load-bearing.** Adding a required check is file-then-protection; a required
check that never reports deadlocks PRs, and this repo has hit that.

1. Merge PR 1 and PR 2 first. PR 2's own check list demonstrates `new-vuln-gate`
   reporting — that is the file half.
2. `gh api repos/:owner/:repo/branches/main/protection > before.json`.
3. `POST .../branches/main/protection/required_status_checks/contexts` with a bare array:
   `["Analyze (python)","Analyze (javascript-typescript)","Analyze (actions)","No new dependency advisories"]`.
   **Never `PATCH .../protection`** — omitted fields reset to default and would clobber
   `enforce_admins` and the existing 5 contexts.
4. `GET` again, diff against `before.json`, confirm the original 5 survive.
5. Ruleset 9138781 → **Require code scanning results**, tool `CodeQL`, Alerts threshold
   **None**, Security alerts threshold **Critical**. **Do this in the UI** — the ruleset
   API `PUT` replaces the entire rules array and has no additive sub-resource.

**Note this narrows your literal ask, deliberately.** Requiring the `CodeQL` *results*
check would fail on `high` severity — and 22 highs sit on `main` in hot forum files
(`TipTapEditor.tsx`, `ThreadDetailPage.tsx`, `weather_service.py`). Requiring it today
deadlocks forum work; LEARNINGS 2026-09-05 is this repo's own proof of the
fingerprint-shift hazard. So: require the three `Analyze (<lang>)` contexts (they report
on every PR, including docs-only #656, and fail only if analysis itself fails), and put
the *blocking* half in the ruleset at `critical`, which is provably green against today's
backlog. Tightening to `high_or_higher` is a one-field follow-up once todo 354 is done.

### Session 1 verification

`gh workflow run security-scan.yml` — it is **red right now** and `workflow_dispatch`
satisfies `!= 'pull_request'`, so this exercises alarm-open end to end with no wait for
Monday. Then `python3 scripts/sync_alarm_todo.py` exercises the bridge. A second dispatch
once the backlog is green exercises self-close. Plus
`python3 scripts/check_suppressions.py --validate`, the harness self-tests
(`test-inject-patterns.sh`, `test_match_triggers.py`, `test_capture_trigger.py`), and a
throwaway PR confirming all 9 required contexts report.

---

## Sessions 2–6 — Dependency remediation

### The re-freeze mechanic (sessions 2, 5, 6 — stated once)

`backend/requirements.txt` is a flat freeze with **two hand edits a naive
`pip freeze >` destroys**: the inline `ruff` comment and the trailing
`-e ./packages/wagtail_forum`. Find them by content, never by line number —
slice 1 took the file from 234 lines to 213 and moved both. The check is
`grep -n 'ruff==.*# F401' requirements.txt` and `tail -1 requirements.txt`.

It is a flat freeze, so **transitives are pinned as their own lines**: deleting a
top-level package does not remove its children. Compute the exclusive subtree
first (a package in the file that no *other* remaining package requires), delete
all of it, then let the freeze diff prove nothing was over-deleted.

```bash
cd backend
# 1. Edit pins by hand FIRST. 2. Rebuild a scratch venv FROM the edited file:
python3.13 -m venv /tmp/refreeze && /tmp/refreeze/bin/pip install -U pip
/tmp/refreeze/bin/pip install -r requirements.txt
/tmp/refreeze/bin/pip freeze --exclude-editable | sort -f > /tmp/frozen.txt
diff <(grep -v '^#' requirements.txt | grep -v '^-e ' | sed 's/ *#.*//' | sort -f) /tmp/frozen.txt
# 3. Apply only intended deletions by hand. Confirm each dropped package has no
#    other parent: grep -l "^Requires-Dist: <pkg>" backend/venv/lib/python3.13/site-packages/*/METADATA
```

Installing *from the edited file* keeps `wagtail`, `Django`, `celery` pinned where they
are — the freeze reproduces the input minus the removed subtree.

| # | Session | Scope | Closes |
|---|---|---|---|
| 2 | Dead-tooling purge + `llm` | Delete `bandit` (:12), `safety` (:189), `safety-schemas` (:190); re-freeze (expect `nltk`, `joblib`, `regex`, `typer`, `dparse` to drop — **eyeball `authlib`**). `llm==0.27.1 → 0.31.1` (:122). `git rm backend/requirements.txt.bak2` (tracked, pins nltk 3.9.2, ships in the image). Drop 5 now-dead suppressions. **Rewrite todo 355 into the epic shape, correcting the nltk/llm claim.** | 19 GHSAs |
| 3 | `web/` lockfile refresh | `cd web && npm update`. **Zero `package.json` edits** — every target is inside an existing caret range. **Supersedes Dependabot PRs #650–#654.** | 18 GHSAs |
| 4 | Root `wrangler` bump | `wrangler ^4.95.0 → ^4.129.0`; regenerate root lock. Do **not** delete the manifest. | 14 rows / 9 GHSAs |
| 5 | **Wagtail 7.4.3 + DRF 3.17.2** | `:224` and `:69`. **Runs alone** — two concurrent pytest runs corrupt the shared test DB. **Read the release notes first.** | 7 GHSAs |
| 6 | Backend transitive re-freeze | `sqlparse 0.6.0`, `pyasn1 0.6.4`, `h2 4.4.1`, `httplib2 0.32.0`, `setuptools 83.0.0`, **`Django 6.0.7 → 6.0.8`**, **`Twisted 25.5.0 → 26.4.0`**, and **`cryptography 50.0.1` + `pyOpenSSL 26.4.0` as a pair**. | 14 GHSAs, leaves 0 |

**`cryptography` cannot move alone.** `pyOpenSSL 26.2.0` caps `cryptography<49`; the
advisory wants `>=50.0.0`; `pyOpenSSL 26.4.0` requires `>=49.0.0`. Unpaired, `pip check`
fails. It has 13 parents — smoke the field-encryption and JWT paths.

**Verification per session:** every backend session runs `python -m pip check` (mirrors
`backend-ci.yml:66`), `pip-audit`, `manage.py check --deploy`, and the full pytest suite
— sessions 5 and 6 with `--create-db`, alone. Session 5 adds
`makemigrations --check --dry-run`, `manage.py spectacular`, a `/cms/` admin smoke (all
5 wagtail advisories are permission handling), and an upload-limit assertion against
`file-upload.md`'s 4-layer validation, which assumes `DATA_UPLOAD_MAX_MEMORY_SIZE` holds.
Session 3 adds `npm ci && type-check && lint && test && build`, `npm audit`, and a
**manual composer smoke** — `@tiptap/*` moves 8 minor versions.

## Sessions 7–10 — CodeQL remediation

Session 1 already took the 8 `actions/missing-workflow-permissions` alerts.

| # | Session | Scope | Closes |
|---|---|---|---|
| 7 | Backend view-layer | `oauth_views.py` provider allowlist (todo 354 settled these as false positives — the fix makes the taint unreachable; add a regression test). Plus 12 `py/stack-trace-exposure` — cross-check todo 320's error-envelope work first; confirm `simple_urls.py`/`simple_views.py` are still reachable. | 20 |
| 8 | Clear-text logging | 13 live-code redactions (`weather_service.py` ×9, `settings.py` ×2, `care_assistant_service.py`, `ratelimit.py`) keeping the bracketed-prefix convention; 3 dev-script dismissals. Per §Evidence before claims, report count-found vs count-changed. | 16 |
| 9 | Web cluster + dedup | `js/xss-through-dom` #122 — **353's lesson is binding: a suppression comment is not a fix**; break the path structurally or dismiss via API. 3 sanitization dismissals citing 354. Dedup `isBlankHtml`, duplicated verbatim across two pages. | 4 |
| 10 | Closeout | Final counts; document any residue; flip both epics to `completed` and archive. | — |

---

## Tracking artifact

**Rewrite `todos/355-…md` and `todos/354-…md` into epics. Do not file new todos** — 355
already *is* the dependency tracker and 354 the CodeQL one, both on `main`, and 355 must
be corrected in place anyway.

Use the project's existing convention (no `parent`/`epic` frontmatter field exists):
title prefix, `epic` in `tags`, and a `## Slices` checklist where each line names its PR
— the shape of `todos/archive/273-…` and `todos/archive/341-…`.

### The constraint that shapes this

`todo-next`, `todo-sweep`, and `todo-batch` all discover via
`grep -l "^status: pending" todos/*.md`, and `completing-todos` flips
`pending → in_progress` (and `git mv`s the filename) at the *start* of a run, archiving
at the end. **So `in_progress` is as invisible to the sweeps as `blocked` is** — a
ten-session epic run through `completing-todos` would vanish after slice 1.

Therefore **355 and 354 stay `status: pending` for their entire lives**, with a literal
warning in each body telling future sweep agents not to run them through those skills.
Only the closeout session flips them.

## Handoff mechanism

The project already has a git-tracked cross-session ledger — the `## Work Log`, one
`### YYYY-MM-DD - <event>` heading per session (`todos/archive/253-…` runs 13 entries).
Nothing new is needed; what's missing is a sub-shape that makes an entry resumable cold.
The `completing-todos` checkpoint is **not** usable — gitignored (`.gitignore:217`), so
it dies with a fresh clone or worktree switch.

Each session appends, never edits in place:

```markdown
### YYYY-MM-DD - Slice N (<name>) shipped — PR #NNN

- **Scope shipped**: <files by repo-relative path, every pin from→to>
- **Verification** — commands and their ACTUAL output, not "passed":
  - `<command>` → `<pasted result>`
- **Alert ledger**: Dependabot <before> → <after> GHSAs · CodeQL <before> → <after>
- **Decisions locked** (do not re-litigate): <bullets>
- **Surprises / carried forward**: <what moved, what invalidates a later slice>

**Next session — Slice N+1 (<name>)**
- Branch state: PR #NNN <merged | OPEN on `<branch>`, CI <status>>
- Resume with: `cd <repo> && git checkout main && git pull`
- Branch to create: `<type>/<slug>`
- First command: `<one command that proves the starting state>`
- Scope: <2–4 concrete lines>
- Verification that ends it: `<command>`
- Do NOT: <the specific trap>
```

Rules: the `**Next session**` stanza is mandatory and always last; the matching
`## Slices` line is checked off with its PR number in the same commit; the entry is
committed on the feature branch **before the session ends** — squash-merge carries it to
`main` intact, but only if the PR merges.

## Verification of the whole effort

```bash
gh api --paginate "repos/:owner/:repo/dependabot/alerts?state=open&per_page=100" \
  --jq '.[].security_advisory.ghsa_id' | sort -u | wc -l     # expect 0
gh api --paginate "repos/:owner/:repo/code-scanning/alerts?state=open&per_page=100" \
  --jq 'length'                                              # expect 0
gh run list --workflow security-scan.yml --event schedule --limit 4   # expect success
python3 scripts/check_suppressions.py --validate             # expect exit 0
gh api repos/:owner/:repo/branches/main/protection --jq '.required_status_checks.contexts'
```

## Open items needing your call

- **Dependabot PRs #650–#654** — session 3's refresh reaches equal-or-newer versions than
  all five. Close as superseded, or merge them first?
- **Branch protection + ruleset edits** are GitHub settings actions you must apply.

## Not verified

- Whether the ruleset `code_scanning` rule counts PR-diff alerts or all branch alerts.
  Mitigated by construction: with 0 criticals, `critical` is green under either reading.
- pip-audit JSON schema (`dependencies[].vulns[].{id,fix_versions,aliases}`) — from docs,
  not a local run. Verify against run 33376362875's artifact (inside 30-day retention)
  before writing the parser. The `aliases` key matters for the recheck.
- `npm audit --package-lock-only --json` as the cheap path for the npm diff.
- Wagtail 7.4.3 / DRF 3.17.2 release notes — read at the top of session 5.
- TipTap 3.22.5 → 3.30.x breaking changes — the main risk in session 3.
- Whether Cloudflare Workers Builds runs `npm ci` at root (quoted from a comment in
  `wrangler.jsonc`, not the dashboard).
