---
status: completed
priority: p4
issue_id: "538"
tags: [web, forum, follow-ups]
dependencies: []
source_todo: "537"
triage: ready
triaged: 2026-10-10
owner_decision: "Finding 3: log the schema-check failure and keep the stored draft untouched until the user edits; do not salvage the text (2026-10-10)"
---

# Forum composer TipTap JSON: follow-ups from PR #977 (todo 526)

## Problem

PR #977 moved the forum composer to TipTap JSON. Its review rounds reported six non-blocking findings, which
todo 537 parked. The owner promoted them here on 2026-10-10.

## Findings

1. **`web/src/pages/forum/ThreadDetailPage.tsx:919`** (medium, pre-existing). An untouched re-save still PATCHes
   when a body ends in an image, quote, list or heading. StarterKit v3's TrailingNode appends an empty paragraph on
   the first transaction, `docToBodyBlocks` emits `<p></p>`, and `isUnchangedBody` is false. Suggested: drop
   trailing empty paragraph blocks before comparing, and test against a real editor after a selection transaction.
2. **Tests** (low). The page test for the untouched-save case is tautological, since the stubbed editor never fires
   `onChange`. `forumBody.test.ts` `throughEditor` dispatches no transaction and uses `FORUM_SCHEMA_EXTENSIONS`,
   not the live extension set (mention suggestion + Placeholder). Suggested: mount the real `TipTapEditor` and
   assert `isUnchangedBody(editor.getJSON(), stored)`.
3. **`web/src/utils/forumBody.ts:134` `toComposerDoc`** (low). A JSON draft that fails the schema `check()` becomes
   `emptyDoc()` with no signal, and NewThreadPage's persist effect then overwrites the stored draft. A future schema
   change would silently delete drafts. Suggested: salvage the text nodes into paragraphs, or log and leave the
   stored draft untouched until the user edits.
4. **`web/src/pages/forum/ThreadDetailPage.tsx:621` `handleQuote`** (low, pre-existing). `isBlankDoc` treats an
   image-only reply as blank, so quoting drops the image already in the reply.
5. **Layering and perf** (low). `ForumBodyWriteBlock` lives in `utils/forumBody.ts` while `types/forum.ts`
   imports it; move it into `types`. `utils/forumBody.ts` imports `components/forum/forumEditorSchema`.
   `isBlankDoc` serialises the whole doc several times per keystroke; memoise or scan cheaply.
6. **Docs** (low). `.claude/agents/{wagtail,react-typescript}-reviewer.md` still name the removed helpers
   (`bodyBlocksToHtml`, `htmlToBodyBlocks`, …); the worker's sandbox denied that edit.

## Acceptance Criteria

- [x] Each of findings 1–6 is fixed (finding 1 with a test against a real editor after a selection
      transaction), or closed with a dated reason in the Work Log.

## Work Log

- 2026-10-10: Promoted out of todo 537 (run 2026-10-10-1537 triage) by owner decision. Line numbers are as of the
  source PR's merge; re-check each finding against main before acting on it.

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-10-2307)

- Findings 1–2 fixed: `isUnchangedBody` trims trailing content-less paragraph NODES on both sides (after a heading
  or list TrailingNode's paragraph joins the same run, so block-level trimming was not enough). New
  `TipTapEditor.test.tsx` cases mount the real composer, dispatch a selection transaction and assert the appended
  paragraph AND `isUnchangedBody` for bodies ending in an image, heading, list and quote (all failed before).
- Finding 3 fixed per owner decision: `toComposerDoc` logs a rejected draft (reason only, never its text) and
  NewThreadPage's persist effect writes nothing until the form differs from what it mounted with.
- Finding 4 fixed: new `isEmptyDoc` (blank AND no image) decides whether Quote keeps the reply; the reply and
  new-thread draft writers use it too, so an image-only draft is no longer deleted. Submit gate unchanged.
- Finding 5: `ForumBodyWriteBlock` moved to `types/forum.ts`; `isBlankDoc` memoised per document (WeakMap, same
  HTML rule, so `&nbsp;` stays non-blank). The `utils/forumBody` -> `components/forum/forumEditorSchema` import is
  CLOSED 2026-10-10 without change: that module and the two node files it imports are pure schema (no React, no
  services), and moving three files churns six importers for no behaviour gain.
- Finding 6 fixed: both reviewer agents now name `bodyBlocksToDoc` / `docToBodyBlocks`.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-10-2307)

- AC 1: `cd web && python3 scripts/todos/slot_env.py 2 -- npx vitest run src/components/forum/TipTapEditor.test.tsx src/utils/forumBody.test.ts src/pages/forum/NewThreadPage.test.tsx src/pages/forum/ThreadDetailPage.test.tsx && npx tsc --noEmit && echo TSC_OK && ! grep -n 'bodyBlocksToHtml\|htmlToBodyBlocks' .claude/agents/react-typescript-reviewer.md .claude/agents/wagtail-reviewer.md && echo NO_STALE_HELPER_NAMES && grep -n 'CLOSED 2026-10-10\|^- Finding' todos/archive/538-completed-p4-forum-composer-tiptap-json-followups.md` — evidence `.sweep-evidence/g2/538-ac0.txt` (not committed), last lines:

  ```text
  58:- Finding 3 fixed per owner decision: `toComposerDoc` logs a rejected draft (reason only, never its text) and
  60:- Finding 4 fixed: new `isEmptyDoc` (blank AND no image) decides whether Quote keeps the reply; the reply and
  62:- Finding 5: `ForumBodyWriteBlock` moved to `types/forum.ts`; `isBlankDoc` memoised per document (WeakMap, same
  64:  CLOSED 2026-10-10 without change: that module and the two node files it imports are pure schema (no React, no
  66:- Finding 6 fixed: both reviewer agents now name `bodyBlocksToDoc` / `docToBodyBlocks`.
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-10-2307)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
