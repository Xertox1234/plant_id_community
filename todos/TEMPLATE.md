<!--
COPY THIS FILE — do not edit in place.

Filename: NNN-pending-pX-short-slug.md
  NNN     = next zero-padded issue id (check `ls todos/*.md | tail -1`)
  pX      = p1 | p2 | p3 | p4
  slug    = lowercase-kebab-case, ≤ 6 words

Status transitions: pending → in_progress → completed (or blocked).
The filename status segment MUST match the frontmatter status value.

Required sections: Problem, Findings, Recommended Action, Technical Details,
Acceptance Criteria, Work Log. Optional sections (Proposed Solutions, Notes)
may be deleted entirely if not used — never leave them blank.
-->

---
status: pending
priority: pX
issue_id: "NNN"
tags: []
dependencies: []
---

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

## Work Log

### YYYY-MM-DD - <Event>

- <What happened, by whom, with what outcome.>

## Notes

<Priority rationale, related issue ids, trade-offs, deferred decisions.>
