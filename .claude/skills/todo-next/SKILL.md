---
name: todo-next
description: Pick and complete the single highest-priority pending todo. Daily-driver workflow. Use when the user says "/todo-next", "do next todo", or "pick up next task".
---

# Todo Next — Daily Driver

Complete exactly one pending todo: the highest-priority, dependency-resolved item.

## Steps

1. **Pre-flight — Check working directory state**

   ```bash
   git status --short
   ```

   - If output is non-empty, warn the user: `Working directory is dirty. Continue? (yes / stash / cancel)`
   - On `stash`: run `git stash push -m "todo-next pre-flight"` and continue.
   - On `cancel`: exit immediately.

2. **Discover pending todos**

   ```bash
   grep -l "^status: pending" todos/*.md | grep -v -E '/(TEMPLATE|README|GITHUB|IMPLEMENTATION|QUICK_REFERENCE|RESEARCH)\.md$' | sort
   ```

3. **Parse frontmatter** of each candidate: read `priority`, `issue_id`, `dependencies`, and title (first `#` line).

4. **Sort**: p1 → p2 → p3 → p4. Within each priority, dependency-respecting topological sort. Skip any todo whose `dependencies` list contains an id that is not in `archive/` (i.e., not completed).

5. **Pick the first item** as the next todo.

6. **Present to user for confirmation:**

   ```text
   Next todo: <issue_id> [<priority>] <title>
   Estimated effort: <from todo file if available>
   Files likely touched: <from Technical Details section>
   Proceed? (yes / skip / cancel)
   ```

   - On `skip`: remove this id from consideration, return to step 5 with the next item.
   - On `cancel`: exit immediately.

7. **Invoke the `completing-todos` skill** with `--ids <issue_id>`.

   Announce: "I'm using the completing-todos skill to work through todo <issue_id>."

8. **Post-flight — Git hygiene reminder**

   After the skill exits (Phase 2 wrap-up):

   ```bash
   git status --short
   git diff --stat HEAD
   ```

   Suggest to the user:

   ```text
   Todo <issue_id> complete. Review the diff above.
   Suggested commit: git commit -m "<issue_id>: <title>"
   ```

   If a stash was created in step 1, remind: `Stash found: run git stash pop when ready.`

## Safety Notes

- Never auto-commit. The workflow only suggests commit messages.
- If `completing-todos` marks the todo `skipped` (verification failed), the workflow ends cleanly; do not auto-pick another.
- If the user cancels at any confirmation prompt, leave all files untouched.
