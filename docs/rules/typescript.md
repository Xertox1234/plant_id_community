# TypeScript (web) — binding rules

Compact checklist auto-injected before edits. Long-form:
`web/docs/patterns/react-typescript.md`.

- **Strict mode holds** — no `any`. Use `unknown` + a type guard, or a precise type.
- **`.ts`/`.tsx` only** — no plain `.js`/`.jsx` source files.
- **Type API responses** at the fetch boundary; do not pass `any` inward.
- Prefer discriminated unions over optional-field soup for variant data.
- Narrow with type guards, not casts (`as`). Casts hide real shape mismatches.
- Keep shared types in one module; don't redeclare the same shape per file.
- **A new custom request header needs a matching `CORS_ALLOW_HEADERS` entry**
  (`backend/plant_community_backend/settings.py`) before any browser can send
  it. `CORS_ALLOW_HEADERS` is an allowlist, and a missing entry fails silently:
  the preflight still returns 200, the response just omits the header, and the
  browser then never sends the real request — no 4xx, no server log, and the
  refusal is cached for `CORS_PREFLIGHT_MAX_AGE` (24h). jsdom does not enforce
  CORS, so unit tests cannot see it; add the header to `BROWSER_SENT_HEADERS` in
  `apps/forum_host/tests/test_cors_preflight.py` (todo 357, `Idempotency-Key`).
