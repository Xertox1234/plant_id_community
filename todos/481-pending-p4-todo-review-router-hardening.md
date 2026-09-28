---
status: pending
priority: p4
issue_id: "481"
tags: [harness, todo-sweep]
dependencies: []
triage: needs-design
triaged: 2026-09-28
blocked_on: "Two choices: the completeness rule when the router is dead, and git-grep vs review_args flagging for unsafe file names."
owner_decision: "Dead router: the round counts as complete only when no .py outside apps/blog/ could need wagtail-by-content; switch the router to git -C WT grep for unsafe names (2026-09-28)"
---

# Todo sweep: router hardening (dead-router fallback, file names in the router prompt)

## Problem

Two low findings from the third live `todo-review` run on PR #873 (`wf_f1dbd020-8ac`),
both about the `code-review-orchestrator` routing step:

1. **A dead router forces a full rerun.** If the router returns nothing, the whole
   checklist lane is discarded and the round is `rerun`. A second rerun blocks the
   PR. Yet the path rules (`ROUTES`) alone can dispatch every row of the routing
   table except wagtail-by-content. A flaky router can block a PR that the path rules
   could have reviewed almost completely.
2. **File names go raw into the router's prompt.** `routingPrompt` lists
   `changed_files` and tells the Bash-only router to grep `'<worktree>/<path>'`. A
   file name holding `'` or `$(...)` could break out of that quoting. The git guard
   vets only git and gh, so any other program would run.

Filed from todo 478 finding 6. The owner asked for it as its own todo (2026-09-28).

## Recommended Action

1. On a null routing result, still dispatch `routeFiles(p.changed_files)`, and add
   `wagtail-reviewer` for any `.py` outside `apps/blog/` (the content grep can't be
   done without the router). Record `routing_failed: true`. Decide whether the round
   is still complete, or complete only when no `.py` could need wagtail-by-content.
2. Tell the router to grep through the guard-vetted `git -C WT grep -l -e … -- <path>`,
   or have `review_args` flag any changed file name holding shell metacharacters
   or a newline, and route that PR by path rules only.

## Acceptance Criteria

- [ ] A dead router still dispatches the path-routed reviewers, and the round's
      completeness rule for that case is decided and tested.
- [ ] A changed file named with `'` or `$(...)` cannot run a command through the
      router's grep; a test covers it.

## Work Log

### 2026-09-28 - Filed from todo 478

- Split out of 478 finding 6 at the owner's request, and re-pointed there.
