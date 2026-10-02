---
status: pending
priority: p4
issue_id: "515"
tags: [web, testing]
dependencies: []
---

# Diagnose condition backend tie: non-blocking findings from PR #927 (todo 502)

## Problem

PR #927 (todo 502) merged after two review rounds in todo-sweep run 2026-10-02-0118. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:163`** (medium, round 1, round 2). The test reads ../../../../backend/apps/plant\_identification/models.py with node:fs and parses it by regex. It fails if the web package is tested without the backend checkout (web-only Docker or CI job), and if models.py is reformatted (single quotes, a tuple or constant refactor).
   Suggested: Confirm every web test job checks out backend/. Otherwise compare against a shared fixture, such as a generated JSON of the choices. Keep the expect(field).not.toBeNull() guard so a regex miss fails loudly.
   Also reported: The parity test reads backend/apps/plant\_identification/models.py from disk by relative path. It would fail wherever web tests run without the backend checked out (e.g. a web-only Docker context or sparse checkout).
   Also reported: Test reads backend/models.py from disk via a relative \_\_dirname path and a regex. It works today (choices match), but it couples the web test to the monorepo layout and fails if web is tested in isolation, e.g. a web-only Docker context.

2. **`web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:165`** (low, round 2). The drift test reads backend/apps/plant\_identification/models.py by relative path and parses it with a regex. It breaks if web tests run where backend/ is not checked out, or if the choices are reformatted (single quotes, a constant). The two guard expects fail loudly rather than pass silently.
   Suggested: Acceptable as is. If web tests ever run without the backend tree, switch to a shared JSON fixture or an OpenAPI-derived list.

3. **`web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:167`** (low, round 1, round 2). The field regex `plant_condition = models.CharField\([\s\S]*?choices=\[` is not bounded to the field. If the choices move to a TextChoices or a constant, it matches the next field's `choices=[` (models.py:886). The test still fails, but the diff blames the wrong field.
   Suggested: Stop the lazy match at the field's closing paren, for example `plant_condition = models\.CharField\(((?:(?!models\.)[\s\S])*?)\n    \)`, and then search for `choices=\[` inside that slice. Or assert that the match index is before the next `models.` declaration.
   Also reported: The regex `plant_condition = models\.CharField\([\s\S]*?choices=\[` is not bounded to the field. If plant\_condition moves to `choices=SomeChoices.choices` or a named constant, the lazy match runs on to a later field's `choices=[`. The test then fails with a diff against an unrelated field, which hides the real cause. It still fails loudly, so this cannot pass by mistake.

4. **`web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:170`** (low, round 2). The tuple regex only matches `("key", "label")`. A new model choice written another way, such as `("dormant", _("Dormant"))` (gettext) or with single quotes, is skipped silently. If web also lacks it, the test still passes, so the backend tie fails open for exactly the drift it guards.
   Suggested: Also count the tuple entries in the captured block, e.g. `field[1].match(/^\s*\(/gm).length`, and assert it equals backendChoices.length. Then any choice the regex cannot parse fails the test instead of being dropped.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #927 review rounds 1-2.
