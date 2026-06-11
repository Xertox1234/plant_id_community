---
status: pending
priority: p3
issue_id: "229"
tags: [harness, agents, review, maintainability]
dependencies: ["226"]
---

# Rationalize the 17-agent reviewer fleet against bundled /code-review and /security-review

## Problem

The 17 project agents (2,839 lines) predate Claude Code's bundled `/code-review`
and `/security-review`, which now provide fresh-subagent diff review with
false-positive verification — the same architecture as the custom orchestrator.
The generic reviewers are largely replicated by bundled tooling; maintaining them
is cost without differentiation. There is also no documented boundary between
`code-review-orchestrator` and `full-review-orchestrator`.

## Findings

- Generic reviewers with high overlap vs bundled commands: `test-quality-reviewer`,
  `performance-reviewer`, `api-design-reviewer`, `security-reviewer` (bundled
  `/security-review` overlaps the last).
- Differentiated domain reviewers worth keeping: `wagtail-reviewer`,
  `django-drf-reviewer` (project-gotcha-loaded), `flutter-dart-reviewer`,
  `flutter-firebase-reviewer`, `firebase-cloudfunction-reviewer`,
  `celery-async-reviewer`, `react-typescript-reviewer` (project-pattern-loaded).
- `full-review-orchestrator.md` (562 lines) vs `code-review-orchestrator.md`
  (186 lines): no "when to use which" doc; audit found unclear interaction with
  the `/audit` skill as well.
- Agent description frontmatter is always-loaded context; bodies are not.
- Discovery source: 2026-06-10 harness audit (Explore agent report + community
  research on fleet bloat, e.g. wshobson/agents#93).

## Recommended Action

1. Trial: run bundled `/code-review` on a real branch alongside
   code-review-orchestrator; compare findings coverage for generic dimensions.
2. Retire (git rm) generic reviewers whose findings are subsumed; fold any
   project-specific checks they carried into the surviving domain reviewers or
   docs/rules checklists.
3. Add a short "when to use which" section to CLAUDE.md (Code Review Agents
   table): orchestrator = domain review of a diff; full-review = whole-repo
   sweep; bundled /code-review = quick generic pass.
4. Trim agent frontmatter descriptions to one terse line each (always-loaded
   context tax).

## Technical Details

- Depends loosely on todo 226 (routing consolidation) — retiring agents means
  updating routing tables; do 226 first so it is one edit.
- Keep kimi-review commit gate untouched; it is a different layer.

## Acceptance Criteria

- [ ] Side-by-side comparison documented (bundled vs custom on the same diff).
- [ ] Each retired agent's unique checks are either codified elsewhere or
      explicitly declared redundant in the work log.
- [ ] CLAUDE.md documents the orchestrator/full-review/bundled boundaries.

## Work Log

### 2026-06-10 - Created

- Filed from harness audit session (recommendation #7).
