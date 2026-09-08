---
status: pending
priority: p3
issue_id: "373"
tags: [railway, deployment, forum, verification, wagtail]
dependencies: []
---

# Verify the `forum-prune-cron` schedule actually fired under the new snapshot

## Problem

On 2026-09-07 a fresh snapshot was uploaded to `forum-prune-cron` to clear a
major-version drift (it had been running the 2026-07-26 tree). The **image** is
verified correct, but a Railway deploy does **not** trigger a run — only the
03:00 UTC schedule does. So it is still unproven that the cron actually executes
under the new image, and that image is a major Wagtail version newer than the
code that last ran successfully.

## Findings

- Deployment `d467efc6-7a1f-4a74-888c-78634c12746d` reached `SUCCESS` at
  2026-09-08T02:43:28Z, replacing `6323aa91-…` (now `REMOVED`).
- Its build log reads `Collecting wagtail==8.0 (from -r requirements.txt (line
  201))`, matching `origin/main` `df1d7ac` exactly — so the uploaded context is
  the current tree, not the July one.
- `backend/docs/deployment/railway.md` records, from 2026-07-26: "A deploy does
  NOT trigger a run (confirmed empirically: a successful deploy left the deploy
  log completely empty)." A green deploy therefore proves nothing about
  execution.
- The last *proven* successful prune ran on the old image (Wagtail 7.4.2 /
  Django 6.0.7). The new image is Wagtail 8.0 / Django 6.1.1 running against a
  Postgres the web service migrated to 8.0 (`wagtailcore.0098_apitoken`,
  additive). That exact pairing has never been exercised.
- Reading its logs has two known traps, both recorded in the deployment doc:
  pass the deployment id **explicitly** (`railway logs <deployment-id> --service
  forum-prune-cron --deployment --lines 60`) because the default resolves to a
  superseded deployment and returns nothing; and the log stream tags ordinary
  INFO lines as `[ERRO]`, which is not a real error.

## Recommended Action

1. After 03:00 UTC on 2026-09-08, read the deploy log for the live cron
   deployment (see the command above; confirm the id first with
   `list-deployments`, since a newer one may have superseded it).
2. Confirm `prune_forum_tombstones` ran, and that the container **exited** — a
   run that does not terminate skips the next one.
3. Confirm there is no traceback, in particular no `ImportError` or removed-API
   error from the Wagtail 7.4.2 → 8.0 jump.
4. If nothing fired at all, check that the `cronSchedule` survived the new
   upload — `railway.cron.json` sets `0 3 * * *`, and the schedule comes from
   the uploaded config-as-code, not from service settings.
5. If it fired and passed, note it in todo 372 as evidence that a re-upload is a
   safe operation, then close this todo.

## Technical Details

- Service `7fee2fe0-5b83-46ab-99e4-ccfc001de87e`, project
  `2f3e4124-d0e0-430f-8e23-5a459eeff374`, environment `production`.
- Schedules are UTC and fire roughly 1–2 minutes late (a `32 14 * * *` test
  schedule fired at `14:34:15Z` on 2026-07-26).
- `restartPolicyType: NEVER` — a failed prune waits for tomorrow rather than
  crash-looping, so a failure is quiet by design. That is exactly why this needs
  an explicit check rather than an assumption.

## Acceptance Criteria

- [ ] The live cron deployment's log shows a `prune_forum_tombstones` run dated
      on or after 2026-09-08T03:00Z
- [ ] That run completed with no traceback (specifically no Wagtail 8 import or
      removed-API error)
- [ ] The container exited rather than hanging
- [ ] If it did not fire: the `cronSchedule` is confirmed on the service and
      re-applied, and this todo is re-raised to p2

## Work Log

### 2026-09-07 - Filed

- Split out of the same session that re-uploaded the snapshot. The upload and
  the build are verified; execution is not, and cannot be until the schedule
  fires.

## Notes

p3 because the prune job is low-stakes maintenance and `restartPolicyType:
NEVER` means a failure cannot cascade. It becomes p2 if the run did **not**
fire, because the previous snapshot's schedule had been live and firing since
2026-07-26 — a silent loss of scheduling would be a regression introduced by the
re-upload.

Related: todo 372 (attach a GitHub source so this stops needing manual
uploads), todo 363 (the Wagtail 8.0 upgrade whose code this run first exercises
in the cron container).
