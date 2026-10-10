---
status: pending
priority: p4
issue_id: "538"
tags: [web, forum, follow-ups]
dependencies: []
source_todo: "537"
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

- [ ] Each of findings 1–6 is fixed (finding 1 with a test against a real editor after a selection
      transaction), or closed with a dated reason in the Work Log.

## Work Log

- 2026-10-10: Promoted out of todo 537 (run 2026-10-10-1537 triage) by owner decision. Line numbers are as of the
  source PR's merge; re-check each finding against main before acting on it.
