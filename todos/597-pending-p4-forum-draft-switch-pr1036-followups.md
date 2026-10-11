---
status: pending
priority: p4
issue_id: "597"
tags: [todos, follow-ups]
dependencies: []
---

# Follow-ups from PR #1036 (todo 575)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1036 (loading a board's stored draft on a category switch). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1036 (todo sweep run 2026-10-11-1448, group g12, todos 575); follow-ups: verified; 3 item(s) the curator did not return were kept as stored.

1. **low** `web/src/pages/forum/NewThreadPage.tsx:106` parseDraft only checks that the parsed value is an object, then casts it to StoredDraft. A stored draft with a non-string title or tags (e.g. {"title":1}) reaches setTitle/setTagsInput on a ?category= switch, and title.trim() then throws. The mount path had the same gap. | also: parseDraft casts the parsed JSON to StoredDraft without checking field types. A stored draft whose title or tags is not a string (e.g. {"title":1}) goes into string state, and title.trim() in canSubmit throws. This was already true on mount; the new key-switch load path now reaches it too. (NewThreadPage.tsx:107) | parseDraft only checks that the parsed value is an object, then casts it to StoredDraft. A stored draft like {"title":5} or {"tags":[]} passes through. The new draft.title || '' and draft.tags || '' then set non-string state, and title.trim() throws on the next render. (NewThreadPage.tsx:96)
2. **low** `web/src/pages/forum/NewThreadPage.tsx:283` When a ?category= switch loads board B's stored draft, only title, body and tags are replaced. Poll state and the handoff identification attachment stay from board A, so B's text can be posted with A's poll or image. | also: When a ?category= change loads board B's stored draft, only title/body/tags switch. Board A's poll fields (pollEnabled, question, options) and an 'Ask the community' identification handoff stay, so B's text can be posted with A's poll or attached image without the user noticing. (NewThreadPage.tsx:276)
3. **low** `web/src/pages/forum/NewThreadPage.test.tsx:681` The edited todo-549 assertion is justified and the 549 guard is still asserted. No test covers switching back from board B to board A to restore A's draft.
4. **low** `web/src/pages/forum/NewThreadPage.test.tsx:833` The unreadable-draft switch test does not assert that board A's draft survives the switch, and no test covers a stored draft that is valid JSON but not an object, such as 'null' or '5'.
5. **low** `web/src/pages/forum/NewThreadPage.tsx:107` parseDraft casts the parsed JSON to StoredDraft without checking field types. A stored draft whose title or tags is not a string (e.g. {"title":1}) goes into string state, and title.trim() in canSubmit throws. This was already true on mount; the new key-switch load path now reaches it too. | also: parseDraft casts JSON to StoredDraft without checking field types. A stored draft with a non-string title or tags, such as {"title":5}, is loaded by the new ?category= switch path and then crashes on title.trim() or tagsInput.trim(). The mount path already had this behaviour; the switch path now has it too.
6. **low** `web/src/pages/forum/NewThreadPage.tsx:276` When a ?category= change loads board B's stored draft, only title/body/tags switch. Board A's poll fields (pollEnabled, question, options) and an 'Ask the community' identification handoff stay, so B's text can be posted with A's poll or attached image without the user noticing.
7. **low** `web/src/pages/forum/NewThreadPage.tsx:96` parseDraft only checks that the parsed value is an object, then casts it to StoredDraft. A stored draft like {"title":5} or {"tags":[]} passes through. The new draft.title || '' and draft.tags || '' then set non-string state, and title.trim() throws on the next render.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1036 (todo 575).
