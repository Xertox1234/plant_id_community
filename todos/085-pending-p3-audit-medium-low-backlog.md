---
status: pending
priority: p3
issue_id: "085"
tags: [audit-2026-05-17, backlog]
dependencies: []
source_review: "docs/audits/2026-05-17-full.md"
source_finding: "M1-M5,M7,M8,M10,M12,M14-M25,M26-M46,L1-L4,L8-L30"
---

# Medium / Low audit findings backlog (2026-05-17 full audit)

## Problem

The 2026-05-17 full audit logged 46 Medium and 31 Low findings. The audit fixed
Critical + security + N+1 only; the rest were deferred. This todo is the backlog
index — the authoritative per-finding detail (description, file:line, severity)
lives in the manifest. Forum-app (`apps/forum/`) M/L findings are tracked
separately in todo 084.

## Findings

See `docs/audits/2026-05-17-full.md` — Medium and Low tables. Notable Mediums
worth pulling forward:

- **M1** — Firebase token exchange links accounts by email, no `firebase_uid`
  binding (`apps/users/firebase_auth_views.py:252`) — security defence-in-depth.
- **M2** — Firebase Storage rules let any authenticated user read every user's
  private images (`firebase/storage.rules:24,33,44`) — privacy.
- **M3** — Unescaped LIKE wildcards in 5 search endpoints — query-cost DoS.
- **M22** — Unmigrated StreamField change (model 6 blocks, migration 0003 has 10) —
  `makemigrations blog` will generate a pending migration.

L7 is a confirmed false-positive (duplicate of H7) — no action needed.

## Recommended Action

Work the Medium findings first (M1/M2/M3/M22 have real user-facing/security
impact). Pull each finding from the manifest, verify it still applies, fix, and
update the manifest's `Status` column. Low findings are opportunistic cleanup.

## Acceptance Criteria

- [ ] Medium security/privacy findings (M1, M2, M3) addressed or risk-accepted.
- [ ] Remaining Medium/Low findings triaged — each fixed, or closed with rationale
      recorded in the manifest.

## Work Log

### 2026-05-17 - Created

- Deferred from the 2026-05-17 full audit (Phase 4) per user triage (fix scope was
  Critical + security + N+1 only).
