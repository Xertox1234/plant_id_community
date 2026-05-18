---
name: audit
description: Run a structured code audit with manifest tracking, per-fix verification, and pattern codification
---

# Code Audit

You are running a structured code audit. The scope is: $ARGUMENTS (defaults to
"full" if empty). Valid scopes: `full`, or a single domain name from the table
below (e.g. `security`, `performance`, `wagtail`).

This workflow enforces finding tracking, per-fix verification, and a persistent
audit trail. **Never skip steps.**

## Specialist Agent Mapping

Each audit domain maps to review agents in `.claude/agents/`. Launch them as
subagents during Phase 2 discovery.

| Audit Domain      | Agent(s)                                                       |
| ----------------- | -------------------------------------------------------------- |
| `security`        | `security-reviewer`                                            |
| `performance`     | `performance-reviewer`                                         |
| `django-drf`      | `django-drf-reviewer`, `api-design-reviewer`                   |
| `wagtail`         | `wagtail-reviewer`                                             |
| `react-typescript`| `react-typescript-reviewer`                                    |
| `flutter`         | `flutter-dart-reviewer`, `flutter-firebase-reviewer`           |
| `firebase`        | `firebase-cloudfunction-reviewer`                              |
| `celery`          | `celery-async-reviewer`                                        |
| `testing`         | `test-quality-reviewer`                                        |

**`full` scope:** launch every agent above whose domain has changed/relevant
files. Batch in groups of ~4 to avoid overwhelming context.
**Named scope:** launch only that domain's agent(s).

**Agent prompt template for discovery:**

```text
You are auditing the plant_id_community codebase for [DOMAIN] issues.

Scope: [files/modules to focus on, or "full codebase"]

For each finding, report:
- A concise description of the issue
- The exact file path and line number(s)
- Severity: Critical / High / Medium / Low
- The specific pattern or rule being violated (reference docs/rules/,
  the relevant */docs/patterns/ doc, or docs/LEARNINGS.md where applicable)

Do NOT fix anything — only report findings. Do NOT report issues already handled
correctly. Focus on genuinely new issues, not style preferences.
```

## Phase 1: Setup

1. Record the baseline for the stacks the scope touches:
   - Backend: `cd backend && python manage.py test --noinput` (note pass count),
     `python manage.py check`
   - Web: `cd web && npm run test`, `npm run type-check`, `npm run lint`
   - Mobile: `cd plant_community_mobile && flutter test`, `flutter analyze`
2. Check `docs/audits/CHANGELOG.md` for prior findings that may still be relevant.
3. Create the manifest `docs/audits/YYYY-MM-DD-[scope].md` from `docs/audits/TEMPLATE.md`.
4. Record the baseline in the manifest header.
5. Capture the current branch: `git branch --show-current` (fall back to
   `git rev-parse --abbrev-ref HEAD` on detached HEAD).
6. Create and enter an audit worktree — all later phases run from it:

   ```bash
   git worktree add .worktrees/audit-$(date +%Y-%m-%d) HEAD
   ```

   (or use `EnterWorktree`). After the Phase 7 commit, remove it:
   `git worktree remove .worktrees/audit-YYYY-MM-DD`.

## Phase 2: Discovery

1. **Launch the specialist agents** for the scope (see mapping table), in
   parallel batches of ~4, using the discovery prompt template.
2. As each agent completes, **deduplicate** findings against the previous audit
   manifest (mark already-fixed items `false-positive`) and against other agents
   in this run (combine duplicates).
3. For each genuinely new finding, **verify it in current code** — read the file
   at the reported line, grep for the flagged pattern. If the code does not match,
   mark `false-positive` with evidence.
4. Write all verified findings to the manifest with status `open` and the
   reporting agent.

## Phase 2.5: Research

Validate Phase 2 findings against current documentation before triage.

1. **Launch `docs-researcher` subagents in parallel** — one per domain that has
   at least one finding. Skip a domain with zero findings; skip the whole phase
   if Phase 2 found nothing.
2. Dispatch prompt per researcher (fill in `[DOMAIN]` and the findings list):

   ```text
   You are validating audit findings for the [DOMAIN] domain against current
   library documentation.

   Findings to validate:
   [paste this domain's findings — for each: ID, description, file:line, the rule cited]

   For EACH finding, check current documentation via Context7
   (resolve-library-id then query-docs) when the finding hinges on external
   library/framework behavior. Return exactly one verdict per finding:
   - confirmed     — current docs agree the finding is valid
   - better-fix    — real finding, but docs show a cleaner fix; describe it
   - contradicted  — docs say the flagged pattern is fine; cite the doc
   - not-applicable — does not hinge on external library behavior (IDOR,
     missing ownership check, N+1, dead code) — no doc call needed

   Non-`not-applicable` verdicts MUST cite the specific doc (library + section).
   If you incidentally notice an unmet current-doc best practice in code you
   already viewed, report it as a NEW finding candidate with file:line + citation.
   Do NOT fix anything.
   ```

3. Update each finding's manifest `Research` column: `confirmed` /
   `better-fix` (record the doc-informed approach) / `contradicted ⚠` (stays
   `open` — user decides at triage) / `—` for `not-applicable`.
4. Verify any new finding candidate in current code before adding it to the
   manifest (same discipline as Phase 2 step 3).
5. **Show the user the full findings table** and ask which to fix now vs defer,
   noting that `contradicted ⚠` findings may be false positives.

## Phase 3: Fix (one at a time)

For **each** finding the user wants fixed:

1. Manifest status → `fixing`.
2. Read the code; make the fix (minimal, surgical — no drive-by improvements).
3. Run the targeted tests for the affected files; fix until they pass.
4. **Verify** the fix landed — re-read/grep the changed code; run the specific
   test file(s).
5. **kimi-review** the fix from the worktree root:

   ```bash
   kimi-review --scope "[one-line fix description]" --profile plant_id --rules [domain]
   ```

   - **CRITICAL**: stop the loop, surface to the user — do not mark `verified`
     until resolved.
   - **WARNING**: fix inline when small and in-scope; otherwise record it in the
     manifest Verification column and create a deferred todo (Phase 4).
   - **SUGGESTION**: proceed; note in the manifest if worth codifying.
6. Manifest status → `verified`; Verification column → what you checked.

**Critical rules:** one finding at a time, never batch; never mark `verified`
without running tests; re-read the file to confirm the change is present.

## Phase 4: Defer

For deferred findings:

1. Create a todo `todos/NNN-pending-pX-slug.md` (next free `NNN`, priority
   `p1`–`p4`) following `todos/TEMPLATE.md`. If the finding came from a review
   doc, add `source_review` / `source_finding` frontmatter per the root
   `CLAUDE.md` "Review Doc Tracking" convention.
2. Manifest status → `deferred` with a link to the todo.
3. Record the rationale in the manifest's Deferred Items table.
4. For straightforward boilerplate/test-only deferred work, `kimi-write` may
   generate a first pass — review before committing.

## Phase 5: Close

1. Re-run the full baseline suite for the affected stacks — all green.
2. Update the manifest summary table with final counts.
3. Append an entry to `docs/audits/CHANGELOG.md` (append-only).
4. Report the final summary: findings (C/H/M/L), verified, deferred (with
   todo links), false-positive, open (**must be 0**).
5. Do not ask about committing yet — proceed to Phase 6.

## Phase 6: Code Review

1. Invoke the `code-review-orchestrator` agent (`.claude/agents/code-review-orchestrator.md`)
   on the multi-file diff from Phase 3 — it routes changed files to the relevant
   domain reviewers and deduplicates findings.
2. CRITICAL / HIGH findings → fix immediately (Phase 3 discipline).
3. MEDIUM → judgment call; LOW → defer unless a trivial one-liner.
4. Re-run tests / type checks after any review fixes.

## Phase 7: Commit Fixes

1. Stage all changed files (code fixes + manifest + changelog + new todos).
2. Commit: `fix: resolve [scope] audit findings ([N] verified, [M] deferred)`.
3. Per project policy, do not push to `main` — open a PR. Ask the user first.

## Phase 8: Codify

After fixes are committed, extract reusable knowledge. **Run the `codify` skill**
(`.claude/skills/codify/SKILL.md`) — it routes findings to `docs/rules/<domain>.md`
(one-line binding rules), the `*/docs/patterns/` libraries (multi-line patterns),
`docs/LEARNINGS.md` (incidents), and the review agents (new checks). Codify the
complete Phase 3 picture, including corrections triggered by kimi-review.
Commit documentation separately: `docs: codify patterns and learnings from [scope] audit`.

## Rules

- **The manifest is the source of truth.** Every finding and status change is in it.
- **Zero open findings at close** — everything verified, deferred (with todo), or
  false-positive.
- **No documentation during the fix phase** — codify only in Phase 8.
- **kimi-review is not optional** — every Phase 3 fix passes it before `verified`.
- **Deferred is not dropped** — every deferred item has a todo with priority and
  rationale.
- **The changelog is append-only.**
