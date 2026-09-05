---
status: completed
priority: p4
issue_id: "336"
tags: [web, forum, testing, playwright, tiptap]
dependencies: []
source_review: "docs/audits/2026-09-04-forum.md"
source_finding: "L5"
---

# Playwright spec for the @mention dropdown in a real mounted editor

## Problem

The @mention suggestion dropdown (`web/src/components/forum/forumMentionNode.ts`
`render()`) now has Vitest coverage that drives `onStart`/`onUpdate`/`onKeyDown`/
`onExit` directly with plugin-shaped props (audit 2026-09-04 L5). That pins the
dropdown's own DOM lifecycle but not the *triggering* contract: whether
ProseMirror's suggestion plugin actually calls those hooks at the right moment
with a live `clientRect`, and whether `onExit` fires on blur / Escape / editor
teardown in a real editor. `web/docs/patterns/testing.md` prescribes a Playwright
spec for exactly that.

## Findings

- `web/src/components/forum/forumMentionNode.test.ts` — five lifecycle tests
  (added in the audit PR) call `ForumMention.options.suggestion.render()`
  directly; no `@` keystroke reaches a mounted `EditorView`.
- `web/e2e/*.spec.*` — no spec types `@` into the composer or references
  "mention" (grep, 2026-09-04).
- `web/docs/patterns/testing.md` (TipTap section) — "to actually exercise
  onStart/onUpdate/onExit, use Playwright against a real mounted editor".
- Raised by the react-typescript-reviewer in the audit's Phase 6 review as
  MEDIUM, non-blocking; filed per the review-loop budget.

## Recommended Action

1. Add `web/e2e/forum-mention.spec.ts` under the `*-authenticated` projects only
   (it needs a logged-in composer; see the login-rate-limit note in
   `web/CLAUDE.md`).
2. Open a thread, focus the reply composer, type `@ad`, assert the dropdown
   appears with a fixture user, ArrowDown + Enter inserts `@<username>`, and
   Escape removes the dropdown (no leftover `div.z-50` in `document.body`).
3. Mock or seed the user-search endpoint so the fixture user is deterministic
   (`GET /forum/users/search/?q=` — `mention_user_search` throttle 30/m).

## Technical Details

- Dropdown class literal: `DROPDOWN_CLASS` in `forumMentionNode.ts` (starts
  `z-50 min-w-[10rem]`); positioning is manual (`clientRect`) because the
  installed `@tiptap/suggestion@3.22.5` has no `mount()` helper.
- E2E auth state per project lives in `.auth/user-<browser>.json`; refresh with
  `playwright test --project=setup-chromium` (call
  `./node_modules/.bin/playwright` directly — RTK mangles filter args).

## Acceptance Criteria

- [x] A Playwright spec types `@` in the real composer and asserts the dropdown
      mounts, navigates, commits, and is removed on Escape.
- [x] The spec runs only in the authenticated projects and passes locally.
- [x] `web/docs/patterns/testing.md`'s TipTap section points at the spec.

## Work Log

### 2026-09-04 - Filed from the forum audit's Phase 6 review

- Non-blocking reviewer finding on the L5 fix; the Vitest lifecycle tests ship
  in the audit PR, this spec is the remaining prescribed layer.

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-0408) (run 2026-09-05-0408)

- Picked up by automated workflow.

### 2026-09-05 - Completed by completing-todos skill (run 2026-09-05-0408)

- Verification: all 3 acceptance criteria evidenced (spec 2 passed on chromium-authenticated and firefox-authenticated; unauthenticated project lists 0 tests; testing.md points at the spec).
- Review: cross-cutting + react-typescript, 1 round; every finding repaired (structural mention-node assertions, in-app route-change teardown, fixed-position check, stable data-testid, honest ArrowDown claim, doc wording).

## Notes

p4: the Vitest layer catches the regressions the file's own comments warn about
(stale dropdown resurrection, teardown); this is defence in depth for the
plugin-contract half.

### 2026-09-05 - Implemented by completing-todos skill (run 2026-09-05-0408)

- `web/e2e/forum-mention.spec.js` (`.js`, like every other authenticated
  spec): real keystrokes `@e2e_test_u` in a mounted `TipTapEditor`; asserts
  the dropdown (`body > div.z-50`, `DROPDOWN_CLASS`) mounts with a
  `@e2e_test_user` button at a non-origin `clientRect`; ArrowDown + Enter
  commits `@e2e_test_user` into the doc and removes the dropdown; Escape
  removes it with the query left as plain text; navigating away
  mid-suggestion leaves no orphan.
- **Deviation, recorded:** the spec drives the NEW-THREAD composer rather
  than a reply composer. Same `TipTapEditor`, same `ForumMention` extension
  (`TipTapEditor.tsx:94`); a fresh local forum's first board has no topic to
  open (the first run failed exactly there), and this way nothing is ever
  posted. The seeded e2e user mentions itself: `users/search/` is a
  username `istartswith` match that does not exclude the caller — no fixture
  user or endpoint mock needed.
- `playwright.config.ts`: added to both `*-authenticated` `testMatch`
  regexes and to all five unauthenticated projects' `testIgnore`.
- `web/docs/patterns/testing.md` TipTap section now points at the spec and
  states the two-list scoping rule.

Verification:

```text
$ ./node_modules/.bin/playwright test --project=chromium-authenticated e2e/forum-mention.spec.js
  2 passed (7.0s)   # setup-chromium + the spec; repeated: 2 passed (6.8s)
$ ./node_modules/.bin/playwright test --project=firefox-authenticated e2e/forum-mention.spec.js
  2 passed (10.9s)
$ eslint e2e/forum-mention.spec.js playwright.config.ts → clean; prettier --check → clean after --write
```

Source review doc `docs/audits/2026-09-04-forum.md` renamed to
`docs/audits/2026-09-04-forum-COMPLETED.md` — all findings resolved (#L5 was
the last open line; every other line was already `- [x]` or re-pointed).

### 2026-09-05 - Review round 1: cross-cutting + react-typescript (run 2026-09-05-0408)

Both reviewers, independently, on the first draft — every finding repaired:

- **[high, both] two assertions that could never fail.** After Escape,
  `toContainText('@e2e_test_u')` was already satisfied by the mention
  committed in step 2 (the query is a prefix of the label); and
  `page.goto('/forum')` destroys `<body>` so "no orphan dropdown" proved
  nothing about `onExit`. Repaired: assertions are structural — exactly one
  `span[data-type="mention"]` after Enter (exact text), still exactly one
  after Escape — and teardown is driven by an IN-APP route change (the
  breadcrumb `<Link>`, React Router unmounts the editor while the document
  survives), then the dropdown count is asserted on the live document.
- **[medium, react] `x + y > 0` cannot detect a null clientRect** (the div
  would sit in static flow at a large y). Repaired:
  `toHaveCSS('position', 'fixed')`.
- **[medium, react] substring commit check** could mask a wrong-item commit
  if a second `e2e_test_u*` user ever exists. Repaired by the node-level
  exact-text assertion above.
- **[medium, cross-cutting] ArrowDown is a no-op with one suggestion** yet
  the title claimed navigation coverage. Repaired: title/docblock claim
  "Enter commits the highlighted item"; the press stays for the real key
  path and the comment says item-to-item navigation is pinned by
  `forumMentionNode.test.ts` (no second seeded user; not worth a fixture).
- **[medium, both] `testing.md` said "reply editor"** — repaired: says
  new-thread composer, notes the reply composer has no E2E layer, and that
  a `page.goto()` teardown check can never fail.
- **[low, react] `body > div.z-50` is one portal away from ambiguous** —
  repaired: `data-testid="mention-suggestions"` (`DROPDOWN_TESTID`) set at
  both creation sites in `forumMentionNode.ts`; the spec selects on it.
- [low/info, cross-cutting] unflipped boxes / audit line — the reviewer read
  the tree before those edits landed; both are in the Work Log above.

Evidence after repair:

```text
$ playwright test --project=chromium-authenticated e2e/forum-mention.spec.js → 2 passed (6.9s)
$ vitest run src/components/forum/forumMentionNode.test.ts → 9 passed
$ npm run type-check → rc=0; eslint + prettier clean on the spec, config and node
```
