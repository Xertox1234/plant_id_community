---
status: pending
priority: p4
issue_id: "478"
tags: [harness, todo-sweep]
dependencies: []
---

# Todo sweep: non-blocking findings from PR #873 round 1 (full-depth review)

## Problem

PR #873 moved the review stage's fan-out into `todo-review.js` (todo 472 item 2).
Round 1 used the bundled `/code-review` at high effort and found 10 issues. The PR
fixed 9 of them: the refute rule now covers every phrasing on a line, the routing
floor is checked in code, dead refute judgments keep the finding blocking, refuted
findings persist in the run file, the domain reviewers get the read-only git guard,
round 2 has a `rerun` step, the routing caps were raised, and paths are normalized.
These were left for later.

## Findings

1. **Each domain reviewer gets the whole changed-file list.** The ROUTING record has
   no per-agent file mapping, so `flutter-dart-reviewer` also sees the `.py` files on
   a mixed diff. This costs tokens and invites out-of-domain checklist findings. The
   orchestrator's routing table assigns files to agents, so ROUTING could carry
   `{agent: [files]}` and `domainPrompt` could pass each agent its own files.
2. **The null-judgment path has no test.** `candidates.forEach` keeps a finding
   blocking when its whole refute judgment is null. The stub harness can't make the
   inner `parallel` return null, so a mutation back to `judged.filter(Boolean)` is
   not caught.
3. **`MUST_ROUTE` repeats three rows of the orchestrator's routing table.** If the
   table changes, the workflow floor does not follow. A shared routing file, or a test
   that reads both, would keep them in step.

## Acceptance Criteria

- [ ] Domain reviewers get only their routed files, or this records why not.
- [ ] A test fails when a null refute judgment drops its finding.
- [ ] `MUST_ROUTE` and the orchestrator's table can't drift silently (shared source or
      a test).

## Work Log

### 2026-09-28 - Filed from PR #873 round 1

- Round 1 of the bundled `/code-review` (high effort); findings 8 and two gaps found
  while fixing it.
