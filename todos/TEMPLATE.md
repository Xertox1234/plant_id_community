---
status: pending
priority: pX
issue_id: "NNN"
tags: []
dependencies: []
---

<!--
COPY THIS FILE — do not edit in place.

Filename: NNN-pending-pX-short-slug.md
  NNN     = next zero-padded issue id (check `ls todos/*.md | tail -1`)
  pX      = p1 | p2 | p3 | p4
  slug    = lowercase-kebab-case, ≤ 6 words

Status transitions: pending → in_progress → completed (or blocked).
The filename status segment MUST match the frontmatter status value, and a todo
under archive/ MUST carry a terminal status (completed/complete/resolved/done/
fixed, or closed/skipped/superseded when the work was deliberately not done).
Both are enforced by scripts/check_archived_todo_status.py on every PR.

Required sections: Problem, Findings, Recommended Action, Technical Details,
Acceptance Criteria, Work Log. Optional sections (Proposed Solutions, Notes)
may be deleted entirely if not used — never leave them blank.
-->

# <Concise Issue Title>

## Problem

<1–3 sentences. What's broken or missing, and why it matters.>

## Findings

<Bullet list. Each bullet anchored to a file path, line number, command output,
or commit. State the discovery source (audit run, agent, human).>

## Proposed Solutions

### Option 1: <Recommended>

- **Implementation:** <how>
- **Pros:** <list>
- **Cons:** <list>
- **Effort:** <minutes / hours>
- **Risk:** <low / medium / high, with reason>

### Option 2: <Alternative>

<Same shape. Drop entire section if there is genuinely only one viable option.>

## Recommended Action

<Numbered list of concrete steps. Include code snippets, commands, file paths.>

## Technical Details

<File paths, line numbers, configuration examples, links to relevant patterns
under backend/docs/patterns/, web/docs/patterns/, etc.>

## Acceptance Criteria

- [ ] <Verifiable criterion — passes a test, produces a build, etc.>
- [ ] <Each criterion must be objectively checkable.>

<!--
A criterion that can only be settled OUTSIDE the repo — a key rotated at a
vendor, a DNS record, a dashboard toggle, a store submission — must record the
DATE and the OBSERVED RESULT here before this todo is archived:

- [x] Plant.id key rotated — 2026-09-13: GET plant.id/api/v3/usage_info with the
      old literal returns HTTP 401 "api key is not active"; the new key returns
      200 / active: true

"Verified" with no date and no observation is not evidence. External work leaves
no artifact in the tree, so this file is the only record there will ever be —
and nobody can re-derive it later. todos/archive/005-superseded-p1-api-key-
rotation-verification.md was archived with its rotation date left as the literal
template [DATE]; eleven months later a key from that incident was still live in
this public repo.

A criterion that MOVED rather than shipped stays `- [ ]` and names its target:

- [ ] Wire the export button → todo 283 (re-pointed 2026-07-26; promoted out of 263)

Checking off a relocated criterion falsifies the record. Archiving with a bare
unchecked criterion fails CI (scripts/check_archived_todo_status.py).
-->

## Work Log

### YYYY-MM-DD - <Event>

- <What happened, by whom, with what outcome.>

## Notes

<Priority rationale, related issue ids, trade-offs, deferred decisions.>
