# React (web) — binding rules

Compact checklist auto-injected before edits. Long-form:
`web/docs/patterns/react-typescript.md`, `.../tailwind.md`.

- **Import router hooks from `react-router-dom`, never `react-router`.**
  `import { useNavigate } from 'react-router'` is a silent runtime failure
  (`Cannot read properties of undefined`).
- **Debounce/timer IDs go in `useRef`, not `useState`.** `useState` re-renders on
  every update, recreates the callback, and leaks the timer on unmount.
- **Sanitize HTML with DOMPurify** before any `dangerouslySetInnerHTML`.
- **Send CSRF headers** on state-changing requests (`X-CSRFToken`).
- Clean up effects — abort fetches, clear timers, remove listeners on unmount.
- Tailwind CSS 4 conventions; no hardcoded hex colors where a token exists.
- **Render `error.message`, not the error object.** `String({message,code})` is the
  literal `[object Object]`; a `sanitize*` helper that returns non-strings unchanged
  won't save you — pass the string field in.
- **Non-component exports go in their own module.** A `.tsx` file that exports a
  React component must export ONLY components — exporting a constant, a TipTap
  node/extension, or a helper from it fails `react-refresh/only-export-components`
  (eslint error, blocks the commit). Put the shared value in a sibling `.ts` module
  (e.g. `forumImageNode.ts`) and import it.
- **Pin `@tiptap/extension-*` to the EXACT `@tiptap/core` version.** A caret
  (`^3.22.5`) resolves to the newest 3.x (e.g. 3.27), whose `peer @tiptap/core` no
  longer matches the pinned core → `npm install` ERESOLVE. Install the exact
  matching version (`@tiptap/extension-image@3.22.5`); `npm ci` then honors the lock.
- **Never `Array(n).fill(makeThing())` for fixtures** — `.fill()` evaluates its
  argument ONCE, so all n slots share one object (duplicate React keys, cross-item
  mutation, warning noise that buries real warnings). Use
  `Array.from({ length: n }, (_, i) => makeThing({ id: i }))`.
