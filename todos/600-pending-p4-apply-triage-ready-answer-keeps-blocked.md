---
status: pending
priority: p4
issue_id: "600"
tags: [todo-sweep, tooling]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# `apply-triage` keeps a triager's block after the owner answers "ready"

## Problem

When the triager classes a todo `needs-design` (or `blocked-*`) and the owner's Decide answer makes it
`ready`, `apply-triage` still writes the triager's class and `blocked_on` into the todo's frontmatter.
`_triage_fields` (`scripts/todos/state.py:484`) sets `triage: record["class"]` and copies
`record["blocked_on"]`. Its only override turns a todo INTO `blocked-owner`; nothing turns an answered one
into `ready`.

Seen three times. Most recently, todo 581 in run 2026-10-11-1929 committed `triage: needs-design` plus a
`blocked_on` asking the very question the owner had just answered. It was hand-fixed in the triage worktree
before PR #1039. Left unfixed, a todo the owner unblocked reads as still blocked, and a later scan that
honours `blocked_on` skips it. It surfaced earlier in runs 2026-10-11-1448 and -1434 (see memory notes).

## Acceptance Criteria

- [ ] When a todo's run entry is `ready` with an `owner_decision`, `apply-triage` writes `triage: ready` and
      no `blocked_on`, whatever the triager's class was.
- [ ] A test in `scripts/todos/` covers a `needs-design` record answered `ready`, and fails with the fix
      reverted.
- [ ] The existing todo-468 behaviour (an owner's own block becomes `blocked-owner`) is unchanged, and its
      tests still pass.

## Work Log
