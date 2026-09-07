---
status: completed
priority: p2
issue_id: "356"
tags: [security, ci, dependencies, prevention]
dependencies: []
---

# `security-scan.yml` has never audited the root npm manifest

## Problem

The repository has two lockfile-bearing npm manifests — `package.json` (root)
and `web/package.json`. Every npm step in `.github/workflows/security-scan.yml`
hardcodes `web/`. The root manifest is therefore invisible to both halves of the
scan: the weekly `frontend-security` audit and the `new-vuln-gate` PR diff.

That manifest is not incidental. Cloudflare Workers Builds runs
`npm clean-install` against it and deploys with `npx wrangler versions upload`
from the root `node_modules` — it is the production deploy path. It carried 14
open advisories (11 × `undici`, `sharp`, `ws`, `esbuild`; 5 high, 1 low) that
only Dependabot ever surfaced. The repo's own scanner reported nothing, and
nothing read as fine.

## Findings

Discovered 2026-09-06 during todo 355 slice 3, which was the first PR to change
the root lockfile.

- **`frontend-security` audits only `web/`.**
  `.github/workflows/security-scan.yml:130` caches `web/package-lock.json`,
  `:132-135` runs `cd web && npm ci`, and `:137-141` / `:143-148` run
  `npm audit` inside `web/`. Nothing in the job ever visits the repo root. So
  the weekly hard-failing scan could not have caught the 14 root advisories,
  and did not.
- **`new-vuln-gate` detects a root change but audits the wrong tree.**
  The scope step at `:292` matches `(^|/)package-lock\.json$|(^|/)package\.json$`
  — the `^` alternative matches the ROOT lockfile, so `npm=true` is set. But the
  "Audit web base and head" step at `:326-337` unconditionally reads
  `web/package.json`, `web/package-lock.json` and runs
  `(cd web && npm audit …)`. A PR that changes only the root lockfile therefore
  audits `web/` against `web/`, gets an identical pair, and prints
  `npm audit: N advisories on base, N on head, 0 new`.
- **Consequence: a false green, not a skip.** The gate does not report
  "skipped" — it reports a confident `0 new` while never reading the file the PR
  changed. A PR that *adds* an advisory to the root lockfile passes the gate.
- **Measured on PR #669**, the first PR to change the root lockfile. Job
  `No new dependency advisories`, run 34006610283:

  ```
  changed files:
    package-lock.json
    package.json
    todos/356-pending-p2-security-scan-root-manifest-blind.md
  ...
  NPM: true
  pip-audit: skipped (no manifest change in this PR)
  npm audit: 0 advisories on base, 0 on head, 0 new
  No new dependency advisories introduced by this pull request.
  ```

  The scope step listed the root lockfile by name and set `npm=true`. The
  comparison then reported **`0 advisories on base, 0 on head`** — the `web/`
  tree, which slice 2 had already cleared to zero. Meanwhile the root tree that
  the PR actually changed went from 15 distinct advisories to 0 locally
  (`npm audit --audit-level=moderate`: `6 vulnerabilities (1 low, 5 high)` →
  `found 0 vulnerabilities`). The gate reported confidently on a tree with no
  relationship to the diff.
- Note the shape of the false green: `pip-audit` printed an honest
  `skipped (no manifest change in this PR)` on the same run. The npm half had
  the same "skip" vocabulary available and did not use it, because its scope
  predicate said the PR *was* relevant. Detection was right; the action was
  pointed at the wrong tree.
- `design_reference/package.json` also exists but has **no lockfile**, so it is
  out of scope for a lockfile-based audit.

## Recommended Action

1. **`frontend-security`** — audit both manifests. Either loop over
   `. web` in the existing steps, or add a second parallel job. The weekly
   hard-fail (`github.event_name != 'pull_request'`) must cover the root tree,
   since that is the deploy artifact.
2. **`new-vuln-gate`** — replace the hardcoded `web/` in the audit step with the
   set of directories whose lockfile actually appears in
   `git diff --name-only "$BASE_SHA" HEAD`. `scripts/new_vuln_gate.py` already
   accepts one `--base-npm`/`--head-npm` pair; either extend it to accept
   several pairs, or run it once per changed manifest and fail if any run fails.
3. **Guard the fix with a test.** `scripts/test_new_vuln_gate.py` is run by
   `harness-ci.yml`. Add a case asserting that a root-only lockfile change
   produces a comparison of the ROOT trees — the current suite passes with the
   bug present, because the bug is in the workflow's plumbing, not the script.
4. Re-read `docs/rules/security.md` — it should name *both* manifests wherever
   it names one.

## Technical Details

- `.github/workflows/security-scan.yml` — `frontend-security` job (`:115-183`),
  `new-vuln-gate` job (`:260-367`).
- `scripts/new_vuln_gate.py` — `compare()` takes a single base/head pair per
  ecosystem and raises `GateError` when given only one half, so any multi-pair
  extension must preserve that "half a pair is an error" property.
- `wrangler.jsonc` — the deployed Worker (`plantidcommunity`). Its build log
  (Workers Builds, build `45880b9e-ac9a-4e16-87dd-88613a4833ff`) shows
  `Installing project dependencies: npm clean-install` at the root, then
  `cd web && npm ci && npm run build`, then `npx wrangler versions upload`.
- Related pattern: `docs/LEARNINGS.md` 2026-09-06 — "a mechanism that has never
  fired is not verified". This is the same shape: a scanner that never reads a
  file reports nothing about it, and nothing reads as fine.

## Acceptance Criteria

- [x] A PR that adds a known-vulnerable package to the **root** lockfile fails
      `new-vuln-gate` (demonstrated on a throwaway commit, then reverted).
- [x] `frontend-security` on a `workflow_dispatch` run audits the root manifest;
      its log shows an `npm audit` invocation whose cwd is the repo root.
- [x] `scripts/test_new_vuln_gate.py` gains a case that fails against the
      pre-fix plumbing — as far as a unit test can, see the caveat in the work log.
- [x] `docs/rules/security.md` names both manifests.

## Work Log

### 2026-09-07 - Fixed: the manifest set moved into the tested gate script

**What changed.** The manifest set and both scope predicates now live in
`scripts/new_vuln_gate.py` — `NPM_MANIFEST_DIRS = (".", "web")`,
`npm_dirs_from_changes()`, `pip_changed()` — where `harness-ci` (a REQUIRED check)
already tests them. `security-scan.yml` loops over what `--list-npm-dirs` and
`--scope` report instead of over a directory name written into YAML. There is no
workflow string left to get wrong.

- `frontend-security` audits every manifest, grouped per cwd in the log. Dropped
  `npm ci` entirely for `--package-lock-only` — **verified equivalent**, not
  assumed: PR #669's base root lockfile (15 advisories) yields identical GHSA id
  sets with and without the install. Added an assertion that the manifest list is
  non-empty, since an empty list would be a silent green scan of zero trees.
- `new-vuln-gate` audits one base/head pair per CHANGED manifest, each against
  its own base. Per-manifest comparison is load-bearing: merging the reports
  would let an advisory already sitting in `web/`'s base cancel the same advisory
  arriving in the root tree (there is a test for exactly that).
- The audit loop and the compare loop read the same `$NPM_DIRS`. If the audit
  loop skips a manifest the compare loop names, the report is absent and
  `_load()` raises `GateError` — the gate fails loudly rather than answering from
  a stand-in tree. No cross-check flag needed.

**AC3 cannot be satisfied literally, and this is the honest version.** No unit
test in `scripts/test_new_vuln_gate.py` can fail against a bug that lives in
workflow YAML. What the 12 new cases prove is that the *extracted* logic is right
(mutation-checked: pinning `NPM_MANIFEST_DIRS` to `("web",)` reddens 3 tests;
adding a pin to `requirements-dev.txt` reddens 1). The proof that the plumbing
now reaches the root tree is the AC1 run below. A green `harness-ci` is NOT that
proof — reading it as such would be this todo's own "a mechanism that has never
fired is not verified", one level up.

**Local evidence before CI.** Replaying PR #669's exact scope
(`package.json` + `package-lock.json`, base `2f6cbc8^`) through the fixed
plumbing prints:

```
npm audit (.): 15 advisories on base, 0 on head, 0 new
```

The pre-fix gate printed `0 advisories on base, 0 on head` for the same PR. Same
diff, same base — the 15 is the root tree finally being read.

Adding `lodash@4.17.20` to the root lockfile and re-running against a clean base:

```
npm audit (.): 0 advisories on base, 5 on head, 5 new
  - .: GHSA-35jh-r3h4-6jhm (lodash, high)   [+4 more]
GATE EXIT=1
```

**Also fixed:** the PR-comment body said `Run locally: cd web && npm audit`,
which taught humans the same blind spot the workflow had. It now names both trees.

**Also, small:** `pip_changed()` is deliberately broader than the file the pip
audit reads, which is safe only because `backend/requirements-dev.txt` is a
pinless `-r requirements.txt` overlay. `test_requirements_dev_carries_no_pins`
now guards that invariant, so the day it gains a pin the suite goes red instead
of the gate going falsely green.

### 2026-09-07 - MERGED

PR #698 squash-merged as `49cc3fd`. 17/18 checks green (the skip is the Flutter
build, correctly path-filtered). Codified in the same PR: two
`docs/rules/security.md` rules, a `docs/LEARNINGS.md` entry, the write-time
trigger `npm-audit-package-lock-only-misses-lockfile-skew` (four fixtures against
the real index, mutation-checked both ways), four `cross-cutting-reviewer`
checks, and a `docs/rules/routing.json` fix — every top-level `scripts/*.py` is a
security scanner and all four routed to NO domain, so the rules naming
`new_vuln_gate.py` could never reach whoever edits it.

### 2026-09-07 - Round 1 code review: three findings, all fixed

The review found the same false-green shape **one layer down**, plus two silent
omissions the `npm ci` removal opened. All three confirmed by experiment, not
by reading.

1. **A FAILED `npm audit --json` reads as zero advisories.** Against an
   unreachable registry it writes 186 bytes of
   `{"message": "... ECONNREFUSED", "error": {...}}` to stdout and exits 1. That
   survives the `[ -s "$f" ]` size assertion (non-empty), and the `|| true`
   cannot use the exit code because npm audit exits 1 for ordinary advisories
   too. `npm_advisories()` returns `{}`. A transient failure on the HEAD audit
   would print `15 on base, 0 on head, 0 new` and pass. `_load()` now raises
   `GateError` on a top-level `error` key; mutation-checked. Only the head side
   was silent — a base-side failure inverts into a loud false red.
2. **The root package.json ↔ lockfile sync was left unguarded.**
   `--package-lock-only` audits the LOCKFILE, so a dependency declared in
   `package.json` but absent from the lockfile is never looked at and the audit
   still exits 0 with `found 0 vulnerabilities` (verified). `npm ci` used to
   hard-fail on that skew and is now gone from this job; `web/` is still covered
   by `web-ci.yml`, the ROOT was not covered anywhere in CI. Added
   `npm ls --package-lock-only` at the same severity as the audit.
3. **`slug="$dir"` breaks for a nested manifest**, which the drift test actively
   invites someone to add. A slug with a slash makes the report redirect fail on
   the missing parent, swallowed by `|| true` — the manifest silently drops out
   of the artifact. Now `${dir//\//-}` in all three places.

Cleared and not changed: the two-dot `git diff` (checkout gives
`refs/pull/N/merge`, so HEAD already carries base), argparse `action="append"`
default mutation (Python 3.8+ copies), drift-test reachability
(`harness-ci.yml`'s `paths:` filter applies to `push` only).

### 2026-09-07 - CI evidence (PR #698)

**AC1 — the gate now reads the ROOT lockfile.** Commit `6df3fe9` added
`lodash@4.17.20` to the root manifest only. Run
[34136713877](https://github.com/Xertox1234/plant_id_community/actions/runs/34136713877),
job `No new dependency advisories`:

```
changed files:
  package.json
  package-lock.json
pip=false
npm_dirs=.
pip-audit: skipped (no manifest change in this PR)
npm audit (.): 0 advisories on base, 5 on head, 5 new
  - .: GHSA-35jh-r3h4-6jhm (lodash, high)          [+4 more]
##[error]Process completed with exit code 1.
```

Compare with PR #669's pre-fix run 34006610283 on the *same* scope:
`NPM: true` then `npm audit: 0 advisories on base, 0 on head, 0 new`. Same class
of diff, opposite verdict — the gate is reading the tree the PR changed.
Reverted in `a40e7e1`; the root manifests are byte-identical to `main` again.

**AC2 — the weekly hard-fail covers the root tree.** `workflow_dispatch` run
[34136717865](https://github.com/Xertox1234/plant_id_community/actions/runs/34136717865),
job `Frontend npm Security Scan`, on the same specimen commit:

```
manifests to audit: . web
##[group]npm audit --audit-level=moderate (cwd: .)
1 high severity vulnerability
##[group]npm audit --audit-level=moderate (cwd: web)
found 0 vulnerabilities
clean: web
npm audit found moderate+ vulnerabilities on a workflow_dispatch run — failing the gate.
```

Stronger than the AC asked for: it does not merely *visit* the root tree, it
BLOCKS on a root-only advisory — the exact thing that could not happen while the
job hardcoded `web/`, and the reason 14 root advisories sat unseen. The
`pull_request` run of the same job on the same commit passed, correctly, because
PR runs stay advisory-only by design.

**Regression.** With the specimen reverted, `new-vuln-gate` on this PR reports
`npm audit: skipped (no manifest change in this PR)` — the honest skip, not a
bare `0 new`.

### 2026-09-06 - Filed from todo 355 slice 3

- Found while verifying the root `wrangler` bump: the stanza's prescribed
  verification ("confirm `new-vuln-gate` reports `NPM: true` / `0 new`") would
  have been a false confirmation, since the gate audits `web/` regardless.
- Filed rather than fixed in the same PR deliberately: a gate fix wants to be
  exercised against a base that lacks it, and slice 3 is the specimen. Fixing
  it inside slice 3 would compare base-`web/` against head-root.

## Notes

p2, not p3: this is the deploy path on a public repo, and the gap is what let 14
advisories sit unseen by the repo's own scanner. Sized small — the change is
confined to one workflow file plus a test.

Related: todo 355 (dependency epic, slice 3),
`docs/superpowers/plans/2026-09-05-security-backlog-multi-session.md` §2d.
