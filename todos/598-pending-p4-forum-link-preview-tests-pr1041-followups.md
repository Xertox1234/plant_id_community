---
status: pending
priority: p4
issue_id: "598"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1041 (todo 576)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1041 (link-preview test follow-ups from PR #1015). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1041 (todo sweep run 2026-10-11-1448, group g13, todos 576); follow-ups: verified.

1. **low** `backend/apps/forum_host/tests/conftest.py:66` Docstrings now say hung_up is reserved for a mid-drip hang-up. But a client that sends RST before any request makes the first recv() raise ConnectionResetError, which the OSError handler records as hung_up=True. The documented contract is wider than the code.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1041 (todo 576).
