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

## Gotcha: debounce timers

Use `useRef` — not `useState` — for debounce/interval timer IDs. `useState` triggers a re-render on every update, causes the callback to be recreated, and leaks the timer on unmount:

```typescript
const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

const handleInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
  if (timerRef.current) clearTimeout(timerRef.current);
  timerRef.current = setTimeout(() => { /* search */ }, 500);
}, []);  // stable — no dependencies

useEffect(() => () => {
  if (timerRef.current) clearTimeout(timerRef.current);
}, []);
```
