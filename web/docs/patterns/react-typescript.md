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

---

## TipTap: Verify Installed Source Before Trusting Docs or Writing an Override

A pinned TipTap version (see `docs/rules/react.md`'s exact-version-pin rule) can
lag behind what Context7's hosted docs describe, and a vendor extension's own
default `renderHTML`/`renderText` frequently already does what a custom override
is about to reimplement — check `node_modules/@tiptap/<pkg>/dist/index.js`
directly before writing one (todo 253 slice 4 review).

**Docs-vs-installed mismatch** (`@tiptap/suggestion@3.22.5`): the hosted
`SuggestionProps` docs describe a `props.mount(el)` auto-positioning helper.
The installed version's actual type only has `clientRect`:

```typescript
// ❌ Compiles against the docs, fails tsc --noEmit against what's installed
onStart: (props: SuggestionProps) => {
  props.mount(dropdown); // Property 'mount' does not exist on type 'SuggestionProps<...>'
},

// ✅ What 3.22.5 actually supports — position manually from clientRect()
onStart: (props: SuggestionProps) => {
  const rect = props.clientRect?.();
  if (rect) {
    dropdown.style.position = 'fixed';
    dropdown.style.top = `${rect.bottom + 4}px`;
    dropdown.style.left = `${rect.left}px`;
  }
},
```

**Reimplementing an already-correct default** (`@tiptap/extension-mention`):
the vendor's own default `renderHTML`/`renderText` already prepend the
suggestion char and correctly `mergeAttributes()` the configured
`HTMLAttributes` — read directly from
`node_modules/@tiptap/extension-mention/dist/index.js`:

```javascript
// The vendor default (already correct, don't reimplement this):
renderHTML({ options, node, suggestion }) {
  return [
    'span',
    mergeAttributes(this.HTMLAttributes, options.HTMLAttributes),
    `${suggestion?.char ?? '@'}${node.attrs.label ?? node.attrs.id}`,
  ];
}
```

A custom override that skips `mergeAttributes()` silently drops the
configured styling while LOOKING correct (the "@" prefix still renders,
since that part's easy to get right by hand — the attribute merge is the
part that's easy to get wrong):

```typescript
// ❌ Hardcodes {} for attrs — the configured `class` never reaches the DOM
renderHTML({ options, node }) {
  return ['span', {}, `${options.suggestion.char}${node.attrs.label ?? node.attrs.id}`];
},
```

If the vendor default already does what you need, delete the override
entirely rather than patching it — don't maintain a parallel reimplementation
of code the library ships.

---

## Debounce + Stale-Response Guard Outside a Component

`docs/rules/react.md`'s `useRef`-for-timers rule covers debounce **inside** a
React component (an effect can clean up the ref on unmount). A plain TS module
— e.g. a TipTap `suggestion.items` callback, not a component — has no
lifecycle to hook a cleanup into, and a debounce timer alone doesn't protect
against **out-of-order network responses**: once two debounced calls both
survive their wait and reach the network, response order isn't guaranteed by
request order. A slow-but-earlier response arriving after a fast-but-later one
can overwrite fresher results with stale ones (todo 253 slice 4 review — this
is exactly how a TipTap mention-autocomplete dropdown could resurrect itself
after the user already dismissed it).

A single shared token, bumped on every new call and checked after the network
response resolves, covers both the debounce-cancellation case (the token check
is almost always moot there — clearing the pending timer already stops the
superseded call from ever reaching the network) and the genuine race (both
calls survive debounce, the token catches whichever one is stale once they
both resolve):

```typescript
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
let requestToken = 0;

export async function search(query: string): Promise<Result[]> {
  if (!query) return [];
  const myToken = ++requestToken;
  if (debounceTimer) clearTimeout(debounceTimer);
  await new Promise<void>((resolve) => {
    debounceTimer = setTimeout(resolve, 300); // matches SearchPage.tsx's window
  });
  try {
    const results = await api.search(query);
    if (myToken !== requestToken) return []; // a newer call has since started
    return results;
  } catch {
    return [];
  }
}
```

The superseded call's `await new Promise(...)` (cancelled via `clearTimeout`)
never resumes — that's fine; nothing calls its `resolve`, so it just never
completes rather than resolving with stale data. Test the race directly by
mocking the network call with two manually-resolvable promises and resolving
them out of order — a debounce-only test (single call, fake-timers advance)
doesn't exercise this path at all.

## One-Shot Side Effects in a List-Dependent Effect

An effect that lists a **growing collection** in its deps (`posts`, `messages`,
`rows`) re-runs on every append. That's correct when the effect's job *is* to
react to the new items — but any **one-shot side effect** in the same effect
(scroll-into-view, autofocus, a fire-once analytics ping) then fires again on
every append, not just the first time. In the forum thread deep-link, the
arrival effect had `posts` in its deps so it could pull later cursor pages until
the `#post-N` target mounted — but the same effect also called
`el.scrollIntoView()`, so posting a reply or clicking "Load More" (with the hash
still in the URL) yanked the viewport back to the anchor on every list change.

Gate the one-shot part on a `useRef` keyed by the effect's *trigger identity*
(here, the hash), and reset it when a fresh trigger arrives:

```typescript
const scrolledHashRef = useRef<string | null>(null);
// reset on navigation (new thread): scrolledHashRef.current = null;

useEffect(() => {
  const el = document.getElementById(targetId);
  if (!el) { /* keep loading pages… */ return; }
  if (scrolledHashRef.current === location.hash) return; // already scrolled to this anchor
  scrolledHashRef.current = location.hash;
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}, [loading, posts, location.hash /* …loaders… */]);
```

Same shape guards the auto-loader itself: advance **once per cursor** via a
`chaseCursorRef` so a failed page-fetch (which leaves `nextCursor` unchanged)
can't retry forever. And any request fired automatically from such an effect
needs a **stale-thread guard** — capture the id before the `await` and skip the
`setState` if `currentIdRef.current` moved on, or a late page for thread A
appends to thread B (see `ThreadDetailPage.tsx`).

## React 19 Native Document Metadata (per-route SEO)

React 19 hoists `<title>`, `<meta>`, and `<link>` rendered **anywhere** in the
tree to `<head>` automatically — no `react-helmet`. Use it for per-route
title/description/OG on an SPA (todo 256 H9): a small `PageMeta` component
(`web/src/components/PageMeta.tsx`) renders the tags inline; each page passes
data-derived values.

```tsx
export default function PageMeta({ title, description, og }: PageMetaProps) {
  return (
    <>
      <title>{title}</title>
      {description && <meta name="description" content={description} />}
      {og && <meta property="og:title" content={og.title} />}
    </>
  );
}
// In a page: <PageMeta title={`${thread.title} · PlantID`} og={{ ... }} />
```

- **Testable in jsdom/Vitest**: after render, assert `document.title` and
  `document.querySelector('meta[property="og:type"]')` — the hoist runs on commit.
- **Placement tradeoff**: rendering `PageMeta` in a page's main (post-load) return
  means the title isn't set during the loading flash. Fine for data-derived titles
  (a crawler waits for network idle); for a *static* title, render it before the
  loading/error early returns if the flash matters.
- **Crawler reach**: only JS-executing crawlers (Googlebot) see these — non-JS
  link unfurlers (Slack/Twitter/FB) do not run the SPA. Pair with a
  server-rendered sitemap/RSS for discovery; accept no rich unfurl without a
  prerender.
- **OG url**: build from `window.location.origin + window.location.pathname`
  (drops query/hash) — the SPA is client-only, so no SSR guard is needed.

## Router: No Nested Anchors, and Route Matching Is Score-Based (todo 257 slice B)

Two React-Router gotchas hit while adding forum author-profile links + a route.

**1. Never nest an interactive `<Link>` inside a card-level `<Link>`.** `ThreadCard`
wraps the *entire card* in `<Link to={threadUrl} className="block">`. Adding an
author `<Link>` inside it produced **nested `<a>` tags — invalid HTML**; the browser
auto-closes the outer anchor at the inner one, and a `getByRole('link')` test fails
with "Found multiple elements with the role link". Put per-element links only where
the container is *not* itself a link: `PostCard` and the thread-header author name
are fine (their containers are plain `<div>`s); a card-list item whose whole card
already navigates is not — leave its inner text plain.

**2. React Router v6/v7 route matching is SCORE-BASED, not declaration-order.** A
static path segment outranks a dynamic one (`users` beats `:categorySlug`), so
`/forum/users/:username` always outscores `/forum/:categorySlug/:threadSlug` for a
3-segment URL — **reordering the `<Route>`s does NOT change this.** A bare
`/forum/users/:x` route can therefore permanently shadow a sibling
two-dynamic-segment route. Mitigations, in order:

- Keep colliding URLs structurally distinct. Here the collision is only theoretical
  because board/thread URLs are always ID-prefixed (`categoryPath` →
  `/forum/{id}-{slug}/...`), so no real thread URL is ever `/forum/users/<x>`.
  Document that invariant at the route.
- If a genuine literal collision is possible, use a distinct prefix
  (`/forum/u/:username`) or reserve the slug — not route reordering.

## Screen-reader announcements: persistent live region, not conditional mount

A `role="alert"`/`aria-live` element that is **conditionally mounted with its
content** (`{error && <p role="alert">{error}</p>}`) is generally NOT announced —
MDN documents that a live region must already exist in the DOM before its text
changes for assistive tech to read it (audit 2026-07-11 M26). The fix is a
persistent container whose text content swaps.

Two shapes, both used in the forum:

- **App-wide announcer** (`contexts/AnnouncerContext.tsx`): one polite + one
  assertive `aria-live` region mounted once at the app root; `useAnnounce()`
  swaps their text. Use for transient messages with no visible counterpart
  (e.g. "Reply posted." after a successful post).
- **Persistent visible banner**: keep the banner element always mounted and swap
  its text; collapse it with `sr-only` (not unmount) when empty:

```tsx
<div aria-live="polite" aria-atomic="true"
     className={notice ? 'visible-styles' : 'sr-only'}>
  {notice}
</div>
```

Use **bare `aria-live`**, not `role="status"`/`role="alert"`, on these regions:
`role="status"` collides with the many `LoadingSpinner`s across the app in
`getByRole('status')` test queries. The `aria-live` attribute is the actual
announcement mechanism; the roles are just conveniences that imply it. Test a
content-swap announcement by asserting the SAME region node's `textContent`
changes (not that a new node mounted) — that is what proves the live-region
contract, and it's the non-tautological version of an announce test.

## Skeleton loading states: one status root, hidden blocks (PR #623)

`web/src/components/forum/ForumSkeleton.tsx` is the reference. The contract
that keeps the page tests (`getByRole('status')`) and screen readers happy:

- **One `role="status" aria-live="polite"` root per page composition**, with
  `aria-label` (the `status` role is name-from-author; the sr-only copy is
  what the live region announces). Shape subcomponents (`ThreadCardSkeleton`,
  `PostCardSkeleton`) never self-wrap — a second root makes `getByRole` throw.
- **Decorative blocks live under a child `aria-hidden="true"` container** —
  never put `aria-hidden` on the root, or testing-library's role query skips
  it and the "shows a status while loading" assertions fail.
- **Chrome comes from the real primitive** (`<Card>`), so border, gradient,
  radius and density padding are pixel-identical to the loaded card and only
  the content bars pulse. Pulse per block (`motion-safe:animate-pulse`), not on
  the wrapper — a wrapper pulse fades the card chrome too.
- **Mirror only unconditional structure**: no auth-gated buttons, reaction
  bars, tag chips, rail modules, or headings (the forum-index e2e overflow
  check waits for the loaded `h1`; the board/thread checks sample mid-fetch).
- **Fluid widths only** (fractions, `w-full`, `flex-1`, `w-full max-w-*`);
  fixed widths stay small and inside `flex-wrap` rows, so 375px never
  overflows.

```tsx
export function SkeletonStatus({ children, label = 'Loading…' }) {
  return (
    <div role="status" aria-live="polite" aria-label={label}>
      <span className="sr-only">{label}</span>
      <div aria-hidden="true">{children}</div>
    </div>
  );
}

const RADIUS = { xs: 'rounded-xs', sm: 'rounded-sm', md: 'rounded-md', pill: 'rounded-pill' } as const;
export function SkeletonBlock({ className = '', rounded = 'xs' }) {
  // radius is a prop, not part of className — two rounded-* utilities on one
  // element are resolved by stylesheet order, not class order
  return <div className={`bg-surface-3 motion-safe:animate-pulse ${RADIUS[rounded]} ${className}`} />;
}
```

To eyeball a skeleton without racing the network, delay the API from a
throwaway Playwright script rather than throttling devtools:

```js
await page.route((u) => u.includes('/api/') && /forum|topic/.test(u), (r) => setTimeout(() => r.continue(), 30000));
await page.goto('/forum', { waitUntil: 'commit' }); await page.waitForTimeout(900);
```

## Chat-style thread over newest-first cursor pages (todo 339)

`ConversationPage` reads `GET conversations/<id>/messages/`, which pages
newest-first so a thread opens on its latest messages. The page keeps a
single oldest→newest array: the first page is reversed on arrival, "Load
older" fetches `next` and prepends that page reversed, a successful send
appends the returned message, and every merge dedupes by `id` so the echo of
a send cannot reappear when a later page contains it. Guard every async
result on the username the request was issued for (a late response for the
previous thread must not render into the current one), keep the draft on a
failed send, and surface a 403 in a persistent `aria-live` region (a
conditionally rendered live region announces nothing). The resolve step —
`GET conversations/with/<username>/` → 404 means "no thread yet", not an
error — renders the empty state with a live composer and re-resolves after
the first send.

## Referencing blocks in the forum composer (post quotes, todo 342)

A `post_quote` block references another post: `{post, text}` on write,
`{text, post_id, available, topic_id, author, is_blocked, is_muted}` on read.

- **Round-trip by attribute, not by re-declaring the node.** A TipTap
  `Extension.create({ addGlobalAttributes })` on `blockquote` maps
  `postId ↔ data-post-id`; `parseHTML` returns `null` when the attribute is
  absent so a legacy `<blockquote>` never comes back as `data-post-id=""`.
  `htmlToBodyBlocks` turns a top-level blockquote with the attribute into
  `post_quote`, stripping nested markup to plain text (`<br>` ↔ `"\n"`);
  `bodyBlocksToHtml` writes it back escaped, keeping the attribute even when
  `available` is false — the server exempts quotes the stored body already
  carries from re-validation on edit, so the client never downgrades one.
- **Insertion is a remount.** TipTap `content` is init-only, so the Quote
  action writes the draft store, sets the body and bumps the composer key
  with `autoFocus`, then scrolls the form into view and announces. Vary the
  announcement per quote (author name / post number): the announcer relies
  on consecutive messages differing, so an identical string is silent.
- **Render the excerpt as text, collapse on the viewer's signals.** The
  quote's `text` is the quoter's excerpt (plain text by contract) rendered
  as React text, never `SafeHTML`. A nested attribution is one more surface
  rendering an author: read `is_blocked` / `is_muted` and collapse with the
  same placeholder + "Show anyway" reveal `PostCard` uses — never hide.
  `available: false` keeps the text with no attribution.
