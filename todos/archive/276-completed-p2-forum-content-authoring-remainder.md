---
status: completed
priority: p2
issue_id: "276"
tags: [forum, web, drf, product-ux]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M1, M5, M11, L8"
---

# Forum: content-authoring & discovery remainder (M1, M5, M11, L8)

## Problem

Split out of todo 256 on 2026-07-23 (user triage: "top-value slices only" —
256 retained H8 search + H9 SEO and was completed/archived; these four
lower-value or now-smaller findings moved here). Residual is stated against
**current `main`** (post Wave 1 #473 + the H8/H9 slices), not the original
2026-07-11 audit line numbers.

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `web` = `web/src`.

## Findings

- **M1** — No quote-reply: `BlockQuoteBlock` exists in schema + renderer, but the
  TipTap composer can't produce it (toolbar omits the control; nh3 sanitize
  contract must admit it) (`W/blocks.py`). **Coordinate the nh3 / renderer-preset
  contract with todo 259** (renderer preset tightening for quote blocks lives
  there).
- **M5** — No tags/taxonomy beyond boards — species/genus/symptom tags are the
  natural discovery axis for this domain. `TaggableManager` on `Topic`
  (django-taggit is already a Wagtail dependency) + migration + API serialization
  - a tag filter UI; keep board taxonomy primary.
- **M11** — Per-post permalink **copy-link control** only. NOTE: Wave 1 (#473)
  already shipped the deep-link chase + scroll-after-load (posts beyond page 1
  are pulled in and scrolled to — `web/pages/forum/ThreadDetailPage.tsx`
  arrival effect + `collectAllPosts`). The residual is just a copy-link button
  per post (build `…/forum/{cat}/{thread}#post-{id}` from the current thread
  URL). A `/posts/{id}` resolver is optional — the client-side chase already
  lands a fresh visitor correctly.
- **L8** — `index.AutocompleteField("title")` declared on `Topic` (`W/models/topics.py:67`)
  but nothing calls `backend.autocomplete()` — dead index cost. **Decide here**:
  wire a lightweight typeahead suggest endpoint for the search box, or drop the
  field. (The `searchForumUsers` @mention typeahead at `forumService.ts` is the
  wiring pattern if kept.)

## Recommended Action

1. **M11 copy-link** (smallest, do first): copy-link control per post in
   `PostCard`; builds the deep-link from the current thread URL + `#post-{id}`;
   relies on the existing Wave-1 chase to land the visitor.
2. **L8**: decide typeahead-vs-delete and record the rationale; wire or remove.
3. **M5 tags**: `TaggableManager` on Topic + migration + API + tag filter UI.
4. **M1 quote-reply** (last): TipTap toolbar Quote button emitting the quote
   block; extend the nh3/composer contract; coordinate with todo 259.

## Acceptance Criteria

- [x] Copy-link on a post lands a fresh visitor on the correct page + anchor
      (including posts beyond page 1 — reuse the Wave-1 chase)
- [x] Quote-reply produces a block that round-trips composer → API → renderer
- [x] Topics taggable with a working tag filter (or descope recorded)
- [x] L8 typeahead wired OR `AutocompleteField` removed — decision recorded

## Work Log

### 2026-07-30 - Implemented (run 2026-07-30-0259)

Branch `forum/todo-276-content-authoring-remainder`. Order deliberately swapped
from the Recommended Action (M11 → L8 → M1 → M5): M5 has an explicit descope
escape hatch in its AC and M1 does not, so the non-descopable work went first.

**M11 (copy-link) — already shipped; this was a verification task.**
`PostCard.handleCopyLink` landed in Wave 1 (#473, squash 895e948). Confirmed the
residual claim: post pagination is **cursor**-based, so no page ever appears in
the URL — the canonical thread path + `#post-N` is the whole address, and
ThreadDetailPage's Wave-1 arrival effect chases later cursor pages. The existing
PostCard test only asserted `stringContaining('#post-21')`, which would pass even
if the path were wrong, so it was tightened to assert the exact URL and that a
query string (`?order=`) is dropped as view state.

**L8 — decision: no typeahead endpoint; `AutocompleteField` KEPT.**
*(Superseded the initial call — see the 2026-07-30 code-review entry below. The
field was first REMOVED on the rationale that nothing called
`backend.autocomplete()`; that premise was wrong — Wagtail's own snippet-listing
search is the caller — and the removal was reverted in-PR.)* The typeahead half
of the decision stands: no suggest endpoint was wired, because Wave 1 already
shipped header search + the full-text SearchView.

**M1 (quote-reply) — the crux was the value's TYPE, not the toolbar.**
`BlockQuoteBlock` subclasses `TextBlock` (verified in the installed wagtail), so a
quote value is PLAIN TEXT that `api/sanitize.py` deliberately leaves unsanitized
("text by contract"). Four layers:
- `forumBody.ts` lifts a **top-level** `<blockquote>` into its own `quote` block
  (inline markup would be flattened by nh3). Multi-paragraph quotes join with
  `\n\n` (raw `textContent` mashed "onetwo"); a nested `<img data-image-id>` is
  **hoisted out** as its own block rather than silently dropped.
- `bodyBlocksToHtml` HTML-escapes quote text on the way back into the composer,
  or stored text re-parses as real document structure on the next edit.
- `StreamFieldRenderer` — the security fix. The forum path now renders quote text
  as escaped text; the previous `renderTextOrSafeHtml` route sent any value
  containing `<` through the **broad blog STREAMFIELD preset**. Scoped via the
  existing `mentionHighlight` forum signal so blog quotes keep rich text.
- TipTap toolbar Quote button; the stale "blockquote intentionally omitted"
  comment corrected.
Flutter needed no change — `_Quote` is a plain `Text` widget (verified).

**M5 (tags) — implemented, not descoped.** `TaggableManager` on `Topic` +
migration `0017_topic_tags`, bounds in `conf.py` read at **request** time (so a
host override / `@override_settings` applies), normalization (trim, collapse inner
whitespace, lowercase, dedupe, reject commas — taggit's own separator),
serialization on list + detail, `?tag=` exact-match filter, and web UI (chips,
URL-driven filter with clear control, create-form input). Tag chips render
**outside** the card-level `<Link>` — a nested `<button>` in an `<a>` is invalid
HTML and breaks `getByRole('link')`.

**Verification** (all commands run on this branch):

- `python -m pytest packages/wagtail_forum apps/forum_host --create-db -q`
  → `Pytest: 589 passed` (`--create-db` per the migration-change rule).
  First run was `588 passed, 1 failed` — `test_docs.py::test_readme_documents_every_setting`
  caught the two new settings undocumented; README table updated, then green.
- `npm run type-check` → clean (`tsc --noEmit`, no output).
- `npm run lint` → `ESLint: 0 errors, 1 warnings in 1 files` (the warning is in
  the pre-existing coverage artifact `block-navigation.js`, untouched here).
- `./node_modules/.bin/vitest --run` → `Test Files 54 passed (54) / Tests 727 passed (727)`.
  (Direct binary, not via RTK — RTK mangles test-filter args.)
- `python manage.py check` → `System check identified no issues (0 silenced)`.
- `python manage.py makemigrations --check --dry-run` → `No changes detected`.
- `python manage.py spectacular` → exit 0; no forum-related errors (the printed
  "unable to guess serializer" lines are pre-existing, all in `apps/users`/`apps/core`).

**Query-count pins updated (5).** `prefetch_related("tags")` adds exactly one
query per request, so the exact pins moved 3→4 (topics list, anon + authed) and
4→5 / 5→6 (topic detail). Each got an explanation per `docs/rules/testing.md`;
`test_topic_tags.py` adds the pin that actually guards the N+1 (20 tagged topics,
still 4 queries).

**Incident during this run:** `StreamFieldRenderer.test.tsx` already existed; a
stale shell cwd made an `ls` report it missing, and creating it with `cat >`
overwrote 565 lines of existing tests. Caught via `git status` showing ` M`
instead of `??`. Restored with `git checkout HEAD --` and re-appended as a pure
addition — the diff is now `43 insertions(+), 0 deletions(-)` and the file's own
suite went 4 → 35 tests. Lesson: the Write tool's "File has not been read yet"
refusal was a correct guard; routing around it with a shell redirect defeated it.

### 2026-07-30 - Code review + repairs

Ran `code-review-orchestrator` (triage) → `wagtail-reviewer`,
`cross-cutting-reviewer`, `react-typescript-reviewer`. 2 high, 4 medium, 3 low,
plus several "verified clean" notes. **All blocking findings repaired**, each
with a test; the two HIGH ones were independently confirmed against source
before repair rather than taken on trust.

**HIGH — tag-list DoS** (`api/serializers.py`). `normalize_topic_tags` deduped
into a *list* (`if name not in seen`) → O(n²), and the `TOPIC_MAX_TAGS` bound was
only checked after the loop. Reviewer benchmarked 30k tags at 2.24s, well inside
the 10MB body cap. Verified in the installed DRF source that
`ListField(max_length=…)` is enforced by a validator running *after*
`to_internal_value` has already child-validated every element — so `max_length`
alone cannot bound the work. Fixed with `_BoundedTagListField` (raw-length check
first, mirroring `MAX_BODY_BLOCKS` in api/sanitize.py) + O(1) dict dedup.

**HIGH — stale Load More race** (`ThreadListPage.tsx`). Confirmed by reading the
code: the Load More block is gated on `nextCursor` alone (a sibling of the
`loading` ternary) and `nextCursor` was never cleared on reload, while
`handleLoadMore` reads `loadGenRef` *at click time* — which the reload has
already bumped, so the generation guard cannot fire. Clicking during a tag reload
appended wrong-filter rows and overwrote the new cursor with a stale one. Fixed
by clearing `nextCursor` when a reload starts and gating the control on
`!loading`. (Pre-existing for `?sort=` too; the tag filter added a second
trigger.)

**MEDIUM — `?tag=` could not find admin-created tags.** The API is not the only
writer: the Wagtail admin panel writes tags through taggit's widget, bypassing
`normalize_topic_tags`, and taggit's `Tag.name` is case-sensitive. A
moderator-added "Monstera" was permanently unreachable from the very `#Monstera`
chip the UI renders from that name. Switched to `tags__name__iexact` — which then
*requires* `.distinct()`, because "Monstera" and "monstera" are two distinct Tag
rows and a topic carrying both would join twice and appear duplicated. Chose this
over adding admin-form plumbing: it fixes the bug for every write path.

**MEDIUM** — `?tag=` added to the `extend_schema` description (was undiscoverable
for codegen clients). **MEDIUM** — 44px tap target on the interactive tag chip
(`min-h-11`, matching the Clear-filter button in the same feature).
**MEDIUM** — stale "still 4" comment in `test_topic_detail.py` contradicting its
own updated `== 5` assertion.
**LOW** — `TOPIC_TAG_MAX_LENGTH` now clamped to taggit's `Tag.name` width (100);
a host raising it past that produced a `DataError`, which is *not* an
`IntegrityError` and so escaped `_create_topic`'s slug retry as a 500.
**LOW** — `bodyBlocksToHtml` splits on `/\n{2,}/` (blank line) instead of `/\n+/`,
so a single `\n` is no longer promoted to a paragraph break on every re-edit.

**Accepted, not repaired** (recorded rather than silently dropped):
- Image-hoist reordering inside a quote — an image nested between quoted
  paragraphs is moved after the quote. Documented trade-off (the alternative is
  silently dropping it); the reviewer explicitly rated it no-action.
- The topic-DETAIL prefetch pin cannot detect its own removal — for a
  single-object retrieve, `obj.tags.all()` costs one query either way. The
  *list* pin (`test_topic_tags.py`, 20 tagged topics, still 4) is the real N+1
  guard; noted honestly rather than pretending the detail pin guards structure.

**Mutation-tested the repairs** (a test that cannot fail is not a test):
reverting `.distinct()` and the length clamp each turned their test red as
expected. The first version of the oversized-list test did **not** — it was
passing via the ordinary max-count check, so removing the early guard left it
green. Rewrote it to assert the specific `"Too many tags."` message; re-mutating
then produced `14 passed, 1 failed`. Files restored from backup after each
mutation.

**Re-verification after repairs:**
- `python -m pytest packages/wagtail_forum apps/forum_host --create-db -q` → `Pytest: 593 passed`
- `./node_modules/.bin/vitest --run` → `Test Files 54 passed (54) / Tests 729 passed (729)`
- `npm run type-check` → clean; `npm run lint` → `0 errors` (1 pre-existing warning in `block-navigation.js`)
- `flake8` on all changed backend files → clean (fixed one `W391`)

### 2026-07-30 - Post-review coverage gap + PR

PR #511. All required CI checks green (16 pass). The one red check is
non-required `CodeQL` — analysed as a false positive and **left open rather than
dismissed** (that call belongs to the repo owner); reasoning posted as a PR
comment. It did surface one *real* nearby issue, fixed in `50e858b`: a bare
body-level text node's `textContent` was pushed verbatim into a `paragraph`
block whose value IS HTML, so `a < b` re-parsed as markup. Escaping it is also
the correct rendering.

**Coverage gap caught after the review round.** Every `?tag=` test used an
anonymous client — which takes `_annotate_topic_unread`'s constant
`Value(False)` branch. An authenticated request instead builds
`.alias(_read_baseline=Coalesce(Subquery(...), ...))` and annotates off an
expression deliberately NOT in the select list, and Postgres constrains what
`ORDER BY` may reference under `SELECT DISTINCT`. Since `.distinct()` was added
during the *repair* round (after the main test pass) and every tag fixture was
1–2 topics, the combination of authenticated + distinct + cursor pagination had
zero coverage. Closed in `0cab18c` with a 25-topic authenticated paginated test:
green against Postgres (the local test DB is postgresql, matching CI), all 25
slugs exactly once across both cursor pages. No production bug — but it was the
last untested shape.

Final: `594 passed` backend, `731 passed` web.

### 2026-07-30 - Bundled /code-review (medium) — 3 findings, all fixed

Run AFTER the checklist reviewers and CI had signed off. Fresh evidence of the
todo-244 "the two passes are complementary" finding: the checklist pass had
actively *confirmed* the thing this pass disproved.

**#1 medium — REVERSED the L8 decision.** My rationale for dropping
`index.AutocompleteField("title")` — "nothing ever calls `backend.autocomplete()`"
— was derived from grepping this repo, and was wrong. The caller is Wagtail:
`TopicViewSet` is a `SnippetViewSet` with `search_fields = ["title"]`, and the
generic `search_queryset` (`wagtail/admin/views/generic/base.py:261-282`) calls
`search_backend.autocomplete()` whenever `get_autocomplete_search_fields()` is
non-empty, else degrades to whole-word `search()` + a `RuntimeWarning`. Verified
on-branch that `Topic.get_autocomplete_search_fields()` had become `[]`, so a
moderator typing "mons" no longer matched "Monstera repotting" in the CMS.
Nothing caught it: `pytest.ini` silences only Deprecation warnings, and
`test_admin.py` covered listing search for Post and ForumProfile but not Topic.
Notably the `wagtail-reviewer` agent had independently asserted "confirmed by
grep, no code calls `backend.autocomplete()`" — the same blind spot. Field
restored, comment rewritten to name Wagtail as the reader, and pinned by
`test_topic_listing_search_matches_a_title_prefix` (a PREFIX query, since only
the autocomplete path resolves one). Mutation-verified: removing the field again
gives `13 passed, 1 failed`; restored with `git checkout --` per
`docs/rules/testing.md`.

**#2 medium — dishonest Load More count under a tag filter.** The "N remaining"
label subtracted the rendered rows from `category.thread_count`, the board's
*unfiltered* total: on a 400-thread board with 25 tagged, `?tag=` showed
"380 remaining" for a 25-result set — precisely the fake-count class the comment
directly above it says audit M30 fixed. Count suppressed while a tag is active;
both branches now pinned.

**#3 low — unguarded nested-image hoist.** The blockquote image hoist read
`data-image-id` without the truthiness guard the top-level branch has, so
`<img data-image-id="">` produced `value: 0` and a non-numeric one `NaN` →
`null`. Both fail `validate_forum_body`, so ONE unusable image would 400 the
entire save instead of being dropped.

Also verified-clean by that pass (recorded so it isn't re-litigated): the
idempotency fingerprint DOES include `tags` (so a tags-only retry under a reused
key correctly 422s); the two topic serializers have no other consumers, so
`get_tags` introduces no un-prefetched N+1; and the tag-creation race in
`_create_topic` is a non-issue — `get_or_create` absorbs the name-unique
`IntegrityError` in its own savepoint, so it never reaches the slug-retry
`except`.

Final: `595 passed` backend, `734 passed` web.

### 2026-07-23 - Created by splitting todo 256

- Todo 256 (Q&A/discovery/SEO epic) re-scoped by user to H8 (search) + H9 (SEO)
  only; H6 (solved marking) had already moved to todo 273 (Wave 2). These four
  findings (M1/M5/M11/L8) split here. M11 reduced to copy-link-only because Wave 1
  (#473) shipped the deep-link chase.
