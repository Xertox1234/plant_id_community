---
status: completed
priority: p3
issue_id: "278"
tags: [forum, web, react, wagtail, a11y]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "L2"
---

# Forum web: empty/onboarding states + app-wide role="alert" migration

## Problem

Deferred from todo 259 (forum web UX & a11y hardening) at implementation time.
Todo 259 satisfied all 7 of its acceptance criteria (the transient a11y
announcer, fetch race-guards, styled dialogs, composer hardening, sanitizer
tightening, scroll-to-top). Two pieces were explicitly held back because they
fall outside 259's AC and/or drag in backend work:

## Findings

- **L2** — Onboarding/empty states are bare. The `ForumIndex.intro` CMS field is
  never serialized so welcome copy can't reach the UI; the board list lacks a
  last-activity indicator. Full-stack: needs a Wagtail serializer change on the
  forum index page (backend) plus web rendering (CategoryListPage / CategoryCard).
- **M26 residue (app-wide)** — Todo 259 built the persistent live-region
  `AnnouncerContext` and migrated the forum write-path banners + the forum
  composer's upload error. The audit's M26 scope is app-wide: the remaining
  conditional-mount `role="alert"` sites outside forum flows still use the
  MDN-documented not-announced anti-pattern — `components/ui/Input.tsx:81`,
  `pages/auth/LoginPage.tsx`, and the other sites the audit enumerated. Migrate
  them to the persistent announcer / persistent-container pattern.

## Recommended Action

1. Serialize `ForumIndex.intro` in the forum index API and render it as welcome
   copy on CategoryListPage; add richer empty-state copy; surface last-activity
   on board cards (needs a `last_post_at` per board from the API).
2. Sweep the non-forum `role="alert"` conditional-mount sites and migrate them
   to `useAnnounce` (AnnouncerContext) or a persistent live-region container.

## Acceptance Criteria

- [x] `ForumIndex.intro` reaches the UI and renders as welcome copy
- [x] Board cards show a last-activity indicator
- [x] Non-forum `role="alert"` sites (Input, LoginPage, …) announce via the
      persistent-container pattern, verified by a content-swap test

## Notes

p3. Split out from todo 259 (see its Work Log, 2026-07-24). The AnnouncerContext
primitive and the pattern to copy already exist on main.

## Work Log

### 2026-07-30 - Started by completing-todos skill (run 2026-07-30-2346)

- Picked up by automated workflow. Branch `todo-278-forum-empty-states-alerts`.

### 2026-07-30 - Implementation

**L2 — intro transport decision.** `intro` was added to the existing
`GET boards/` flat envelope (`{results}` → `{results, intro}`) rather than
getting its own endpoint. Both render on the forum home screen and always
change together, so a second endpoint would have cost a second round-trip and
a second cache entry for one rich-text blob. The cost of the choice is that
`test_list_envelopes.py`'s `FLAT_ENVELOPE` guard and the README's envelope-table
row both had to change — done in the same commit, which is the workflow that
guard exists to force, and called out explicitly in the PR body. The
package README's "a host may add sections… additive only" clause is the
precedent.

**`last_post_at`.** Annotated as a correlated scalar `Subquery`, copying
`_annotate_topic_unread`'s idiom, so it folds into the single SELECT instead of
adding a `GROUP BY` over the Wagtail `Page` join. `last_post_at__isnull=False`
in the subquery is load-bearing: Postgres orders `DESC` as NULLS FIRST, so a
live topic with no published post would otherwise win the sort and blank the
column. Both properties have their own test.

**M26 sweep.** Persistent-container everywhere, not `useAnnounce`: `Input` is a
primitive that renders in trees with no `AnnouncerProvider` (it would throw),
and per-field errors belong beside their field. Sites migrated —
`components/ui/Input.tsx`, `pages/auth/LoginPage.tsx`,
`pages/auth/SignupPage.tsx`, `components/auth/GoogleSignInButton.tsx`,
`pages/auth/GoogleCallbackPage.tsx`, `pages/IdentifyPage.tsx`,
`pages/diagnosis/DiseaseDiagnosePage.tsx`.

Layout detail worth keeping: an always-mounted first child inside a
`space-y-*` container gives the *next* sibling a top margin it never had
(`sr-only` is absolutely positioned, but the sibling-margin selector still
matches). So Login/Signup's region was hoisted out of the form and carries its
own `mb-6`, and `GoogleSignInButton` traded `space-y-2` for a conditional
`mb-2`.

**Deliberate exception — `components/ErrorBoundary.tsx`.** The one `role="alert"`
left on the conditional-mount pattern, documented in the file. Both escapes are
closed by construction: it is mounted OUTSIDE `AnnouncerProvider` in
`main.tsx:80` (a provider inside the boundary is what a crash takes down), and
react-error-boundary replaces the whole subtree, so no node in that tree
pre-exists its content. It is a full-page takeover with an `<h1>`, not a banner
beside surviving content.

Mobile needs no change: `forum_api.dart` reads `data['results']` and
`ForumBoard.fromJson` ignores unknown keys, so both additions are
backward-compatible.

### 2026-07-30 - Verification

AC1 — `ForumIndex.intro` reaches the UI:

```
$ pytest packages/wagtail_forum/wagtail_forum/tests/api/test_board_list.py -q
11 passed
```

Covers: intro serialized as HTML; `""` when unset; `""` when the host has no
`ForumIndex` at all; `<script>`/`onerror`/`javascript:` stripped; Wagtail
`<a linktype="page">` expanded to a real href; deterministic pick across two
forum trees. Web side (`CategoryListPage.test.tsx`): renders as markup not
escaped text, DOMPurify second layer strips `img[onerror]`, no welcome block
when empty.

AC2 — board cards show last activity:

```
$ npx vitest --run src/components/forum/CategoryCard.test.tsx
PASS (11) FAIL (0)
```

`<time datetime>` + `aria-label` carrying the absolute date, and
"No activity yet" for a silent board. Backend pins the value: newest live
topic wins, non-live topics ignored, null-`last_post_at` topics ignored, and
one board vs three costs the same number of queries.

AC3 — non-forum `role="alert"` sites announce via content swap:

```
$ npx vitest --run src/components/ui/Input.test.tsx src/pages/auth/LoginPage.test.tsx \
    src/pages/auth/GoogleCallbackPage.test.tsx
PASS (21) FAIL (0)
```

The content-swap test is `Input.test.tsx` "swaps the error text inside the SAME
node instead of remounting it" — it holds a reference to the region across four
`rerender`s (empty → error A → error B → empty) and asserts node *identity*
each time, because a remounted region announces nothing. `LoginPage` has the
same swap assertion end-to-end through a failed login; `GoogleCallbackPage` pins
that the region exists and is empty during the spinner, before there is an
error to put in it. `grep -rn 'role="alert"' src/ --exclude='*.test.*'` leaves
one real attribute: the documented `ErrorBoundary` exception.

Full gates:

```
$ pytest -q                      # backend, whole suite
1340 passed, 0 failed, 8 skipped

$ npm run type-check             # tsc --noEmit
(clean)

$ npx vitest --run
PASS (746) FAIL (0)

$ npm run lint
ESLint: 0 errors, 1 warnings in 1 files   # warning is in a coverage artifact
```

`manage.py spectacular --validate --fail-on-warn` reports 186 warnings / 202
errors both with and without this branch's changes — byte-identical to the
`main` baseline, so the envelope change adds no schema regression.

### 2026-07-30 - Completed by completing-todos skill (run 2026-07-30-2346)

- Verification: all 3 acceptance criteria passed with quoted command output above.
- Review: see the review round below. 1 high (fixed), 1 medium (fixed), 3 low
  (fixed). No findings accepted-without-fix.

### 2026-07-30 - Review round (PR #514)

`django-drf-reviewer` + `react-typescript-reviewer` on the branch diff. The
bundled `/code-review` slash command is user-invocable only, so the review ran
through the agent fleet the skill prescribes.

**HIGH — untimed outbound HTTP on a public endpoint, via `expand_db_html`.**
The best finding of the round, and a genuine hole I put there. `ForumIndex.intro`
had no `features` restriction, so Wagtail's default Draftail toolbar offered
`embed` and `image`. Expanding an `<embed embedtype="media">` calls
`OEmbedFinder.find_embed`, which does `requests.get(endpoint, params=..., headers=...)`
— verified in `venv/.../wagtail/embeds/finders/oembed.py:61`, **no `timeout=`**.
On `/forum/boards/` (public, unauthenticated, CDN-fronted) an unreachable
provider hangs the request; a failed fetch raises before `update_or_create`, so
nothing is cached and every miss pays it again. The image path likewise does a
real PIL resize + storage write + Rendition row. All of it landed *before* nh3
dropped the resulting `<iframe>`/`<img>` — the sanitize discarded the markup
while still paying for it.

Verified both halves independently before fixing:

```
$ grep -n "requests.get\|timeout" .../wagtail/embeds/finders/oembed.py
61:            r = requests.get(          # no timeout kwarg

$ python -c "...features.get_default_features()"
DEFAULT: ['ai','ai','bold','document-link','embed','h2','h3','h4','hr','image','italic','link','ol','ul']
```

Fixed in two places, because they cover different threats:
1. `serialize_forum_intro` is now a **two-pass** sanitize — embeds are stripped
   BEFORE `expand_db_html` ever sees them, with a pre-expansion allowlist that
   keeps `a[linktype][id]` so page/document links still resolve. This is the
   load-bearing half: it holds for content a fixture, an import, or a direct DB
   write put in the column.
2. `ForumIndex.intro` now declares `features=[...]` without `image`/`embed`.
   The editor-side half — offering a button whose output silently vanishes from
   every client is its own bug. No migration: `makemigrations --check` is clean,
   because `features` is editor-only and not part of the field's deconstruct.

Both guards were checked for falsifiability by reverting to the single-pass
version — the media guard fails with the exact chain
`expand_db_html → EmbedHandler.expand_db_attributes → embeds.get_embed`, and
the image guard fails on `image.renditions.count() == 0`:

```
FAILED test_media_embeds_are_stripped_before_expansion_ever_runs
FAILED test_image_embeds_are_stripped_before_a_rendition_is_generated
2 failed, 12 deselected
```

The first draft of the image guard used a nonexistent image id and passed in
both modes — hollow, since Wagtail's handler swallows `DoesNotExist`. Replaced
with a real image and a rendition-count assertion.

**MEDIUM — `BoardListView` had no `@extend_schema`.** Every sibling list view
(`TopicListView`, `SearchView`, `SyncView`) was decorated by todo 277's envelope
work; drf-spectacular infers from `serializer_class` and cannot see the custom
`{results, intro}` dict, so `intro` was landing undocumented in that gap. Added,
matching the siblings.

**LOW ×3** — all fixed: `blockquote` dropped from `INTRO_ALLOWED_TAGS` (not a
registered Wagtail feature, so unreachable and contradicting its own comment);
the multi-tree asymmetry (`results` spans every visible tree, `intro` comes from
one) documented in `_visible_forum_index` and now asserted in
`test_intro_comes_from_the_first_index_in_tree_order`, which previously checked
only `intro`; type hints added.

Reviewer checks that came back clean and are worth keeping: `.public()` correctly
excludes an index restricted via any ancestor (`PageQuerySet.private_q()` matches
`descendant_of_q(..., inclusive=True)`), and the `Subquery` annotation is
portable across Postgres/SQLite precisely because NULLs are excluded before
ordering rather than relied on to sort last.

Post-fix gates:

```
$ pytest -q
1343 passed, 8 skipped

$ manage.py spectacular --validate --fail-on-warn
186 warnings / 202 errors   # unchanged from the main baseline
```

### 2026-07-30 - Review round 2 (web, PR #514)

The first `react-typescript-reviewer` dispatch died without returning; re-run
synchronously. Worth recording that it caught **a regression I had shipped and
then personally cleared as safe.**

**HIGH — Tailwind v4 changed `space-y-*`, and I checked against the v3 model.**

```css
:where(.space-y-6 > :not(:last-child)) { margin-block-end: … }
```

margin-BOTTOM on all but the LAST child — not v3's margin-top on
`:not(:first-child)`. Earlier in this same session I inspected
DiseaseDiagnosePage, saw the region was not the *first* child, concluded "no
shift", and moved on. Wrong question entirely: appending an always-mounted
region after the Diagnose button stops the BUTTON being `:last-child`, giving it
24px of trailing whitespace in the idle state. `sr-only`'s `margin:-1px` cancels
the region's own margin but does nothing for the sibling before it.

Verified the rule myself rather than taking the reviewer's word, by compiling
this project's own Tailwind:

```
$ npx @tailwindcss/cli -i in.css -o out.css --content probe.html
:where(.space-y-6 > :not(:last-child)) {
  margin-block-end: calc(calc(var(--spacing) * 6) * …);
}
```

Fixed by giving button + region a shared wrapper so the container's direct-child
list is unchanged, with `mt-6` on the region to reproduce the old spacing.
Login/Signup/GoogleSignInButton were already safe because they hoist the region
out of the spaced container — the right remedy reached by the wrong reasoning,
now documented in place so the next person doesn't repeat the v3 assumption.

**MEDIUM — IdentifyPage: a persistent region with a non-persistent ancestor.**
Flagged independently by both reviewer runs. The region sat inside
`{(results || loading || error) && …}`. The normal flow is fine (the ancestor
mounts before a save can start — which is exactly why my own trace cleared it),
but pick a new file mid-save and `handleFileSelect` nulls `results`, the ancestor
unmounts, and the pending rejection renders nowhere at all. Hoisted out; no
`space-y` in that file, so layout-neutral.

**The coverage pattern is the real lesson.** Every migrated site that got a
persistence test stayed correct; the two that didn't are the two that were
wrong. Added tests: `IdentifyPage.test.tsx` (new file — it was the only migrated
site with no test at all), DiseaseDiagnosePage (content-swap + a structural
guard that the region is not a direct `space-y-6` child), and the LoginPage
node-identity assertion ported to SignupPage and GoogleSignInButton.

Both new structural guards were falsified by stashing ONLY the component fixes
and re-running with the new tests in place:

```
× IdentifyPage > mounts the save-error live region on first paint, before any results exist
× DiseaseDiagnosePage > keeps the live region out of the space-y child list
  → expected <div …> not to be <div …>  // Object.is equality
```

**LOW, fixed:** CategoryListPage gated the welcome block on the RAW intro
string — an intro of only-disallowed markup is truthy but sanitizes to `''`,
rendering an empty padded box; now sanitized once via `useMemo` and gated on the
result. Its sanitizer test asserted only `img[onerror]`, which would also pass
under the FULL preset that allows images outright; now asserts no `img` at all,
plus attribute- and `javascript:`-URI stripping on allowed tags.

**Declined, with reasons:** `Timestamp`'s `aria-label` lengthening the
CategoryCard link's accessible name — ThreadCard already does exactly this
inside its own card link, and audit L12 put it there deliberately; diverging
here would make the two cards inconsistent. And the empty-state link's tap
target, which is an app-wide pattern (every auth-page link shares it), so fixing
one instance in this PR buys nothing.

Post-fix gates:

```
$ npx vitest --run
PASS (753) FAIL (0)     # was 746

$ npm run type-check && npm run lint
(clean; 0 errors)
```

### 2026-07-30 - Merge

CI: 16 checks green. `Claude Code Security Review` failed **closed** without
running — `"result":"Credit balance is too low"`, `api_error_status: 400`, so
`claudecode-results.json` had no `findings` array and the gate could not verify
severity. Not a finding; the known credit blocker (see
`project_security_review_check_credit_block.md`). The bundled `security-review`
skill was run locally in its place and returned no HIGH/MEDIUM findings.

User explicitly authorized bypassing the credit-blocked check.
