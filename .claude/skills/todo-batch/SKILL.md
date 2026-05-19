---
name: todo-batch
description: Filter pending todos by priority, tags, or IDs and sweep through the matching subset. Use when the user says "/todo-batch", "batch todos", "sweep p3 todos", or "do all blog todos".
---

# Todo Batch — Filtered Sweep

Like `todo-sweep`, but restricted to a user-defined subset. Useful for focused sprints (e.g., "all P3 blog issues" or "todos 074–076").

## Steps

1. **Parse filter criteria from invocation**

   Extract flags from the user's message:

   - `--priority pX` — restrict to one priority level
   - `--ids A,B,C` — specific issue IDs
   - `--tag tagname` — match todos whose `tags:` frontmatter contains the tag
   - `--exclude-ids A,B` — skip specific IDs even if they match other criteria
   - `--dry-run` — plan only, touch nothing

   Natural language examples and their normalized forms:
   - "batch all p3 blog todos" → `--priority p3 --tag blog`
   - "do todos 074, 075, 076" → `--ids 074,075,076`
   - "sweep remaining p2 issues" → `--priority p2`

2. **Pre-flight — Working directory check**

   ```bash
   git status --short
   ```

   - Dirty? Offer: `stash / cancel / continue-anyway`
   - On `stash`: `git stash push -m "todo-batch pre-flight"`

3. **Discover candidates**

   ```bash
   grep -l "^status: pending" todos/*.md | grep -v -E '/(TEMPLATE|README|GITHUB|IMPLEMENTATION|QUICK_REFERENCE|RESEARCH)\.md$'
   ```

4. **Apply filters**

   For each candidate, parse frontmatter and test:

   - `--priority pX`: `priority` must equal `pX`
   - `--ids A,B,C`: `issue_id` must be in the list
   - `--tag foo`: `tags` array must contain `foo` (case-insensitive)
   - `--exclude-ids`: drop if `issue_id` matches
   - After filtering, **dependency-prune**: drop any todo whose `dependencies` include an id not in the filtered set AND not in `archive/`. (Dependencies outside the batch but already completed are fine.)

5. **Sort**: priority ascending, then topological sort within priority.

6. **Present filtered plan**

   ```text
   Todo Batch Plan
   ===============
   Filter: <human-readable description of parsed criteria>
   Matching todos: <N>
   <list with id, priority, title, effort if known>

   Skipped by filter: <ids that matched criteria but were dependency-pruned>
   Proceed? (yes / dry-run / edit-filter / cancel)
   ```

   - On `edit-filter`: return to step 1 with refined criteria.
   - On `dry-run`: print what `completing-todos` would do for each todo, then stop.
   - On `cancel`: exit.

7. **Invoke `completing-todos` skill** with the equivalent filter flags.

   Examples:
   - `--priority p3` and `--tag blog` → pass both to the skill
   - `--ids 074,075` → pass `--ids 074,075`

   Announce: "I'm using the completing-todos skill to batch-process `<N>` filtered todos."

8. **Post-flight — Sprint summary**

   After Phase 2 wrap-up:

   ```bash
   git diff --stat HEAD
   ```

   Summarize:

   ```text
   Batch complete.
     Filter applied: <criteria>
     Completed: <list>
     Skipped:   <list>
     Dependency-pruned: <list>

   Suggested commit message:
     "<tag>-sprint: resolve <N> <priority> issues" (customize to filter)
   ```

## Filter Examples

| What you say | Parsed flags | Result |
|---|---|---|
| "batch p3 blog" | `--priority p3 --tag blog` | 074, 075, 076 (if all match) |
| "do 074 and 076" | `--ids 074,076` | Just those two, in order |
| "sweep all p2" | `--priority p2` | Every pending P2 |
| "batch todos tagged security" | `--tag security` | Any priority, security tag |
| "batch p4 except 077" | `--priority p4 --exclude-ids 077` | All P4 minus one |

## Safety Notes

- Dependency-pruning is **automatic**; a todo blocked by an uncompleted dependency outside the batch will be silently excluded. This prevents mid-batch blockages.
- If the filtered set is empty after dependency-pruning, abort with: "No actionable todos match the filter. Adjust criteria or complete dependencies first."
- Never auto-commit.
