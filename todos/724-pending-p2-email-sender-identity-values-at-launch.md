---
status: pending
priority: p2
issue_id: "724"
tags: [backend, email, legal, owner, launch]
dependencies: ["703"]
triage: blocked-owner
triaged: 2026-11-21
blocked_on: "Launch: the owner's sender name and mailing address"
---

# At launch: set the email sender name and mailing address on Railway (from todo 703)

## Problem

Todo 703 ships the sender-identity settings and footer with the values blank (owner decision 2026-11-20: operator blanks wait for launch).

## Findings

- The values are the operator's legal sender name and a mailing address, which the owner supplies at launch.

## Recommended Action

At launch, set both settings on Railway, then check one received email's footer.

## Technical Details

- Settings and their Railway declaration are added by todo 703 (`.railway/railway.ts`).

## Acceptance Criteria

- [ ] Both settings are set on Railway — record the date and one received email's footer here
      (moved from 703 on 2026-11-21).

## Work Log

### 2026-11-21 - Filed

- Filed from sweep run 2026-11-20-2202 on the owner's decision of 2026-11-21: these criteria were
  re-pointed here because they can only be checked after the parent's PR merges, or need the owner.
