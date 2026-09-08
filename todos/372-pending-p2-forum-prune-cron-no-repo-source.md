---
status: pending
priority: p2
issue_id: "372"
tags: [railway, deployment, dependencies, security, forum]
dependencies: []
---

# Attach a GitHub source to `forum-prune-cron` so merges to `main` reach it

## Problem

The `forum-prune-cron` Railway service has **no repo source**. It redeploys an
uploaded snapshot, so merging to `main` never reaches it — and because a Railway
*redeploy* re-runs the build from the retained upload context, it silently
rebuilds an old tree instead of decaying visibly.

On 2026-09-07 it was found running the **2026-07-26** tree: Wagtail 7.4.2 /
Django 6.0.7 against `main`'s 8.0 / 6.1.1, and reinstalling the exact packages
the security epic had removed. A manual re-upload fixed *today's* drift. Nothing
prevents the next one, and no alarm can see it.

## Findings

Discovered 2026-09-07 by direct inspection of the Railway API (not an audit run).

- `get-service-config` for service `7fee2fe0-5b83-46ab-99e4-ccfc001de87e`
  returns **no `source` block at all**. For contrast, `plant_id_community`
  (`78c24604-…`) returns
  `source: {repo: "Xertox1234/plant_id_community", branch: "main", rootDirectory: "backend"}`.
- Deployment history: the last `reason: "deploy"` before today was
  **2026-07-26**. The 2026-08-30, 08-31 and 09-06 entries are all
  `reason: "redeploy"` — which re-runs the build from the retained upload
  context, so the 09-06 rebuild installed the **July** tree.
- Build log of deployment `6323aa91-…` (2026-09-06T23:30:32Z) ends:
  `Successfully installed … Django-6.0.7 … bandit-1.9.4 … llm-0.27.1 … nltk-3.9.4
  … safety-3.6.2 … wagtail-7.4.2 wagtail-ai-3.1.0 wagtail-forum-0.1.0
  wagtail-headless-preview-0.8.0 …`
- Provenance is exact, not inferred: that same log reads
  `wagtail==7.4.2 (from -r requirements.txt (line 219))` with the editable
  `packages/wagtail_forum` at line 229, which matches commit `77287e3`
  (2026-07-26) and **not** `origin/main` (lines 201 / 211).
- `nltk`, `safety` and `bandit` were removed from `backend/requirements.txt` —
  and `llm` bumped to 0.31.1 — by **#659 (`07a27c0`, todo 355 slice 1,
  2026-09-05)**, one day *before* that rebuild reinstalled them. That subtree
  carried the only unpatched critical of the 71-advisory epic.
- **Dependabot cannot see any of this.** It reads the repo, and the repo is
  clean. So "0 open advisories" is a statement about `main` and the web
  container, never about this service.
- The tradeoff is already documented — `backend/docs/deployment/railway.md`,
  "How it was actually deployed — snapshot upload, not a GitHub source" — but
  only as a note at deploy time. Nothing watches the resulting staleness.
- Mitigated for now: on 2026-09-07 a fresh snapshot built from `origin/main`
  `df1d7ac` was uploaded (deployment `d467efc6-…`). That closes the current gap
  and does nothing about recurrence.

## Proposed Solutions

### Option 1: Attach the GitHub source (recommended)

- **Implementation:** dashboard-only — connect the repo, set Root Directory and
  the config-as-code file (steps below).
- **Pros:** the cron follows `main` like everything else; dependency bumps stop
  shipping half; Dependabot's view becomes true for this service too.
- **Cons:** every merge to `main` redeploys the cron, not just backend changes
  (harmless — a deploy does **not** run the command at all; only the 03:00
  UTC schedule fires a run).
- **Effort:** ~10 minutes in the dashboard.
- **Risk:** low, but not zero — a wrong config-as-code setting makes the service
  inherit the web `railway.json` and try to serve gunicorn (see step 3).

### Option 2: Keep the snapshot, add a re-upload step to every dependency bump

- **Implementation:** add the `railway up` recipe to the dependency-bump
  checklist and to `docs/rules/`.
- **Pros:** no infrastructure change.
- **Cons:** relies on a human remembering, which is exactly what failed between
  2026-07-26 and 2026-09-07 across at least three dependency PRs. A checklist
  cannot be verified by CI here.
- **Effort:** ~15 minutes.
- **Risk:** medium — restores the same blind spot the moment attention lapses.

## Recommended Action

0. ~~**Do todo 373 first, or capture its evidence before starting.**~~
   **Resolved 2026-09-08 — no longer blocking.** The hazard was that attaching a
   source supersedes deployment `d467efc6`, and Railway returns nothing for a
   superseded deployment's log. Todo 373's evidence is now captured and archived
   (the 03:00 UTC prune fired at 03:01:47Z under the new snapshot and returned
   `Pruned 0 tombstone row(s) older than 30 day(s).`), so this step is free to
   proceed. Kept visible rather than deleted, because the same hazard applies to
   *any* future attempt to verify a run from a snapshot deployment: capture the
   log before you replace the deployment.
1. Railway dashboard → `forum-prune-cron` → **Settings → Source** → connect
   GitHub repo `Xertox1234/plant_id_community`, branch `main`.
2. **Settings → Root Directory** = `backend`.
3. **Settings → Config-as-code file** = `railway.cron.json`. This one matters:
   a service left on the default `railway.json` inherits the web service's
   gunicorn `startCommand` **and** `healthcheckPath`, so the cron would try to
   serve gunicorn and never pass a healthcheck.
4. Trigger a deploy and confirm its metadata now carries `commitHash` +
   `branch: main` — the signature of a repo source — rather than only a
   `snapshotId`.
5. Confirm the build installs the current pins and none of the purged packages
   (`get-logs` with `types: ["build"]`, filter `Successfully installed`).
6. Update `backend/docs/deployment/railway.md`: the snapshot-upload section
   becomes historical, and steps 2–3 there — currently struck through as "not
   needed with the snapshot upload" — become required again.

## Technical Details

- Service id `7fee2fe0-5b83-46ab-99e4-ccfc001de87e`, project
  `2f3e4124-d0e0-430f-8e23-5a459eeff374` ("PlantID Community"), environment
  `production` (`36a8ade2-…`).
- Config lives in [`backend/railway.cron.json`](../backend/railway.cron.json):
  `python manage.py prune_forum_tombstones`, `cronSchedule: "0 3 * * *"` (UTC),
  `restartPolicyType: NEVER`, no healthcheck.
- **Root Directory and config-as-code are dashboard-only.** Per todo 261 there
  is no CLI flag (`railway add --help`, `railway service source connect --help`)
  and the public GraphQL API rejects the CLI's stored token — introspection
  succeeding is a false positive, every authenticated call returns
  `Not Authorized`. So this cannot be automated from here.
- The cron carries its own copy of the prod env set because it imports the same
  settings — including `USE_R2` and all five `R2_*` vars, per the root
  `CLAUDE.md` environment table. Attaching a source does not change variables.
- To read what a snapshot actually contains, use `get-logs` with
  `types: ["build"]` on its deployment id — a redeploy re-runs the build, so
  pip's resolved versions are in the log.
- Re-upload recipe, if this todo is deferred and drift needs clearing again:
  build the context with `git archive origin/main backend | tar -x -C <tmpdir>`,
  `cp railway.cron.json railway.json` inside it, then
  `railway up -p <projectId> -e production -s forum-prune-cron -d` from that
  directory. Building the context from `git archive` rather than swapping files
  in the working checkout keeps a shared checkout untouched and guarantees the
  upload is exactly `origin/main`.

## Acceptance Criteria

- [ ] `get-service-config` for `forum-prune-cron` returns a `source` block with
      `repo`, `branch: main`, and `rootDirectory: backend`
- [ ] A deployment triggered by a merge to `main` shows `commitHash` and
      `branch` in its metadata (not only a `snapshotId`)
- [ ] That deployment's build log shows the pins then current on `main`, and
      none of `nltk`, `safety`, `bandit`
- [ ] The effective config is still `railway.cron.json`: start command
      `prune_forum_tombstones`, `cronSchedule: "0 3 * * *"`, restart policy
      `NEVER`, no healthcheck — i.e. the service did not inherit gunicorn
- [ ] A scheduled run fires at 03:00 UTC after the change and completes, with
      log evidence (`railway logs <deployment-id> --service forum-prune-cron
      --deployment`)
- [ ] `backend/docs/deployment/railway.md` reflects the new topology

## Work Log

### 2026-09-07 - Filed

- Found while checking a claim that the cron "will sit on Wagtail 7.4.3": it was
  already on **7.4.2**, and the gap to `main` was a *major* version (8.0), not a
  patch — `main` had merged #710 the same day.
- A fresh snapshot built from `origin/main` `df1d7ac` was uploaded
  (deployment `d467efc6-…`), clearing the current drift. This todo covers only
  the structural fix, which is dashboard-only.
- p2 rather than p3: the prune job itself is low-stakes, but its staleness is
  invisible to every automated check the repo has, and it silently falsified a
  security posture ("71 advisories → 0") that was reported as complete.

## Notes

Related: todo 261 (created this service and documented the snapshot-upload
workaround), todo 355 / #659 (the dependency purge this service reverted in its
own image), todo 356 (the "false green" scanning gap — same shape: a check whose
scope silently excluded the thing it was believed to cover).

If Option 1 is rejected on cost, Option 2 is still strictly better than the
status quo — but it should then be a `docs/rules/` entry routed to a file small
enough to actually be injected, per todo 369's 8800-byte cap finding.
