---
status: pending
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

- [ ] A Playwright spec types `@` in the real composer and asserts the dropdown
      mounts, navigates, commits, and is removed on Escape.
- [ ] The spec runs only in the authenticated projects and passes locally.
- [ ] `web/docs/patterns/testing.md`'s TipTap section points at the spec.

## Work Log

### 2026-09-04 - Filed from the forum audit's Phase 6 review

- Non-blocking reviewer finding on the L5 fix; the Vitest lifecycle tests ship
  in the audit PR, this spec is the remaining prescribed layer.

## Notes

p4: the Vitest layer catches the regressions the file's own comments warn about
(stale dropdown resurrection, teardown); this is defence in depth for the
plugin-contract half.
