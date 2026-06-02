---
status: pending
priority: p4
issue_id: "209"
tags: [flake8, lint, blog, tech-debt]
dependencies: []
---

# Investigate pre-existing flake8 violations in blog/ai_integration.py

## Problem

Committing todo 204 (commit `b3f7940`) was blocked by the pre-commit flake8 hook
flagging **4 pre-existing violations** in `backend/apps/blog/ai_integration.py` —
none introduced by that change (it touched lines 371–373 only). The commit had to
proceed with `SKIP=flake8`. Two things are worth investigating: (1) whether to fix
the 4 violations, and (2) why the hook flags whole-file pre-existing violations when
`backend/CLAUDE.md` claims flake8 "lints changed files incrementally."

## Findings

Source: `SKIP=flake8`-bypassed pre-commit run during the todo 204 commit
(2026-06-02). `flake8 backend/apps/blog/ai_integration.py` reports:

- `:120:9: F841` — local variable `action_type` assigned but never used. In
  `BlogAIPrompts.get_introduction_prompt`; the value is computed but never
  interpolated into the returned prompt (genuinely dead).
- `:192:121: E501` — line too long (139 > 120): a meta-description *example*
  string inside the `get_meta_description_prompt` docstring/f-string.
- `:193:121: E501` — line too long (132 > 120): the second example string, same
  block.
- `:321:121: E501` — line too long (179 > 120): the rate-limit error message
  f-string in `BlogAIIntegration.generate_content` (interpolates
  `AIRateLimiter.USER_LIMIT`/`STAFF_LIMIT`).

Meta-observation: `backend/CLAUDE.md` states lint "is pre-commit only, not
enforced in CI (≈3k pre-existing violations…); pre-commit lints changed files
incrementally." Here flake8 ran against the *whole* staged file and surfaced
violations on unchanged lines — so either the hook is not actually incremental,
or "incremental" means "files in the diff" (whole file), not "changed lines."
This is recurring friction (see memory `commit_hook_friction`).

## Proposed Solutions

### Option 1: Fix the 4 violations (Recommended)

- **Implementation:** delete the unused `action_type` block; wrap the three long
  lines (the two example strings can be split across adjacent string literals; the
  error f-string can be built in two pieces or use a shorter phrasing).
- **Pros:** removes the SKIP friction for the next person who touches this file;
  all trivial and behavior-preserving.
- **Cons:** none of substance; purely cosmetic churn in a file otherwise stable.
- **Effort:** ~10 minutes.
- **Risk:** low — no logic change (verify the `action_type` value is truly unused
  before deleting; run the blog AI tests after).

### Option 2: Leave the violations, only clarify the hook behavior

- Document precisely what the flake8 pre-commit hook lints (whole staged file vs
  changed lines) and reconcile the `backend/CLAUDE.md` wording. Don't touch the
  code.
- Pick this if the team prefers not to churn pre-existing-violation files
  piecemeal and would rather address the ~3k backlog in one sweep.

## Recommended Action

1. Confirm `action_type` (line ~120) is unused, then remove the assignment.
2. Reflow the three E501 lines (192, 193, 321) under 120 chars without changing
   output text.
3. Run `python manage.py test apps.blog.tests.test_ai_integration --keepdb` to
   confirm no behavior change.
4. Investigate the flake8 pre-commit config (`.pre-commit-config.yaml`) to confirm
   whether it passes whole files or only changed lines, and correct the
   `backend/CLAUDE.md` "lints changed files incrementally" claim if inaccurate.

## Technical Details

- File: `backend/apps/blog/ai_integration.py` (lines 120, 192, 193, 321 as of
  commit `b3f7940`).
- Hook config: `.pre-commit-config.yaml` (flake8 entry); repo policy in
  `backend/CLAUDE.md` → "CI" section.
- Related: memory `project_commit_hook_friction` (flake8/black/markdownlint
  commit-gate snags).

## Acceptance Criteria

- [ ] `flake8 backend/apps/blog/ai_integration.py` reports zero violations (if
      Option 1 chosen), OR a documented decision to defer with the hook behavior
      clarified (if Option 2).
- [ ] `apps.blog` test suite stays green after any edits.
- [ ] `backend/CLAUDE.md` flake8 wording matches the hook's actual scope
      (whole-file vs changed-lines).

## Work Log

### 2026-06-02 - Filed

- Created while committing todo 204; the 4 violations blocked the commit and were
  bypassed with `SKIP=flake8`. They are unrelated to the wagtail-ai 3.x migration.

## Notes

p4: trivial, non-CI-gated lint cleanup with a small process-clarification angle.
No urgency — flake8 is not a CI gate and these are 4 of ~3k repo-wide
pre-existing violations. Bundle into any future pass that already touches
`ai_integration.py` if not done standalone.
