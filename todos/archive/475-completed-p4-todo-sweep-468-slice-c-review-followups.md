---
status: completed
priority: p4
issue_id: "475"
tags: [harness, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-09-30
owner_decision: "Finding 3: keep masking common-word passwords such as postgres and record why (2026-09-28)"
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

- [x] Archive notes every sibling it could not rewrite, with a test.
- [x] A `source_review : x` sibling is rewritten in place or skipped with a note, with
      a test.
- [x] Masking a password that is also a common word (the DB user, the scheme) is either
      kept on purpose and recorded here, or narrowed, with a test.

## Work Log

### 2026-09-28 - Filed from PR #870 round 1

### 2026-09-30 - Implemented by the todo sweep (run 2026-10-01-0121)

- Finding 1: `land._siblings` now returns the siblings it can rewrite and a `{path, reason}` for every
  one it can't (multi-line value, a key line it can't find, untracked, unreadable frontmatter that
  names the review doc). `archive` writes one Work Log bullet per skipped sibling, saying where to point
  it by hand, and returns them as `review.skipped_siblings`.
- Finding 2: `todofile.key_line` matches `key :` as well as `key:`, and `todofile.field_problem` is now
  the one check behind both `set_fields` and land's phase-1 `_unsettable`. A `source_review : x` line
  is rewritten in place; a key set on a line it can't find (`"source_review": x`) refuses instead of
  being duplicated.
- Finding 3, kept on purpose (owner decision 2026-09-28): a password that is also a common word, such as
  `postgres`, stays masked everywhere. The mask can't tell the password from the word, so any narrowing
  leaves the password readable where it is printed, in a tail committed to a public repo. The only cost is
  readability (`django.db.backends.***ql`). The reason is in `_env_secrets`' docstring and a test pins it.
- Tests: new `475:` checks in `scripts/todos/test_land.py` and `scripts/todos/test_todofile.py`. Against
  the merge-base code, the finding-1 and finding-2 checks fail.

### 2026-09-30 - Verified by the todo sweep (run 2026-10-01-0121)

- AC 1: `python3 scripts/todos/test_land.py` — evidence `.sweep-evidence/g5/475-ac0.txt`, last lines:

  ```text
    PASS  m9: the verify-only heading is 'Checked by'
    PASS  m9: no worker Work Log heading satisfies Land's Verified-note check
    PASS  m9: flip_acs's own heading still does

  All checks passed.
  ```

- AC 2: `python3 scripts/todos/test_todofile.py && python3 scripts/todos/test_land.py` — evidence `.sweep-evidence/g5/475-ac1.txt`, last lines:

  ```text
    PASS  m9: the verify-only heading is 'Checked by'
    PASS  m9: no worker Work Log heading satisfies Land's Verified-note check
    PASS  m9: flip_acs's own heading still does

  All checks passed.
  ```

- AC 3: `grep -n "Finding 3, kept on purpose" todos/475-pending-p4-todo-sweep-468-slice-c-review-followups.md && python3 scripts/todos/test_land.py` — evidence `.sweep-evidence/g5/475-ac2.txt`, last lines:

  ```text
    PASS  m9: the verify-only heading is 'Checked by'
    PASS  m9: no worker Work Log heading satisfies Land's Verified-note check
    PASS  m9: flip_acs's own heading still does

  All checks passed.
  ```

### 2026-09-30 - Completed by the todo sweep (run 2026-10-01-0121)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
