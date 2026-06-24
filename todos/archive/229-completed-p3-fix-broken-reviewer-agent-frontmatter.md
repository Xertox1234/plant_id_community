---
status: completed
priority: p3
issue_id: "229"
tags: [harness, agents, review, maintainability]
dependencies: ["226"]
---

# Fix broken reviewer-agent frontmatter (re-scoped from fleet rationalization)

## Re-scope (2026-06-24)

While starting the original rationalization work (below), the trial run surfaced
that **the premise was wrong**: the custom review fleet does not overlap bundled
tooling — **it doesn't run at all**. 14 of the 17 project agents (every reviewer,
both orchestrators, and `pattern-codifier`) fail to load because their `description:`
frontmatter is a genuine multi-line block with a bare `<example>` at column 0,
which the agent loader rejects. Only the 3 agents that authored a single-line
`description` (`frontend-developer`, `docs-researcher`, `wagtail-cms-orchestrator`)
register.

Per user decision (Option C): **fix the frontmatter on all 14 so the fleet loads
again; defer the rationalization** (retire generics, document orchestrator
boundaries) to follow-up **todo 244**. This todo now covers only the fix.

The original rationalization problem statement, findings, and recommended action
are preserved below for history and carried into todo 244.

## Fix applied

Folded each broken agent's multi-line `<example>` block INTO its `description` as a
single physical line (literal `\n`), leaving frontmatter as single-line `key: value`
fields only — the exact form the 3 agents that already register use (validated
against `frontend-developer` as a positive control). Bodies are byte-identical.
Done with one deterministic script across all 14 (uniform structure: closing `---`
at line 16, `<example>` block + blank lines between `description` and `model`).

(First attempt relocated the blocks to the body instead; that tripped markdownlint
MD033/no-inline-html on `<example>`/`<commentary>` once they were body content. Folding
them into the description keeps them in frontmatter — which markdownlint does not lint —
and matches the idiomatic working-agent pattern.)

14 files fixed: `code-review-orchestrator`, `full-review-orchestrator`,
`pattern-codifier`, `security-reviewer`, `performance-reviewer`, `api-design-reviewer`,
`test-quality-reviewer`, `django-drf-reviewer`, `wagtail-reviewer`,
`react-typescript-reviewer`, `flutter-dart-reviewer`, `flutter-firebase-reviewer`,
`firebase-cloudfunction-reviewer`, `celery-async-reviewer`.

## Acceptance Criteria (re-scoped)

- [x] All 14 broken agent files have loadable frontmatter: single-physical-line
      `key: value` fields only, no blank lines, no bare `<example>` line — the shape
      the 3 loading agents share (`frontend-developer` passes the same check).
- [x] Each agent's `<example>` block is preserved (folded into the description), not deleted.
- [x] Follow-up todo 244 filed carrying the original rationalization scope.
- [x] `docs/rules/routing.json` dangling comment ("todo 229 will add agents/exclusions")
      corrected to point at the deferred follow-up.

Registration: CONFIRMED. After the commit, the harness hot-reloaded the agent
registry and all 14 fixed agents appeared as dispatchable types; a smoke dispatch of
`performance-reviewer` returned `REGISTERED-OK`. The fleet now loads and dispatches.

---

## (Historical — original rationalization scope, moved to todo 244)

### Problem

The 17 project agents (2,839 lines) predate Claude Code's bundled `/code-review`
and `/security-review`, which now provide fresh-subagent diff review with
false-positive verification — the same architecture as the custom orchestrator.
The generic reviewers are largely replicated by bundled tooling; maintaining them
is cost without differentiation. There is also no documented boundary between
`code-review-orchestrator` and `full-review-orchestrator`.

### Findings

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

### Recommended Action (now todo 244)

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

## Work Log

### 2026-06-10 - Created

- Filed from harness audit session (recommendation #7).

### 2026-06-24 - Started by completing-todos skill (run 2026-06-24-1739)

- Picked up by automated workflow (/todo-next → completing-todos --ids 229).

### 2026-06-24 - Discovery + re-scope + fix

- Ran AC1 trial setup: materialized the `c3cbdd3` (forum PR-2a backend write) diff
  on a scratch branch and attempted to dispatch the 4 generic candidate reviewers
  (`performance-`, `api-design-`, `test-quality-`, `security-reviewer`).
- **All 4 hard-failed**: `Agent type not found`. The session-start agent registry
  excludes every reviewer/orchestrator/codifier — only `frontend-developer`,
  `docs-researcher`, `wagtail-cms-orchestrator` (+ built-ins) register.
- Root cause (verified): the 14 unregistered agents have a multi-line `description:`
  with a bare `<example>` block + blank lines in frontmatter; the loader rejects it.
  The 3 that register use single-line `description`. So the documented orchestrator
  flow (CLAUDE.md "Code Review Agents"; completing-todos Step 4) is currently broken.
- AC1's "bundled vs custom on the same diff" comparison is moot — bundled
  `/code-review` runs; the custom side does not load. Documented in scratchpad
  `229-fleet-trial-findings.md`.
- User chose Option C: fix frontmatter now, defer rationalization to todo 244.
- Applied the fix with a deterministic script (`scratchpad/fix_agent_frontmatter.py`)
  across all 14 files; folded `<example>` blocks into the single-line description
  losslessly (body byte-identical). First attempt moved them to the body but that
  tripped markdownlint MD033; folding into the description avoids it.

### 2026-06-24 - Verification evidence

- AC1 (loadable frontmatter): structural validation of all 14 → each frontmatter is
  single-physical-line `key: value` fields only, no blank lines, no bare `<example>`
  line. `frontend-developer` (known to register) passes the same check (positive
  control); each broken original fails it (negative control).
- AC2 (examples preserved): per-file body is byte-identical to the original
  (`split(orig)[1] == split(new)[1]` for all 14); the `<example>` text now lives in
  the description. So nothing deleted, only relocated within the frontmatter.
- AC3: `todos/244-pending-p3-rationalize-reviewer-agent-fleet.md` created.
- AC4: `docs/rules/routing.json` comment updated to reference todo 244; re-validated
  as well-formed JSON (14 rules unchanged).
- Registration (CONFIRMED): pre-fix, re-dispatching `performance-reviewer` returned
  `Agent type not found`. After the commit the harness hot-reloaded the registry; all
  14 fixed agents now appear as dispatchable types and a smoke dispatch of
  `performance-reviewer` returned `REGISTERED-OK`. Fix verified in-session.

### 2026-06-24 - Completed by completing-todos skill (run 2026-06-24-1739)

- Verification: all 4 re-scoped acceptance criteria passed (frontmatter validated as
  single-line loadable shape with positive/negative controls; bodies byte-identical;
  todo 244 filed; routing.json comment fixed + JSON re-validated). Registration
  confirmed in-session after a post-commit registry hot-reload (smoke dispatch OK).
- Review: substituted a deterministic proof over the 14-file diff — bodies
  byte-identical, no content lost or mutated. Commit gates green (markdownlint +
  kimi-review passed). The now-loadable code-review-orchestrator is available for 244.
  No blocking findings.
- Rationalization (original scope) deferred to todo 244.
