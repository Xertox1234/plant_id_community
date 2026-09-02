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
- This repo squash-merges, which ERASES ancestry — so "is this branch's work in
  `main`?" cannot be answered by any diff or ancestry check. Each one answers a
  different question: `git diff main...branch` (three-dot) = changes since the
  merge base, non-empty for merged-and-stale AND for unmerged; `git diff main
  branch` (two-dot) = is the tree IDENTICAL to main, non-empty the moment main
  moves on; `git branch -d` refuses; `git cherry` marks `+`. The authoritative
  check is the PR record: `gh pr list --head <branch> --state all --json
  number,state,mergedAt`. Run it before any `git branch -D` or remote branch
  deletion. Two corollaries: a file-hash comparison against main under-reports,
  because append-only files (`docs/LEARNINGS.md`, `docs/rules/triggers.json`)
  always differ on an older branch; and a branch with NO PR may still be merged
  — it can be a local review copy of a differently-named PR head (`pr-538-review`
  held 24 commits absent from main, all landed via PR #538 from
  `feat/canopy-forum-content`). See `docs/LEARNINGS.md` 2026-09-02.
