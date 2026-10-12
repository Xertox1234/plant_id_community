---
status: pending
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
- [ ] `--dry-run` is removed from the expiry cron in `.railway/railway.ts`, and the comment names
      this todo or none.
- [ ] Archived 447's `blocked_on` is removed, or renamed to a non-blocking note that points here.

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
