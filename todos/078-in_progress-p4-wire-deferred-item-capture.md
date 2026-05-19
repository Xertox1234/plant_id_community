---
status: in_progress
priority: p4
issue_id: "078"
tags: [harness, hooks, skills]
dependencies: []
---

# Stop hook checks a deferred-items file that nothing writes

## Problem

`.claude/settings.json` registers a `Stop` hook that reads
`/tmp/plant-id-deferred.txt` and reminds the user about deferred items not yet
tracked as todos. No code path ever writes that file, so the hook is currently
dead plumbing.

## Findings

- `.claude/settings.json` — `Stop` hook greps `/tmp/plant-id-deferred.txt`.
- Ported from OCRecipes, where the audit/work flow appends to its deferred file.
- The `audit` skill's Phase 4 and the `codify` skill route deferred work into
  `todos/` files directly — neither writes the `/tmp` capture file.

## Proposed Solutions

### Option 1: Wire the skills to append (Recommended)

- **Implementation:** When the `audit` or `codify` skill identifies a deferral
  it does not immediately file as a todo, append a one-line entry to
  `/tmp/plant-id-deferred.txt`. The Stop hook then nudges the user at session end.
- **Pros:** Makes the hook functional; matches OCRecipes' "create todos inline,
  don't drop deferrals" intent.
- **Cons:** Adds a step to two skill docs.
- **Effort:** ~30 min
- **Risk:** low

### Option 2: Remove the Stop hook

- Drop the `Stop` block from `.claude/settings.json` entirely if deferred items
  are always filed as todos immediately and a `/tmp` reminder adds no value.

## Recommended Action

1. Decide between Option 1 (wire it up) and Option 2 (remove the hook).
2. If Option 1: add an "append to `/tmp/plant-id-deferred.txt`" step to the
   `audit` skill Phase 4 and the `codify` skill Step 5, for deferrals not
   immediately turned into a `todos/` file.
3. If Option 2: delete the `Stop` block from `.claude/settings.json`.

## Technical Details

- `.claude/settings.json` — `Stop` hook block
- `.claude/skills/audit/SKILL.md` — Phase 4 (Defer)
- `.claude/skills/codify/SKILL.md` — Step 5

## Acceptance Criteria

- [ ] Either the deferred file is written by a real code path, or the Stop hook
      is removed.
- [ ] `.claude/settings.json` remains valid JSON.

## Work Log

### 2026-05-17 - Created

- Filed during the OCRecipes harness port (commit `da3e6da`); the Stop hook was
  ported but its writer was not.

### 2026-05-18 - Attempted by completing-todos skill (run 2026-05-18-2300) — SKIPPED (blocked)

- Picked up by the automated sweep; **blocked by the harness self-modification guard**.
- Both proposed solutions edit `.claude/` harness files, which the auto-mode
  classifier hard-blocks when the agent itself attempts the edit:
  - Option 1 → `.claude/skills/audit/SKILL.md` + `.claude/skills/codify/SKILL.md`.
  - Option 2 → `.claude/settings.json` (delete the `Stop` block).
- Attempted Option 2 (the recommended one — removing dead plumbing is lower-risk
  than wiring two skills to write `/tmp`): editing `.claude/settings.json` was
  denied as Self-Modification.
- Recommended resolution (for a human to apply): **Option 2** — delete the
  `"Stop"` block from `.claude/settings.json` (the `,` after the PreToolUse `]`
  through the `"Stop": [ ... ]` array). The Stop hook only greps
  `/tmp/plant-id-deferred.txt`, which no code path writes; the harness works
  fully without it (see Notes). After deletion the file is still valid JSON —
  verify with `python3 -m json.tool .claude/settings.json`.

## Notes

p4 — opt-in convenience plumbing, no functional regression. The harness works
fully without it; this just decides whether to finish or drop the feature.
