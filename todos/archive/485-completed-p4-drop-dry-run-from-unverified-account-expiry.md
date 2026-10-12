---
status: completed
priority: p4
issue_id: "485"
tags: [backend, auth, ops]
dependencies: []
source_review: "PR #877"
owner_decision: "Unblocked: owner-approved read of forum-prune-cron logs 2026-10-01..2026-10-11 shows 0 candidates every night (2026-10-11); remove --dry-run per AC 2-3 (2026-10-11)"
triage: ready
triaged: 2026-10-11
---

# Drop `--dry-run` from the unverified-account expiry cron; tidy archived 447

## Problem

Todo 447 was archived by PR #877 (todo sweep run 2026-09-28-2018). Its last open step belongs to
the owner and was tracked only by `blocked_on` in the archived file. `scan.py` reads
`todos/*.md` only, so nothing else tracks it. `expire_unverified_accounts` still runs with
`--dry-run` (`.railway/railway.ts:56-59`), so squatted unverified accounts are never deleted.
The `railway.ts` comment still points at the archived todo 447. Both review rounds on #877 raised
this.

## Findings

1. **The owner step has no open tracker.** The owner reads a prod night's
   `[PRUNE] unverified accounts` counts, then opens a PR that drops `--dry-run` in
   `.railway/railway.ts`.
2. **The archived 447 frontmatter contradicts itself.** It has `status: completed` and
   `triage: already-done`, and also a live `blocked_on`.
3. **The `railway.ts:56` comment names todo 447**, which is now closed.

## Acceptance Criteria

- [x] The owner has read a prod night's `[PRUNE] unverified accounts` counts. The date and the
      quoted counts are recorded here. (completed 2026-10-11: 0 candidates nightly 10-01..10-11, see the Work Log)
- [x] `--dry-run` is removed from the expiry cron in `.railway/railway.ts`, and the comment names
      this todo or none.
- [x] Archived 447's `blocked_on` is removed, or renamed to a non-blocking note that points here.

## Work Log

### 2026-09-28 - Filed from PR #877 rounds 1 and 2 (todo sweep run 2026-09-28-2018)

### 2026-10-11 - Prod cron counts recorded (AC 1)

Read with the owner's approval from the Railway `forum-prune-cron` deploy logs (MCP `get-logs`, read-only). The
run on 2026-10-11 at 03:02:59 UTC (argv `expire_unverified_accounts --dry-run`) logged:

```
[PRUNE] unverified accounts: 0 candidate(s) older than 7d, 0 kept, would delete 0, 0 failed.
```

Every night from 2026-10-01 through 2026-10-11 logged the same line, 0 candidates each time. Removing
`--dry-run` deletes nothing today. AC 2 and AC 3 go ahead.

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-12-0349)

- `.railway/railway.ts`: the `forum-prune-cron` start command now runs `expire_unverified_accounts`
  without `--dry-run`, so unverified password accounts older than 7 days are deleted nightly. The
  comment names this todo and records the 0-candidate nights that cleared the change.
- `todos/archive/447-completed-p2-email-verification-follow-ups.md`: `blocked_on` is replaced by a
  non-blocking `follow_up` note that points here; its Work Log line no longer cites `blocked_on`.
- `backend/docs/patterns/security/authentication.md`: the "first run is a dry run" note now says
  production deletes, per this todo.
- Takes effect once `railway-apply` applies `.railway/railway.ts` after merge.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-12-0349)

- AC 2: `grep -n -e 'expire_unverified_accounts' -e 'dry-run' -e 'todo [0-9][0-9][0-9]' .railway/railway.ts` — evidence `.sweep-evidence/g2/485-ac1.txt` (not committed), last lines:

  ```text
  56:    // flushexpiredtokens (simplejwt's token_blacklist, todo 498) deletes
  61:    // expire_unverified_accounts deletes password accounts whose email was
  62:    // never verified. It ran with --dry-run until the owner had read the
  63:    // nightly "[PRUNE] unverified accounts: ..." counts (todo 485: 0
  66:    start: "/bin/sh -c \"python manage.py prune_forum_tombstones && python manage.py prune_link_preview_images && python manage.py flushexpiredtokens && python manage.py expire_unverified_accounts\"",
  ```

- AC 3: `sed -n 1,12p todos/archive/447-completed-p2-email-verification-follow-ups.md` — evidence `.sweep-evidence/g2/485-ac2.txt` (not committed), last lines:

  ```text
  source_review: "todos/archive/446-completed-p2-registration-email-pre-hijack.md"
  triage: already-done
  triaged: 2026-09-28
  follow_up: "Not blocking: dropping --dry-run from the expiry cron moved to todo 485."
  ---
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-12-0349)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
