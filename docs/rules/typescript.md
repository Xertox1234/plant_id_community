# TypeScript (web) — binding rules

Compact checklist auto-injected before edits. Long-form:
`web/docs/patterns/react-typescript.md`.

- **Strict mode holds** — no `any`. Use `unknown` + a type guard, or a precise type.
- **`.ts`/`.tsx` only** — no plain `.js`/`.jsx` source files.
- **Type API responses** at the fetch boundary; do not pass `any` inward.
- Prefer discriminated unions over optional-field soup for variant data.
- Narrow with type guards, not casts (`as`). Casts hide real shape mismatches.
- Keep shared types in one module; don't redeclare the same shape per file.
