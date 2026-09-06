---
status: pending
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
- Confirmed empirically on the slice 3 PR: local root `npm audit` went
  `6 vulnerabilities (1 low, 5 high)` → `found 0 vulnerabilities`, a change the
  gate was structurally unable to observe.
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

- [ ] A PR that adds a known-vulnerable package to the **root** lockfile fails
      `new-vuln-gate` (demonstrated on a throwaway branch, then reverted).
- [ ] `frontend-security` on a `workflow_dispatch` run audits the root manifest;
      its log shows an `npm audit` invocation whose cwd is the repo root.
- [ ] `scripts/test_new_vuln_gate.py` gains a case that fails against the
      pre-fix plumbing.
- [ ] `docs/rules/security.md` names both manifests.

## Work Log

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
