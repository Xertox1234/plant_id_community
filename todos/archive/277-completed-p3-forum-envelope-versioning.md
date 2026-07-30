---
status: completed
priority: p3
issue_id: "277"
tags: [forum, api, drf, openapi]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M40, L20"
---

# Forum: list-envelope normalization + versioning-rationale comment

## Problem

Split out of todo 258 (forum-api-contract-hardening) on 2026-07-24 — both findings
are in 258's Recommended Action but were **not** 258 acceptance criteria, and both
are breaking / broad enough to warrant their own change window.

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`.

- **M40** — The forum API ships four list-envelope shapes: cursor
  `{results,next,previous}` (topic/post/notification lists), flat `{results}`
  (`BoardListView`), search `{topics,posts,topics_has_more,posts_has_more,page}`
  (`SearchView`), and the sync custom shape (`SyncView`). **Partly stale as of
  2026-07-24**: PR #473 already added `reply_count`/`view_count`/`last_post_at`
  to the search *topic* item, so of the four originally-named dropped fields only
  `is_pinned` is still missing there. The genuinely-divergent remainder is the
  **search post item** — an entirely separate lightweight shape vs `PostSerializer`
  (`W/api/views.py` search builders + `W/api/serializers.py`). Normalizing is a
  BREAKING response change — coordinate the web mappers
  (`web/src/services/forumMappers.ts`) and document.
- **L20** — `versioning_class = None` appears on **17** views across
  `W/api/{views,notifications,subscriptions,user_search}.py`, with the opt-out
  rationale commented on exactly one (`BoardListView`). Factor the rationale to a
  shared base/mixin (or a single referenced comment) so it is stated once.

## Recommended Action

1. **M40**: decide the target — converge search/sync onto the cursor envelope
   where feasible, and enrich the search *post* item to the `PostSerializer` field
   set (or explicitly document the lightweight search shape as intentional).
   Breaking: update `web/src/services/forumMappers.ts` + a full-suite grep for the
   old keys, and document the contract. `versioning_class = None` today, so a
   documented break is cheap pre-deploy.
2. **L20**: introduce a shared `versioning_class = None` base/mixin carrying the
   rationale comment once; refactor the 17 views to inherit it (mechanical).

## Acceptance Criteria

- [x] Either a single documented list-envelope contract (search/sync converged
      onto cursor) OR the divergence explicitly documented as intentional; web
      mappers updated + full web/backend suites green
- [x] The versioning-opt-out rationale is stated once (shared base/mixin), not
      duplicated or absent across the 17 views

## Notes

p3. Deferred from 258 — see
`todos/archive/258-completed-p2-forum-api-contract-hardening.md`.

## Work Log

### 2026-07-30 - Started by completing-todos skill (run 2026-07-30-1815)

- Picked up by automated workflow.

### 2026-07-30 - Implementation

**M40 — documented divergence (branch chosen deliberately).**

Converging search/sync onto the cursor envelope is not possible without
information loss: search returns **two** independently-paged sections in one
response (a cursor envelope has one `results`), and sync returns tombstones plus
a client-persisted compound `(updated_at, id)` cursor (DRF's opaque cursor is
per-response, not resumable days later). Took the AC's documentation branch.

- New `## List envelopes` section in `backend/packages/wagtail_forum/README.md`
  (sibling of `## Error envelope`): a table of all four shapes with the reason
  each cannot be cursor, plus a subsection stating that search items are
  deliberately lighter than list items — the `plain_text_excerpt` post item
  exists so search never resolves every hit's StreamField body (the per-post
  image bulk-fetch), and neither section carries an `author`.
- One real gap closed rather than documented: **`is_pinned`** on the search topic
  item — the last of the four fields M40 named (PR #473 had already restored the
  other three). Justified by the consuming UI, not symmetry: `SearchPage.tsx`
  renders the same `ThreadCard` as the board list, whose 📌 badge could never
  fire. Free — the row is already loaded.
- Added it to `apps/forum_host/semantic_search.py::_serialize` too, whose
  docstring promises "the SAME shape as a `topics` search hit" — otherwise the
  fix would have created a fresh instance of the divergence it closes.
- Web: `is_pinned` on `BackendSearchTopic` + mapped in `mapSearchTopicToThread`;
  both search interfaces now carry a doc comment pointing at the README section
  (no shape change was needed on the documentation branch — the "web mappers
  updated" clause is satisfied by the additive field plus these pointers).
- Tightened `test_premium_semantic_hits_use_the_same_shape_as_fts_topic_hits`,
  which despite its name compared against a **hardcoded** key list and would have
  stayed green while the two shapes drifted. It now compares against a real FTS
  hit from the same response, and keeps the literal set as a second pin.

**L20 — one mixin, 20 views.**

- New `wagtail_forum/api/versioning.py::UnversionedForumAPIMixin` states the
  rationale once. Re-based the 17 package views; also folded in the **3 host AI
  views** (`summary.py`, `compose_assist.py`, `similar.py`) that carried their
  own duplicated one-line comment — leaving those would have made "stated once"
  false. `grep -rn versioning_class` over package + host now returns only
  `versioning.py`.

**The verification that actually mattered — and my first version of it was
wrong.** I originally claimed a dropped opt-out is invisible to *all* behavioural
tests, measured by dropping the mixin from `BoardListView` and seeing
`test_api_mounted.py` + `test_boards.py` stay green. The django-drf reviewer
refuted it, and re-measuring confirmed the reviewer: `test_boards.py` makes zero
API calls (an inert control), and the package's own API tests DO catch it —
their test urlconf resolves to namespace `wagtail_forum_api`, which is in no
`ALLOWED_VERSIONS`, so every package API request 404s with
`NotFound: Invalid version in URL path`.

The correct, narrower picture (both measured):

| Mount | Namespace | Opt-out dropped |
|---|---|---|
| package test urlconf | `wagtail_forum_api` | 404 — package API suite catches it |
| real host mount | `v1:wagtail_forum_api` (`v1` allowed) | 200 — nothing behavioural fails |

So the guard's real value is the **host-mounted surface** the package suite
cannot reach: the three host-only AI views and every throttled host subclass.
Measured by reordering `SimilarTopicsView`'s bases — its own 18 tests and all
251 package API tests stayed green; only the guard failed.

So AC2 is backed by `apps/forum_host/tests/test_forum_versioning_optout.py`: it
walks the **host** urlconf (seeing throttled subclasses and `SemanticSearchMixin`,
not just package classes) and asserts the mixin is present, **precedes `APIView`
in the MRO**, and is re-declared nowhere else. The MRO assertion is not
theoretical — DRF's `APIView` declares `versioning_class` in its own class body,
so `class X(APIView, UnversionedForumAPIMixin)` silently hands the host default
back. Confirmed by reordering `SimilarTopicsView`'s bases:

```
E  AssertionError: SimilarTopicsView lists the mixin after APIView — DRF's
   DEFAULT_VERSIONING_CLASS wins the MRO
```

### 2026-07-30 - Verification

```
$ pytest apps/forum_host packages/wagtail_forum -q --create-db
597 passed, 2 warnings in 40.13s

$ npm run type-check          # tsc --noEmit — clean
$ npm run lint                # ESLint: 0 errors, 1 warning (pre-existing, coverage artifact)
$ npx vitest --run            # PASS (734) FAIL (0)

$ python manage.py spectacular --file /dev/null
spectacular exit=0; forum schema output byte-identical to main

$ flake8 packages/wagtail_forum/wagtail_forum/api/ apps/forum_host/   # exit 0
$ python manage.py check      # System check identified no issues (0 silenced)
```

Additive-only response change, so no out-of-diff consumer breaks: a whole-repo
grep for search-payload keys found `web/src/services/forumService.ts` (updated)
and `plant_community_mobile/.../forum_topic.dart`, which already reads
`json['is_pinned'] as bool? ?? false`.

**Process note (cost me a rerun).** I used `git checkout <file>` to undo two
temporary falsifiability experiments. That discards *all* unstaged work in the
file, not just the experiment — it silently reverted the `views.py` and
`similar.py` halves of the refactor while the rest of the branch stayed intact.
The only reason it surfaced was that the drift guard failed in the full-suite
run (and passed in isolation, because it had been run before the revert). Undo a
scratch edit with a file copy, never `git checkout`, when the file has unstaged
work.

### 2026-07-30 - Code review (PR #513, 4 reviewers) — 5 findings, all addressed

No critical/high. Every finding was verified against the code before acting.

| # | Reviewer | Sev | Finding | Resolution |
|---|---|---|---|---|
| 1 | django-drf | medium | The "a dropped opt-out is invisible to behavioural tests" claim in `versioning.py` + the guard's docstring is **false** for package views — the package test urlconf resolves to `wagtail_forum_api`, no allowed version, so it 404s. My control (`test_boards.py`) makes zero API calls | **Reviewer was right.** Re-measured, corrected the claim in 5 places (`versioning.py`, guard docstring, `patterns/domain/forum.md`, `docs/rules/testing.md`, this log) to the per-mount split |
| 2 | cross-cutting | medium | `test_premium_semantic_hits_…` compared key SETS only; `_topic()` leaves `is_pinned=False`, so a hardcoded `"is_pinned": False` in `_serialize` passed everything — the same discipline I'd applied to the FTS twin | Pinned ON + `assert hit["is_pinned"] is True`; mutation-checked (hardcoded → 1 failed, clean → 12 passed) |
| 3 | wagtail | medium | README's `## Search backend` still claimed results are "capped at 50 with no pagination and no `has_more` flag" — contradicting the `## List envelopes` section this PR made authoritative | Replaced with the real contract, verified against `PAGE_SIZE`/`MAX_PAGE` |
| 4 | react-ts | medium | `is_pinned` mapper test asserted only the `true` case — a hardcoded `true` would pass | Added the `false` case; mutation-checked (1 failed / 15 passed) |
| 5 | react-ts | low | New docblock claimed the mappers never alias fields, but `mapTopicListItemToThread` aliases `last_post_at`→`created_at` | Scoped the claim to the two search mappers |

Acted on one **info** finding too (wagtail): nothing pinned the new envelope table
to real responses. Normally info goes unactioned, but that same review had just
found this exact README rotted (#3), so `tests/api/test_list_envelopes.py` now
asserts each of the four envelopes' top-level key set against a live response,
plus that the four are actually distinct. A deliberate, stated scope addition.

Findings 2 and 4 are the same defect — a non-discriminating assertion on a field
whose default equals the asserted value — caught independently in backend and web
by different reviewers, in a PR where I had already written the guard comment for
it in a third file. Worth remembering as a class, not three incidents.
