---
status: completed
priority: p3
issue_id: "375"
tags: [railway, deployment, forum, verification]
dependencies: []
---

# Verify the prune fires on schedule under the repo-sourced deployment

## Problem

Todo 372 attached a GitHub source to `forum-prune-cron` on 2026-09-08. Five of
its six acceptance criteria were verified immediately; the sixth — that the
03:00 UTC schedule still fires — cannot be, because a Railway deploy does not
trigger a run. The schedule has only ever been proven under *snapshot*
deployments. This is the same check todo 373 performed, re-raised because the
deployment it was proven against no longer exists.

## Findings

- Todo 373 verified a successful run at 2026-09-08T03:01:47Z, but against
  deployment `d467efc6` (a snapshot). Attaching the source superseded it, and
  Railway returns nothing for a superseded deployment's log — exactly the hazard
  372's step 0 described. 373's evidence was captured before that happened, so
  nothing was lost, but it no longer describes the live deployment.
- The live deployment is now `07c9ed09` (`reason: "deploy"`,
  `commitHash: b36e9b9`, `branch: main`), built from the repo and confirmed
  `SUCCESS`.
- Its service config carries `cronSchedule: "0 3 * * *"`,
  `startCommand: python manage.py prune_forum_tombstones`,
  `restartPolicyType: NEVER`, no healthcheck — so the schedule *should* survive
  the source change. This todo is confirming that, not investigating a doubt.
- `restartPolicyType: NEVER` means a failure is silent by design: the run waits
  for the next day rather than crash-looping. Nothing will page.

## Recommended Action

1. After 03:00 UTC on 2026-09-09, list deployments to find the live one (a merge
   to `main` may have superseded `07c9ed09` — that is now expected behaviour,
   not a problem).
2. Read its deploy log: `get-logs` with `types: ["deploy"]`, or
   `railway logs <deployment-id> --service forum-prune-cron --deployment`.
3. Confirm a `Pruned N tombstone row(s)…` line dated after 03:00 UTC, and that
   `argv` shows `prune_forum_tombstones` — which also re-confirms the
   config-as-code file is still being read from
   `backend/railway.cron.json`.
4. If it did not fire, check `cronSchedule` on the service first; a source
   change resetting it is the most likely cause.

## Technical Details

- Service `7fee2fe0-5b83-46ab-99e4-ccfc001de87e`, project
  `2f3e4124-d0e0-430f-8e23-5a459eeff374`, environment `production`.
- Schedules are UTC and fire 1–2 minutes late.
- The log stream tags ordinary INFO lines as `[ERRO]`; that is not an error. The
  `[ENV VALIDATION]` warnings are expected — the cron carries a deliberately
  reduced env set.
- **Capture the log before any action that replaces the deployment.** That is
  what makes this check fragile, and why it has now been raised twice.

## Acceptance Criteria

- [x] The live cron deployment's deploy log shows a `prune_forum_tombstones` run
      dated on or after 2026-09-09T03:00Z — seven daily runs, 2026-09-16 →
      2026-09-22, under `2a260c93` while it was the live deployment
      (completed 2026-09-23)
- [x] That run completed without traceback — each run is argv line → `Pruned N…` line; a `Traceback` filter over the whole window returns nothing (completed 2026-09-23)
- [x] The run happened under a repo-sourced deployment (its metadata carries
      `commitHash` and `branch`, not only a `snapshotId`) — `2a260c93`:
      `commitHash 70511ba4…`, `branch main`, `reason deploy` (completed 2026-09-23)

## Work Log

### 2026-09-08 - Filed

- Split out of todo 372 so that todo could be archived on its five verified
  criteria without ticking a sixth that was never run. Per this repo's rule, a
  criterion that moved is re-pointed and never checked off.

### 2026-09-23 - Verified: the schedule fires daily under repo-sourced deploys; CLOSED

Deployment `2a260c93-0f27-4e77-a1bc-3b5a3cdf9b6b` (created 2026-09-15 22:13 UTC
from `main` @ `70511ba4`, `reason: deploy` — repo-sourced, metadata carries
`commitHash` + `branch`) was the live cron deployment from 2026-09-15 until
2026-09-23 00:56. `get-logs` filtered on `Pruned OR argv OR Traceback`:

```
2026-09-16T03:01:35Z  [settings] … (argv=['manage.py', 'prune_forum_tombstones'])
2026-09-16T03:01:37Z  Pruned 17 tombstone row(s) older than 30 day(s).
2026-09-17T03:02:30Z  argv … prune_forum_tombstones   → Pruned 0 …
2026-09-18T03:02:08Z  argv … prune_forum_tombstones   → Pruned 0 …
2026-09-19T03:01:37Z  argv … prune_forum_tombstones   → Pruned 0 …
2026-09-20T03:02:16Z  argv … prune_forum_tombstones   → Pruned 0 …
2026-09-21T03:02:59Z  argv … prune_forum_tombstones   → Pruned 0 …
2026-09-22T03:04:57Z  argv … prune_forum_tombstones   → Pruned 0 …
```

Seven consecutive nights, each 1.5–5 min after 03:00 UTC, each an argv line
followed by a `Pruned` line and no `Traceback`. The 09-16 run did real work (17
rows), so this is not only a no-op path passing. The argv also re-confirms the
start command comes from `backend/railway.cron.json`.

**Correction to this file's premise.** The Findings say "Railway returns nothing
for a superseded deployment's log". Not true today: `2a260c93` was already
`REMOVED` (superseded by `f02feef4` at 00:54 UTC, then `105ca4a7` at 01:32) when
this log was read, and the full history came back. Retention may still be
finite, so capturing evidence promptly remains the right habit, but a
superseded deployment is not instantly unreadable.

**Every merge to `main` redeploys the cron** (three deployments on 2026-09-23
alone, from docs-only PRs). That is expected under a repo source, and seven
nights across a live week show a redeploy does not reset `cronSchedule`. The
current deployment `105ca4a7` has not yet reached a 03:00 — not needed for the
ACs, which ask about the repo-sourced schedule, not a specific deployment id.

## Notes

p3, and genuinely expected to pass — the schedule is present in the service
config and the start command is unchanged. It is filed because "expected to
pass" is what the previous snapshot drift also looked like, and because a silent
failure here has no other detector.

Related: todo 372 (attached the source), archived todo 373 (the same check under
the previous snapshot deployment).
