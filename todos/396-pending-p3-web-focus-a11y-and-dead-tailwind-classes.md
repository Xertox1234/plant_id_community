---
status: pending
priority: p3
issue_id: "396"
tags: [web, accessibility, tailwind, testing, tech-debt]
dependencies: []
source_review: "PR #771 review (react-typescript-reviewer + cross-cutting-reviewer)"
---

# Dead Tailwind classes, modal focus gaps, and three untested seams (from PR #771 review)

## Problem

The two-round review of PR #771 (todo 374) produced no further blocking
findings after round 1, but it surfaced several issues that are **pre-existing
or cross-cutting** rather than specific to that PR. Per the review-loop budget
in `CLAUDE.md`, they are collected here instead of a third round.

They are unrelated to each other except in provenance; take them independently.

## Findings

### 1. `ring-primary` emits no CSS — 22 occurrences across 10 files

**Measured against the built bundle**, not grepped: `vite build`, then search
`dist/assets/*.css` for `.ring-primary`. It is absent. `.ring-secondary` and
`.ring-line` are present; `--ring-primary` is not a defined token.

So every one of these focus rings is invisible:

```text
src/components/ui/Input.tsx                        src/pages/forum/ConversationPage.tsx
src/components/auth/GoogleSignInButton.tsx         src/pages/forum/NewThreadPage.tsx
src/components/forum/NewGroupConversationForm.tsx  src/pages/diagnosis/DiagnosisListPage.tsx
src/components/PlantIdentification/IdentificationResults.tsx
src/components/diagnosis/SaveDiagnosisModal.tsx    src/pages/diagnosis/DiagnosisDetailPage.tsx
src/components/diagnosis/ReminderManager.tsx
```

This is a **keyboard-accessibility defect**, not a cosmetic one: several of
these are form inputs and modal controls whose only focus affordance is the
ring. Tailwind 4 silently emits nothing for an unrecognised utility — no error,
no lint failure, nothing visible in a diff.

**The generalisable lesson, and the reason this is worth a todo rather than a
quiet fix:** a Tailwind class name cannot be validated by grepping the source,
because a name that appears 22 times looks *more* correct, not less. The only
authoritative check is whether the class appears in the compiled stylesheet.
PR #771 introduced `rounded-card` the same way (invented, 0 CSS) and it was
caught by exactly this build-and-grep check, not by review or lint.

Consider a CI guard: build the CSS, extract every `class`/`className` literal
from `src/`, and fail on any utility the bundle does not define. That would
have caught both this and `rounded-card` at write time.

### 2. Modal focus management is incomplete in `ConfirmDialog` and `ForumImagePicker`

Both are `aria-modal="true"` but neither traps focus — there is no
Tab/Shift+Tab loop, so a keyboard user can tab out of the dialog into the
inert content behind it. `ConfirmDialog`'s two-button layout makes this hard to
hit; `ForumImagePicker`'s open-ended tile grid plus a conditional "Load more"
makes it easy.

Related, same two files: the focus-return effect depends on `[open, onClose]`,
and callers pass an inline arrow (`onClose={() => setPickerOpen(false)}`), so
the effect re-runs on **every parent render**. Each run re-captures
`document.activeElement` as "the element to restore" — which, after the first
run, is something inside the dialog. A parent re-render while the dialog is
open (e.g. an image upload settling in `TipTapEditor`) therefore yanks focus
back to the autofocused control and poisons the restore target. Fix by
capturing the trigger once per open (a ref) rather than per effect run, or by
stabilising the callbacks with `useCallback` at the call sites.

### 3. Every per-row "Delete" button in the settings photo grid has the same accessible name

`SettingsPage.tsx`, `MyForumImagesSection`. The button text is a bare
`"Delete"` for every photo, and the adjacent `<img>` is a sibling, not part of
the button's accessible name. A screen-reader user hears "Delete, button" N
times with no way to tell which photo it targets. The `ConfirmDialog` message
does not name the photo either.

Symptomatic: the section's own tests can only disambiguate rows by array index
(`findAllByRole('button', {name: 'Delete'})[0]`) — exactly what assistive tech
cannot do. Suggested: `aria-label={\`Delete photo: ${image.alt || 'untitled'}\`}`,
and name the photo in the confirm message.

### 4. `ImageBlock.value` is typed non-nullable but the server sends `null`

`web/src/types/blog.ts` declares `value: ImageBlockValue`. `serialize_forum_body`
serialises a deleted image as `null` (PR #771 added the two runtime guards for
exactly this). Because the type disagrees, both regression tests must construct
their fixture with `as never` — an unsafe cast that defeats type-checking
entirely.

Widen to `ImageBlockValue | null`. The compiler would then flag any future
`block.type === 'image'` consumer that forgets the null check, and the `as never`
casts can go. Two consumers are already correct and should stay that way:
`IdentificationCard.tsx` (`{image && …}`) and Flutter's
`forum_body_block.dart` (`value == null` → `DeletedImageBlock()`).

### 5. The drop-position feature is untested repo-wide, and cannot be tested in jsdom

`TipTapEditor`'s `dropPosRef` — which makes a dragged-and-dropped image land
where it was dropped rather than at the top — has **no coverage at all**.
Measured by mutation: making the upload path ignore `dropPosRef` entirely
(`const insertAt = null`) leaves the whole 60-test `TipTapEditor` suite green.

The cause is structural: jsdom implements no layout, so ProseMirror's
`posAtCoords` never resolves a real coordinate and `dropPosRef` stays `null`
for the entire suite. PR #771's stale-coordinate fix is therefore correct but
unprovable there, and two attempts at a regression test for it survived
mutation before the gap was identified. Any change to drop positioning needs a
real browser (Playwright) to verify.

### 6. Two smaller test-surface gaps

- `ForumImagePicker`'s docstring claims focus is "moved in on open and returned
  to the trigger on close" — untested. Deleting `data-autofocus` or the entire
  focus effect turns no test red. `ConfirmDialog.test.tsx` has exactly this test
  for the component the docstring names as its model.
- `deleteForumImage`'s documented 404 ("no such image, or not in the forum
  collection") is handled generically: the row stays on screen with a Delete
  button now wired to a gone id. Not wrong, but asserted-in-a-docstring and
  never exercised.

### 7. Two new unresolved `act()` warnings

`SettingsPage.test.tsx`'s whole-page smoke tests produce 4 `act()` warnings on
`main` and 6 on the PR branch — the 2 new ones from `MyForumImagesSection`,
because those tests mount the page without awaiting each section's fetch. Every
dedicated `MyForumImagesSection` test is clean in isolation. Pre-existing
pattern, two more instances.

## Acceptance Criteria

- [ ] `ring-primary` is replaced with a token that actually compiles (or the
      token is defined), verified by finding the class in the built
      `dist/assets/*.css` — **not** by grepping the source
- [ ] A decision is recorded on the CI guard proposed in finding 1 (build the
      CSS, fail on any `className` utility the bundle does not define), and it
      is either implemented or explicitly declined with a reason
- [ ] `ConfirmDialog` and `ForumImagePicker` trap focus, and the focus-restore
      target is captured once per open rather than per effect run — with a test
      that fails if the trap is removed
- [ ] Each per-photo Delete control carries a distinct accessible name, and the
      section's tests select rows by that name instead of by array index
- [ ] `ImageBlock.value` is `ImageBlockValue | null` and the `as never` casts in
      `StreamFieldRenderer.test.tsx` / `forumBody.test.ts` are gone
- [ ] Finding 5 is resolved one of two ways, stated explicitly: either a
      Playwright test covers drop positioning, or the gap is recorded in
      `web/docs/patterns/testing.md` as a known jsdom limitation so the next
      person does not waste a cycle writing a test that cannot fail
- [ ] The picker's focus behaviour and `deleteForumImage`'s 404 path are either
      tested or their claims removed from the docstrings

## Notes

Provenance: round-1 review of PR #771 by `react-typescript-reviewer` and
`cross-cutting-reviewer`, plus two findings from build-output verification done
while repairing that PR. The PR's own blocking findings were fixed and
mutation-proven in that PR; nothing here blocked it.

Priority p3: finding 1 is a real accessibility defect and is the strongest
candidate to promote if anyone is doing a keyboard-accessibility pass, but
nothing here is a crash, a data risk, or a blocker for other work.
