---
status: pending
priority: p4
issue_id: "475"
tags: [harness, todo-sweep]
dependencies: []
---

# Todo sweep: non-blocking findings from PR #870 round 1 (todo 468 slice C)

## Problem

Round 1 of PR #870 fixed a masking regression: the backend reads `.env` through
python-decouple, which keeps an inline `# …`, so the comment-stripped value alone masked
less than main did. It also fixed three cheap findings: a NUL byte in any todo's
`source_review` crashing `plan_review`, staging an untracked sibling todo, and the
verifier and worker docs disagreeing with the new wrapped-line rule. These three were left
for later.

## Findings

1. **A sibling with a multi-line `source_review` is skipped silently.** Its pointer
   dangles after the `-COMPLETED` rename, and no note says so (`scripts/todos/land.py`,
   `_siblings`).
2. **`source_review : x` (space before the colon) gets a duplicate key.**
   `_unsettable_key` passes it, and `todofile.set_fields` appends a second
   `source_review:` line.
3. **Common short passwords are masked everywhere.** When the `DATABASE_URL` user and
   password are both the word `postgres`, every `postgres` in an evidence tail becomes
   `***`, so a tail reads `django.db.backends.***ql`. That is safe, just hard to read.

## Acceptance Criteria

- [ ] Archive notes every sibling it could not rewrite, with a test.
- [ ] A `source_review : x` sibling is rewritten in place or skipped with a note, with
      a test.
- [ ] Masking a password that is also a common word (the DB user, the scheme) is either
      kept on purpose and recorded here, or narrowed, with a test.

## Work Log

### 2026-09-28 - Filed from PR #870 round 1
