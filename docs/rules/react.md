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
- **Tailwind v4 `space-y-*` is margin-BOTTOM on `:not(:last-child)`, not v3's
  margin-top on `:not(:first-child)`** — the emitted rule is
  `:where(.space-y-6 > :not(:last-child)) { margin-block-end }`. So adding an
  always-mounted child at the END of a spaced container silently gives the
  element BEFORE it a trailing margin it never had (the previous last child
  stops matching `:last-child`). `sr-only` does not save you: it is absolutely
  positioned, so the new child costs no layout itself, but the sibling-margin
  selector still matches it. Reasoning from the v3 model gives the wrong answer
  and looks right. Either hoist the new node out of the spaced container, or
  wrap it with its neighbour so the container's direct-child list is unchanged.
  Verify by compiling (`npx @tailwindcss/cli`) and reading the rule, not from
  memory. Hit in todo 278 (DiseaseDiagnosePage); see `docs/LEARNINGS.md`.
- **A live region is only "persistent" if no ANCESTOR is conditionally
  rendered.** Migrating `{err && <p role="alert">}` to an always-mounted
  `aria-live` node achieves nothing when the node sits inside
  `{(a || b) && (…)}` — it is recreated with its content, which is the exact
  anti-pattern being removed. Trace every conditional ancestor up to a stable
  parent, and pair the migration with a test that asserts the region is present
  and EMPTY before the triggering action: `findByText` after the fact passes
  either way. In todo 278 the two migrated sites that shipped without such a
  test were the two that were wrong.
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
- **Read the installed TipTap source before trusting hosted docs or writing a
  custom `renderHTML`/`renderText` override.** Context7's `/ueberdosis/tiptap-docs`
  can describe a newer API than what's pinned (`SuggestionProps.mount()` doesn't
  exist in the installed `@tiptap/suggestion@3.22.5` — only `tsc --noEmit` caught
  it). A vendor node's own default `renderHTML`/`renderText` frequently already
  does what you're about to reimplement (e.g. `@tiptap/extension-mention`'s
  default already prepends the suggestion char AND `mergeAttributes()`s
  configured `HTMLAttributes` correctly) — check
  `node_modules/@tiptap/<pkg>/dist/index.js` directly before adding an override;
  a hand-written one can silently drop configured attrs (hardcoding `{}` instead
  of merging).
- **Never `Array(n).fill(makeThing())` for fixtures** — `.fill()` evaluates its
  argument ONCE, so all n slots share one object (duplicate React keys, cross-item
  mutation, warning noise that buries real warnings). Use
  `Array.from({ length: n }, (_, i) => makeThing({ id: i }))`.
- **Never nest an interactive `<Link>`/`<a>` inside a card-level `<Link>`** — a
  nested `<a>` is invalid HTML (the browser auto-closes the outer anchor) and
  `getByRole('link')` breaks with "found multiple". Add per-element links only where
  the container isn't itself a link. See `web/docs/patterns/react-typescript.md`.
- **React Router route matching is score-based, not declaration-order** — a static
  segment outranks a dynamic one, so `/forum/users/:x` can shadow `/forum/:a/:b`
  regardless of `<Route>` order; reordering does NOT fix it (use a distinct prefix
  or keep URLs structurally distinct).
- **Never `insertContent(htmlString)` with text you did not author** — TipTap parses
  a string argument as HTML, so model/API output becomes real document structure in
  whatever the user then publishes. Build nodes instead:
  `insertContent([{type:'paragraph', content:[{type:'text', text: line}]}])`, which
  can only ever produce characters (verified against the installed `@tiptap/core`:
  the array branch goes through `schema.nodeFromJSON`, never `DOMParser`).
- **Session-lifetime API state ("this account can never do X") goes in the service
  module, not `useState`** — a composer remounted via `key=` after every post loses
  component state and re-offers the failing action. Seed state from the service
  getter, write it from the caller's error branch (not inside the request function,
  which a stubbing test never runs), and reset it in `beforeEach`. Prefer leaving the
  control **mounted and disabled** over unmounting it: unmounting what the user just
  activated drops keyboard focus to `<body>`. See `web/docs/patterns/testing.md`.
- **Branch on the HTTP STATUS, never on the error message text, whenever the
  KIND of failure is product behaviour.** The backend serialises a DRF
  exception as `str(exc)` (`apps/core/exceptions.py`), so a 403 arrives as
  DRF's default detail — *"You do not have permission to perform this
  action."* — carrying neither `403` nor the word "forbidden". A
  `/403|forbidden/i.test(err.message)` branch therefore never fires in
  production while passing any test that mocks a hand-written message. Throw a
  status-carrying error (`ForumApiError extends Error` in `forumService.ts`;
  extending Error keeps `.message` and every `instanceof Error` caller intact)
  and check `err.status`. Mock rejections with the REAL message the backend
  sends — todo 282 shipped past a green test that mocked
  `Error('HTTP 403 Forbidden')`, a string that endpoint never produces.
- **Never do cleanup work inside a `setState` updater in an unmount effect.**
  React DISCARDS a `setState` on an unmounting component *without invoking the
  updater*, so `return () => setThing((cur) => { release(cur); return null; })`
  silently does nothing — measured 0 calls in todo 281's object-URL revoke.
  It reads as correct, and a test of any OTHER exit path (a button, Escape)
  passes while the unmount path leaks. Mirror the value into a `useRef` and read
  the ref in the cleanup; a ref is a plain object and survives unmount. Test the
  unmount path *specifically* (`const { unmount } = render(...)`), because the
  happy-path test cannot fail on this.
- **`URL.createObjectURL` needs a matching `revokeObjectURL` on EVERY exit
  path** — confirm, cancel, keyboard dismiss, and unmount. Route them all
  through one `close()` helper rather than revoking at each call site; jsdom
  implements neither method, so stub both in tests and spy the revoke (the leak
  is otherwise invisible).
- **New chrome/component CSS uses `--gt-*` semantic tokens, never raw
  `--canopy-*` ramp vars in property positions.** The raw ramp is mode-blind:
  a sage flash ring authored against dark mode measured ~1.4:1 in light mode
  (invisible) and shipped to final review before anyone saw both sides
  (PR #537). Raw ramp vars belong only on the right-hand side of the
  `:root`/`[data-mode]` token-definition blocks.
- **A static state-styling rule that must beat a Tailwind utility goes
  UNLAYERED.** `@layer components` always loses to the utilities layer
  regardless of specificity — this has now bitten twice (PR #536 empty-rail
  hide rule vs `xl:flex`; PR #537 reduced-motion flash ring vs the accepted
  answer's `ring-*` box-shadow). Put the rule outside any `@layer` with a
  comment saying why, mirroring the existing `.app-rail:not(:has(*))` rule.
