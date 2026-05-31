# Web — React 19 / TypeScript / Tailwind CSS 4

## Commands

```bash
cd web

npm run dev           # http://localhost:5174
npm run build         # production build (runs type-check first — must pass)
npm run type-check    # TypeScript compilation check (zero errors required)
npm run lint          # ESLint
npm run test          # Vitest (unit + component)
npm run test:watch    # watch mode for development
npm run test:e2e      # Playwright E2E (auto-starts dev servers)
npm run test:e2e:ui   # Playwright UI — best for debugging E2E failures
```

## Conventions

- **All source files** must be `.ts` or `.tsx`. No `.js` files in `src/`.
- **React Router** — always import from `react-router-dom`, never `react-router`. The latter causes silent runtime failure.
- **TypeScript strictness** — `strict: false` for now. Avoid `any`; use `unknown` for truly unknown types. New types go in `src/types/`.
- **User-generated HTML** — always sanitize with `DOMPurify` before rendering. Never set `dangerouslySetInnerHTML` with raw user input.
- **CSRF** — include `X-CSRFToken` header and `credentials: 'include'` on all mutating requests to the backend.

## CI

`web-ci.yml` gates every PR: TypeScript check (`tsc --noEmit`), ESLint, and Vitest unit tests (`vitest --run`). No external services required.

Coverage thresholds in `vitest.config.ts` (80% statements/lines/branches/functions) are **advisory/local-only** — they are documented there as such. CI does not run `--coverage`, so the threshold is never enforced in the pipeline. Current measured coverage is ~79–81% depending on metric; enforce once the suite is above the floor.

E2E (Playwright) is excluded from CI for now — run locally with `npm run test:e2e`.

## Gotcha: debounce timers

Use `useRef` — not `useState` — for debounce/interval timer IDs. `useState` triggers a re-render on every update, causes the callback to be recreated, and leaks the timer on unmount:

```typescript
const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

const handleInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
  if (timerRef.current) clearTimeout(timerRef.current);
  timerRef.current = setTimeout(() => {
    /* search */
  }, 500);
}, []); // stable — no dependencies

useEffect(
  () => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  },
  []
);
```
