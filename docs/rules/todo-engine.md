# Todo engine — binding rules

Compact checklist auto-injected before edits to the todo sweep engine (`scripts/todos/`, the
`todo-*` agents, workflows and skills, `completing-todos`). Long-form:
`docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md` and `docs/LEARNINGS.md`.

- **A gate that marks a todo `verified` must check everything Land's `flip-acs` will check:** the
  worker's `pass`, the verifier's agreement, and an evidence file. A todo that passes the earlier gate
  and fails Land blocks there, and the only way out is a fresh re-execute (todo 658).
- **Put a check that should cost a retry in the verifier (`MODE: execute`), not only in
  `ingest-execute`.** Only a verifier `fail` reaches the in-place retry worker (same worktree, re-run
  only the affected criterion). A failure at ingest goes `failed → ready` and gets a fresh worktree.
- **Treat an `ac.json` entry's `pass: false` as a failure only when the entry has a `command`.**
  Re-pointed, owner-confirmed and external entries carry `pass: false` with an empty command by design.
- **Scope every new verifier or worker spec rule to the `MODE:` it protects.** Verifier step 3 runs in
  `MODE: execute` and `MODE: repair`. By repair time Land has already flipped the boxes, so an
  execute-only rule applied there blocks a repair with no gate behind it.
