---
status: completed
priority: p3
issue_id: "314"
tags: [forum, flutter, mobile, composer, rich-text]
dependencies: ["294"]
source_review: "todo 294 (re-pointed 2026-08-17)"
---

# Mobile forum composer: rich text (bold/italic/link/list/inline-code)

## Problem

Todo 294 shipped the image half of "mobile forum composer: images and rich
text" (photo upload/attach). This todo carries forward the other half: the
mobile composer is still text-first — bold/italic/links/lists/inline-code are
**rendered** on read (`ForumBodyRenderer`/`ForumHtmlText`) but not authorable
on mobile. Split out per an advisor consult on 2026-08-17.

## Findings

- Todo 294's own Notes named this split before it happened: *"The image half
  is worth doing alone if the rich-text half slips — they are sequenced, not
  coupled."*
- **The asymmetry that justified the split**: the image half had a complete,
  tested backend contract and needed zero new UI paradigm — `image_picker`
  was already a dependency, `ForumImageBlock` already parsed on read, and
  appending an `image` block was a one-line change to the write payload. This
  half needs a mobile rich-text **editing surface** that emits HTML matching
  nh3's server-side allowlist — there is no such widget in the app today.
  Whatever gets picked (`flutter_quill`, a hand-rolled toolbar, a
  delta→HTML mapping) is a new primitive and a real dependency decision, not
  a mechanical extension of existing code.
- **Load-bearing interaction with already-shipped code**: `isSingleEditableParagraph`
  (`forum_body_block.dart`, shipped in todo 292) currently returns `false`
  for any single paragraph whose HTML contains real markup — exactly what a
  rich-text composer starts producing. Once mobile can author marks, the
  "can this post be safely edited on mobile" gate from todo 292 needs to
  either (a) widen to recognize composer-authored rich HTML as
  round-trippable, or (b) the edit composer needs a rich-text mode flag
  distinguishing "the mobile app wrote this" from "a web-authored post with
  unrelated markup." Do not assume this is free — it is the same shape of
  gap that 292's code review caught (a real, reproduced corruption risk),
  just in the opposite direction this time (something that COULD be
  editable getting incorrectly gated out, or something that should stay
  gated getting incorrectly let through).
- The web composer's TipTap FORUM allowlist is the parity target — the
  renderer (`ForumHtmlText`) already handles everything in it; this todo is
  purely "what the composer can emit", not a renderer change.
- Upload/sanitization precedent from todo 294 applies here too: the server
  is the source of truth for what markup survives (nh3 allowlist on write);
  the client must not assume a locally-composed tag survives without
  testing it against the actual server contract.

## Recommended Action

1. Pick the editing-surface approach first (a real design decision, not a
   default) — options include `flutter_quill` (a maintained rich-text
   editor with delta output) vs. a minimal hand-rolled toolbar over
   `TextField` selections that inserts/wraps marker syntax before HTML
   generation. Consider `kimi-challenge` for this specific choice per
   `CLAUDE.md`'s Cheap-Worker Delegation — it is exactly the kind of
   "pressure-test before committing to an architectural decision" case that
   tool exists for.
2. Scope strictly to the web FORUM allowlist (bold, italic, link, list,
   inline-code, per the original todo 294 Findings). Do not invent
   mobile-only marks the renderer cannot display.
3. Resolve the `isSingleEditableParagraph` interaction explicitly (see
   Findings) before wiring rich text into the edit path — get this wrong
   and either legitimate posts become uneditable or real content gets
   silently discarded on save, the exact class of bug 292's review caught.
4. Round-trip test per mark: compose → submit → the fake API's captured
   body → render via `ForumBodyRenderer`/`ForumHtmlText` → assert the mark
   survives, not just that the button toggled a UI state.

## Technical Details

- Client lives in `plant_community_mobile/lib/features/forum/` —
  `models/forum_body_block.dart` (`buildParagraphBody`,
  `isSingleEditableParagraph`, `plainTextFromParagraphHtml`),
  `screens/forum_composer_screen.dart`, `services/forum_composer_controller.dart`.
- Read `plant_community_mobile/docs/patterns/riverpod.md` and
  `.../flutter-patterns.md` before writing.
- Codegen gate: editing a `@riverpod` source needs
  `flutter pub run build_runner build --delete-conflicting-outputs`; CI
  blocks on a stale `.g.dart`, local `flutter analyze` does not catch it.

## Acceptance Criteria

- [x] Bold/italic/link/list/inline-code round-trip through compose → render
      — test per mark, asserting the rendered output, not just controller
      state — 77+ new tests in `forum_rich_text_markup_test.dart` (marker
      generation/parsing per mark) and `forum_rich_text_toolbar_test.dart`
      (toolbar transforms + composer round-trips asserting rendered
      `fontWeight`/`fontStyle`/tap-triggers-`onOpenLink`, not just text
      presence), shipped in PR #574
- [x] The `isSingleEditableParagraph` interaction (Findings) is resolved
      explicitly, with a test proving the resolved behavior on both a
      mobile-rich-text-authored post and a web-authored post with
      unrelated markup — resolved by NOT touching the gate: PR #574 adds a
      separate constrained HTML→marker-text parser that lets the edit
      composer open a rich-text-authored (or grammar-compatible
      web-authored) post in rich-edit mode, falling back untouched to the
      existing plain-text path for anything outside its grammar.
      `isSingleEditableParagraph` and its existing test suite from todo 292
      are confirmed untouched by the diff
- [x] `flutter test` passes; `flutter analyze` clean — re-verified fresh on
      `origin/main` post-merge (see Work Log)

## Work Log

### 2026-08-17 - Split out of todo 294

- Advisor consult during todo 294 confirmed the image/rich-text split todo
  294 already flagged in its own Notes. Todo 294 shipped the image half
  (`ForumApi.uploadImage`, `ForumComposerController.uploadImage`, the
  composer screen's "Add photo" flow); this todo carries the rich-text half
  forward, re-pointed rather than checked off in 294's AC3.

### 2026-08-29 - Implemented, reviewed, merged (PR #574) — todo file reconciled

- Implementation happened on `worktree-todo-314-composer-rich-text` (3
  commits: implementation, a self-caught toolbar-seam/list-toggle fix round,
  a final-review fix round) via a full subagent-driven-development loop, but
  the todo file itself was never updated as part of that work — this entry
  reconciles it after the fact, discovered while closing out todo 294 (local
  `main` had drifted ~40 commits behind `origin/main`).
- **Design decision**: hand-rolled marker-grammar toolbar over the existing
  `TextField`, not `flutter_quill` — confirmed with the user before
  implementation, no new dependency. A small markdown-style grammar
  (`**bold**`, `_italic_`, `` `code` ``, `[text](url)`, `- item`) is typed
  into the same field; toolbar buttons insert/wrap markers around the
  current selection; a generator converts marker text to the exact
  `<strong>`/`<em>`/`<a>`/`<ul><li>`/`<code>` tags the web app's TipTap
  FORUM allowlist already produces and `ForumHtmlText` already renders.
  `<ol>` (numbered lists) deliberately unsupported — the renderer treats
  `<ul>`/`<ol>` identically today, so there's nothing to gain until it grows
  numbered rendering.
- **New files**: `forum_rich_text_markup.dart` (generator + a constrained
  HTML→marker-text parser, with a marker-character
  escaping/sentinel-substitution scheme preventing silent corruption when a
  web-authored post containing a literal `_`/`*`/backtick is reopened and
  resaved on mobile), `forum_rich_text_toolbar.dart`. Both existing
  `forum_body_block.dart` and `forum_composer_screen.dart` were extended,
  not restructured.
- **Final whole-branch review (opus) found 3 real Important bugs**, all
  confined to the two new files, one fix wave addressed all three, verified
  via stash-based mutation checks (revert → exactly the new tests fail) and
  independently re-confirmed by a scoped re-review:
  - a stale IME `composing` range that could trip a Flutter assert during
    ordinary Android typing
  - a link href containing `)` silently truncated — reachable through the
    link dialog's own primary path (plausible on a plant forum, e.g.
    parenthesized species-disambiguation URLs)
  - toolbar buttons dead on the very first tap, before the field had ever
    been focused
- Merged as PR #574, commit `ff91c9c89aabc4c79a23caf2baff531f3601d452`,
  2026-08-29T03:49:02Z. All 17 CI checks green, including `Flutter analyze,
  test, and debug build`.
- **Re-verified fresh** on this reconciliation branch (`origin/main` at the
  merge, both this PR and todo 294's #557 present):

  ```
  $ flutter test
  00:24 +420: All tests passed!

  $ flutter analyze lib/ test/
  Analyzing 2 items...
  No issues found! (ran in 2.3s)
  ```

## Notes

p3. Split from todo 294 on 2026-08-17. Depends conceptually on 294's
`ForumComposerController`/`forum_composer_screen.dart` shape (build on top
of it, don't restructure it without cause).
