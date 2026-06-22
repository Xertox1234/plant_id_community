# React + TypeScript Patterns

**Stack**: React 19, TypeScript (`strict: false` during migration), Tailwind CSS 4, Vite 8
**Dev server**: port 5174 (NOT 5173) — CORS configured for 5174

---

## Critical: React Router v7 Imports

Always import router hooks from `'react-router-dom'`, never `'react-router'`.

```typescript
// ✅ CORRECT
import { useNavigate, useParams, useLocation } from 'react-router-dom';

// ❌ WRONG — causes runtime crash ("Cannot read properties of undefined (reading 'navigate')")
import { useNavigate, useParams } from 'react-router';
```

This was a breaking change in React Router v7 and affected 15+ files during the TypeScript migration.

---

## Memory Leaks — Timer Refs

Use `useRef` for debounce timers, not `useState`. `useState` triggers re-renders and creates stale closures.

```typescript
const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

const handleInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
  if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
  debounceTimerRef.current = setTimeout(() => {
    // search
  }, 500);
}, []); // ✅ Stable — no dependencies

useEffect(() => {
  return () => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
  };
}, []);
```

---

## Security — XSS Prevention

`dangerouslySetInnerHTML` is only allowed with prior `DOMPurify.sanitize()`:

```typescript
import DOMPurify from 'dompurify';

<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(userContent) }} />
```

Rich text from the API must never be rendered raw.

---

## CSRF Protection

All mutating requests must include the CSRF token and credentials:

```typescript
const csrfToken = document.cookie
  .split('; ')
  .find((row) => row.startsWith('csrftoken='))
  ?.split('=')[1];

await fetch(`${import.meta.env.VITE_API_URL}/api/v1/...`, {
  method: 'POST',
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken ?? '',
  },
  body: JSON.stringify(data),
});
```

---

## TypeScript — Component Props

New component props must have an explicit interface, not an inline type literal:

```typescript
// ✅ Explicit interface
interface BlogCardProps {
  post: BlogPost;
  showImage?: boolean;
}

export function BlogCard({ post, showImage = true }: BlogCardProps) {}

// ❌ Inline type — harder to reuse and document
export function BlogCard({ post, showImage = true }: { post: BlogPost; showImage?: boolean }) {}
```

Shared types live in `web/src/types/`.

---

## API URL

Never hardcode API URLs — always use the Vite environment variable:

```typescript
const apiUrl = import.meta.env.VITE_API_URL;
```

---

## Displaying Errors — Render `.message`, Not the Object

A structured error object (`{ message, code, ... }`) rendered as a string becomes
the literal `[object Object]` — `String({ message: 'x' })` calls
`Object.prototype.toString`, it does not reach into the object.

A defensive-looking sanitizer can mask the bug without fixing it. Helpers that
return non-strings **unchanged** are a no-op on objects:

```typescript
// utils/sanitize.ts — returns NON-strings unchanged (a no-op on objects)
export function sanitizeError(error: unknown): unknown {
  if (!error || typeof error !== 'string') return error; // ← an object passes straight through
  return stripHtml(error);
}

// ❌ result.error is an AuthError object → renders "[object Object]" to the user
setServerError(String(sanitizeError(result.error)));

// ✅ extract the string field FIRST, then sanitize
setServerError(String(sanitizeError(result.error?.message ?? 'Something went wrong.')));
```

Rule of thumb: pass the **string** you intend to display into a `sanitize*`/transform
helper, never a structured object. This bit both `LoginPage` and `SignupPage`: the
auth `error.message` was already a clean, readable string (the service layer even
flattens DRF field errors into it); only the render call was wrong.
