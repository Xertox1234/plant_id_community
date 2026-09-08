---
status: pending
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

- [ ] The live cron deployment's deploy log shows a `prune_forum_tombstones` run
      dated on or after 2026-09-09T03:00Z
- [ ] That run completed without traceback
- [ ] The run happened under a repo-sourced deployment (its metadata carries
      `commitHash` and `branch`, not only a `snapshotId`)

## Work Log

### 2026-09-08 - Filed

- Split out of todo 372 so that todo could be archived on its five verified
  criteria without ticking a sixth that was never run. Per this repo's rule, a
  criterion that moved is re-pointed and never checked off.

## Notes

p3, and genuinely expected to pass — the schedule is present in the service
config and the start command is unchanged. It is filed because "expected to
pass" is what the previous snapshot drift also looked like, and because a silent
failure here has no other detector.

Related: todo 372 (attached the source), archived todo 373 (the same check under
the previous snapshot deployment).
