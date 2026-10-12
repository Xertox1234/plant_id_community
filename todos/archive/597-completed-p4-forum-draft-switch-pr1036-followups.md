---
status: completed
priority: p4
issue_id: "597"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "On a category switch to board B's draft, reset the poll fields and drop the identification attachment (owner, 2026-10-11)"
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1036 (todo 575).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- Findings 1, 5 and 7 (one defect): `parseDraft` in `web/src/pages/forum/NewThreadPage.tsx` now validates rather than casts. JSON that is not a plain object (`null`, `5`, `[]`) reads as no fields, and a non-string `title` or `tags` reads as absent, so `title.trim()` can no longer throw on mount or on a `?category=` switch. Tests cover both paths; the stored value is still left untouched until the user edits.
- Findings 2 and 6 (one defect, owner decision 2026-10-11): when a `?category=` switch loads board B's stored draft, the poll fields go back to their defaults (off, blank question, two blank options, no close time, single choice) and the identification attachment is dropped. Tests check that the post sends neither `poll` nor `identification`. A switch to a board with no stored draft keeps the form as it is, poll included, as the earlier owner decision on keeping text requires.
- Finding 3: new test for switching A to B and back to A. It restores A's draft and A's next edit extends A's key, not B's.
- Finding 4: the unreadable-draft switch test now checks that board A's stored draft is unchanged, and a parametrised mount test covers stored drafts `null`, `5`, `[]` and wrong-typed fields.
- Against the unfixed component, the four new behaviour tests fail and the coverage-only tests (findings 3 and 4) pass, as expected.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `bash -c "cd web && npx vitest run src/pages/forum/NewThreadPage.test.tsx --reporter=verbose && grep -n -A6 'Implemented by the todo sweep (run 2026-10-11-2219)' todos/archive/597-completed-p4-forum-draft-switch-pr1036-followups.md"` — evidence `.sweep-evidence/g14/597-ac0.txt` (not committed), last lines:

  ```text
  45-- Findings 1, 5 and 7 (one defect): `parseDraft` in `web/src/pages/forum/NewThreadPage.tsx` now validates rather than casts. JSON that is not a plain object (`null`, `5`, `[]`) reads as no fields, and a non-string `title` or `tags` reads as absent, so `title.trim()` can no longer throw on mount or on a `?category=` switch. Tests cover both paths; the stored value is still left untouched until the user edits.
  46-- Findings 2 and 6 (one defect, owner decision 2026-10-11): when a `?category=` switch loads board B's stored draft, the poll fields go back to their defaults (off, blank question, two blank options, no close time, single choice) and the identification attachment is dropped. Tests check that the post sends neither `poll` nor `identification`. A switch to a board with no stored draft keeps the form as it is, poll included, as the earlier owner decision on keeping text requires.
  47-- Finding 3: new test for switching A to B and back to A. It restores A's draft and A's next edit extends A's key, not B's.
  48-- Finding 4: the unreadable-draft switch test now checks that board A's stored draft is unchanged, and a parametrised mount test covers stored drafts `null`, `5`, `[]` and wrong-typed fields.
  49-- Against the unfixed component, the four new behaviour tests fail and the coverage-only tests (findings 3 and 4) pass, as expected.
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
