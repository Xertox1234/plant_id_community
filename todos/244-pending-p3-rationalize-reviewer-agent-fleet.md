---
status: pending
priority: p3
issue_id: "244"
tags: [harness, agents, review, maintainability]
dependencies: ["229"]
---

# Rationalize the reviewer agent fleet against bundled /code-review and /security-review

## Context

Split out from todo 229. Todo 229 discovered the custom review fleet was
non-functional (14 agents failed to load due to malformed frontmatter) and fixed
the frontmatter so the fleet loads again. This todo is the **original 229
rationalization scope**, deferred so it runs against a fleet that actually works.

Do this only after confirming (fresh session) that the 14 agents fixed in todo 229
now register as dispatchable agent types — otherwise the comparison cannot run.

## Problem

The project agents predate Claude Code's bundled `/code-review` and
`/security-review`, which now provide fresh-subagent diff review with
false-positive verification — the same architecture as the custom orchestrator.
The generic reviewers are largely replicated by bundled tooling; maintaining them
is cost without differentiation. There is also no documented boundary between
`code-review-orchestrator` and `full-review-orchestrator`.

## Findings (from 229)

- Generic reviewers with high overlap vs bundled commands: `test-quality-reviewer`,
  `performance-reviewer`, `api-design-reviewer`, `security-reviewer` (bundled
  `/security-review` overlaps the last).
- Differentiated domain reviewers worth keeping: `wagtail-reviewer`,
  `django-drf-reviewer` (project-gotcha-loaded), `flutter-dart-reviewer`,
  `flutter-firebase-reviewer`, `firebase-cloudfunction-reviewer`,
  `celery-async-reviewer`, `react-typescript-reviewer` (project-pattern-loaded).
- `full-review-orchestrator.md` (562 lines) vs `code-review-orchestrator.md`
  (186 lines): no "when to use which" doc; unclear interaction with `/audit`.
- Much of the domain reviewers' enforceable knowledge already lives in
  `docs/rules/<domain>` checklists (auto-injected) + CLAUDE.md "Critical Gotchas".

## Recommended Action

1. Trial: run bundled `/code-review` on a real diff alongside the (now-loadable)
   custom reviewers; compare coverage for the generic dimensions. The 229 trial
   target `c3cbdd3` (forum PR-2a backend write — views/serializers/tests) is a good
   reproducible diff. Setup: `git switch -c trial c3cbdd3 && git reset c3cbdd3~1 && git add -N .`.
2. Retire (git rm) generic reviewers whose findings are subsumed; fold any
   project-specific checks they carried into surviving domain reviewers or
   `docs/rules` checklists.
3. Add a "when to use which" section to CLAUDE.md (Code Review Agents table):
   orchestrator = domain review of a diff; full-review = whole-repo sweep;
   bundled /code-review = quick generic pass. (CLAUDE.md edits are Auto-Mode-gated.)
4. Trim agent frontmatter descriptions to one terse line each.
5. If agents are retired, update `docs/rules/routing.json` `_comment` and consider
   whether the deferred `agents`/`exclusions` routing belongs here.

## Technical Details

- Editing `.claude/` agents and root `CLAUDE.md` is blocked under Auto Mode — ask
  the user to disable it first.
- Keep the kimi-review commit gate untouched; it is a different layer.
- The `c3cbdd3` trial showed the comparison is only meaningful once the fleet loads
  (todo 229) — verify registration in a fresh session before running step 1.

## Acceptance Criteria

- [ ] Side-by-side comparison documented (bundled vs custom on the same diff).
- [ ] Each retired agent's unique checks are either codified elsewhere or
      explicitly declared redundant in the work log.
- [ ] CLAUDE.md documents the orchestrator/full-review/bundled boundaries.

## Work Log

### 2026-06-24 - Created

- Split from todo 229 (fix-vs-rationalize). 229 fixed the broken frontmatter;
  this carries the rationalization once the fleet is confirmed loadable.
