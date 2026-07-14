# DISCIPLINE — applies before any edit

- Think before coding. State your assumptions out loud. If the request is ambiguous, ask. If a simpler approach exists, push back. Stop when you are confused, name what is unclear, do not just pick one interpretation and run.
- Simplicity first. Write the minimum code that solves the problem. No speculative abstractions. No flexibility nobody asked for. The test: would a senior engineer call this overcomplicated.
- Surgical changes. Touch only what the task requires. Do not improve neighboring code. Do not refactor what is not broken. Every changed line should trace back to the request.
- Goal-driven execution. Turn vague instructions into verifiable targets before writing a line. "Add validation" becomes "write tests for invalid inputs, then make them pass."
- Add a new import in the SAME edit as its first usage, not a prior one. The
  formatter runs between edits and strips an import that's unused at that
  moment — adding it ahead of the code that uses it gets it silently deleted,
  surfacing later as `NameError`/`undefined_identifier`.
- Before committing a `git mv` of a file you just edited, re-`git add` the
  new path. `git mv` stages the rename using the pre-edit index content, not
  your working-tree edits — a rename that should carry a real diff but shows
  `0 insertions(+), 0 deletions(-)` in `git diff --cached --stat` is the
  tell. See `docs/LEARNINGS.md` 2026-07-14 (Tooling / Agents).
