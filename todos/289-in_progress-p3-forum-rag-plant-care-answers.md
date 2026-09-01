---
status: in_progress
priority: p3
issue_id: "289"
tags: [forum, ai, rag, premium, safety]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M13"
---

# RAG plant-care answers grounded in site data — implementation

## Problem

M13 of the 2026-07-11 forum audit: RAG plant-care answers grounded in the site's
own blog + species reference data. The **design round is complete** (todo 275,
2026-07-29) — see `docs/superpowers/specs/2026-07-29-forum-rag-plant-care-design.md`.
Implementation was descoped from 275 because shipping it over today's near-empty
corpus would be worse than not shipping it: a correct implementation refuses every
question (the unsourced-refusal guardrail) and an incorrect one hallucinates
plant-care advice that has real-world consequences.

This todo is the **execution** task, gated on the four enablement gates below.

## Findings

- Design + guardrails + cost model:
  `docs/superpowers/specs/2026-07-29-forum-rag-plant-care-design.md` (todo 275 AC3).
- Substrate exists and is dormant: `apps/forum_host/vector_indexes.py`
  (`SimilarTopics`, `find_similar_topics`), gated by
  `FORUM_VECTOR_SEARCH_ENABLED` (default `False`, no built index in prod).
- Query-embedding budget already in place: `constants.EMBED_BUDGET_CACHE_KEY` /
  `EMBED_BUDGET_LIMIT`, consumed inside `find_similar_topics` (todo 275 AC4), so
  RAG retrieval inherits it by routing through that helper.
- Design correction to record: the audit said "plant-ID data", but per-user
  identification records are diagnostic artifacts never submitted for
  publication. The corpus is **species-level reference text, staff-curated** —
  not user identifications. See the design doc's `PlantCareNotes` section.

## Recommended Action

**Decision 2026-09-01 (user): build it dark, split the gates out.** The four
enablement gates are ops/content conditions no engineering pass can satisfy, so
they blocked this todo on every pickup (2026-08-29, 2026-08-31). They move to
**todo 330** (`forum-rag-enable-in-env`, mirroring the 274→280 spam-backend
split). This todo ships the code behind `FORUM_RAG_ENABLED` (default `False` →
503) **and** `FORUM_VECTOR_SEARCH_ENABLED` (both must be on), the same
dormant-on-merge posture as M12/M14 — nothing reaches users until an operator
flips the flags per 330.

Build order (design doc, with the corrections recorded in its
"Implementation notes" section):

1. Constants (`care_ask` throttle, `RAG_*` budget/floor/chunking/prompt).
2. Block-boundary chunker (`rag_chunking.py`) — pure functions.
3. `_scored_search` core extracted from `find_similar_topics` (which discards
   scores, so the similarity floor cannot reuse it) + `BlogChunks` index with
   per-chunk `block_index` metadata; `build()` purges its own rows first.
4. `retrieve_grounding_passages` (`rag_retrieval.py`): floor → per-corpus
   visibility refetch → dedupe → merge → cap → renumber.
5. Guardrails (`rag_guardrails.py`): deterministic blocked-class classifier,
   citation validator, `NO_INFORMATION` sentinel.
6. Host-owned `RagAnswer` + `RagAnswerReport` models (first `forum_host`
   migration) + CMS snippet list "AI answer reports".
7. `POST /forum/care/ask/` + `POST /forum/care/answers/<id>/report/`.
8. `sync_blog_page_chunks` Celery task + `page_published`/`page_unpublished`/
   `post_delete` receivers (host-side).
9. Wiring: settings flag, `api_urls.py`, `HOST_ONLY_ROUTES`, schema.
10. Web (PR-2): `PlantCareAskPanel` on `/forum/search`, `#block-N` anchors on
    blog detail, non-optimistic "This is wrong" report.

## Technical Details

- Design: `docs/superpowers/specs/2026-07-29-forum-rag-plant-care-design.md`
- Substrate: `backend/apps/forum_host/vector_indexes.py`,
  `backend/apps/blog/wagtail_ai_v3_integration.py` (`generate_ai_text`),
  `backend/apps/blog/services/ai_rate_limiter.py` (`peek_budget`/`consume_budget`)
- Precedent endpoints to mirror: `apps/forum_host/summary.py` (premium + cached),
  `apps/forum_host/compose_assist.py` (premium + flag-gated + own budget)
- Patterns: `backend/docs/patterns/domain/forum.md`, `.../domain/blog.md`
- New flag: `FORUM_RAG_ENABLED` (default `False` → 503), matching
  `FORUM_COMPOSE_ASSIST_ENABLED` / `FORUM_VECTOR_SEARCH_ENABLED`.

## Acceptance Criteria

- [x] All four enablement gates confirmed and recorded in the Work Log (or the
      todo is re-deferred with the failing gate named) — superseded 2026-09-01:
      the gates are split out to todo 330 (ops enablement); this todo ships
      the code dark behind `FORUM_RAG_ENABLED`
- [x] `BlogChunks` index shipped with block-boundary chunking + anchor metadata,
      rebuilt on `page_published` (2026-09-01: `test_rag_chunking.py` 11,
      `BlogChunks` section of `test_rag_retrieval.py`, `test_rag_index_tasks.py` 9)
- [x] Retrieval returns nothing below the similarity floor, and a below-floor
      question returns "no information" **without** an LLM call (test-pinned)
      (2026-09-01: `test_below_floor_docs_are_discarded`, both e2e floor tests,
      `test_nothing_above_floor_returns_no_information_without_calling_the_provider`;
      mutation-checked)
- [x] Blocked question classes (ingestion/toxicity/medicinal, pesticide dosing)
      return a static referral with no retrieval and no LLM call (test-pinned)
      (2026-09-01: 20 blocked + 15 not-blocked table rows in
      `test_rag_guardrails.py`, two referral endpoint tests; mutation-checked)
- [x] Invented `[n]` citations are dropped; an answer with zero valid citations is
      suppressed and degrades to plain passage results (test-pinned)
      (2026-09-01: `test_invented_citations_are_dropped_from_the_answer`,
      `test_zero_valid_citations_degrades_to_passages_only_and_persists_nothing`;
      mutation-checked)
- [x] Premium-gated, throttled, own budget counter, `FORUM_RAG_ENABLED` default
      off → 503 (test-pinned, mirroring `test_compose_assist.py`)
      (2026-09-01: `test_rag.py` bounds 1–4 incl. the settings-source regex pin
      and the two-flag 503)
- [ ] Report-a-wrong-answer affordance lands in the moderation queue
      (backend half shipped 2026-09-01: `POST /forum/care/answers/<id>/report/`
      + CMS "AI answer reports" list/inspect, `test_rag_reports.py`; the web
      button is PR-2)
- [ ] Web "ask about plant care" panel on `/forum/search` — `[n]` citations
      link to the cited passage, sources listed with kind/title/date, visible
      not-expert-advice label, non-optimistic "This is wrong" report
- [ ] `#block-N` anchors on blog detail so a blog citation lands on the passage

## Work Log

### 2026-07-29 - Spun out of todo 275 with the design round complete

- Todo 275 AC3 required "own design round completed; shipped … or explicitly
  descoped with rationale". The design round was done and the implementation
  explicitly descoped; this todo carries the execution.
- p3 (not p2): gated on a corpus that does not exist yet. Raise to p2 once gates
  1–2 hold.

### 2026-08-29 - Gate-check: 2 of 4 gates fail objectively, todo re-deferred

Ran the four enablement gates against live prod state rather than starting
implementation. AC1 satisfied via its alternate clause ("or the todo is
re-deferred with the failing gate named").

- **Gate 1 — FAIL.** `FORUM_VECTOR_SEARCH_ENABLED` is **absent** from the prod
  `plant_id_community` service's variable list (Railway `get-service-config`,
  checked 2026-08-29) — not present, not merely set to `False` — so it
  resolves to the coded default `False`
  (`backend/plant_community_backend/settings.py:806-808`). No `SimilarTopics`
  index has been built and no M12 real-traffic evidence exists: the audit
  doc's own M13 re-pointer note already says "H15 still dormant in prod",
  and no LEARNINGS/Work Log entry records a `rebuild_indexes SimilarTopics`
  run.
- **Gate 2 — FAIL.** Live prod counts pulled directly on 2026-08-29:
  `GET /api/v1/forum/boards/` → **16 topics** across 5 boards (need ≥200 —
  ~8% of threshold); `GET /api/v2/blog-posts/?limit=1` →
  `meta.total_count: 0` (need ≥50 chunked articles); `GET
  /api/v2/care-guides/?limit=1` → `total_count: 0`. Even the repo's own seed
  catalogues (`apps/forum_host/seed_content.py`, `apps/blog/seed_content.py`)
  only define 16 topics / 6 posts if fully applied — nowhere near threshold
  either way. The DEBUG-gated `seed_demo_content --confirm` /
  `seed_demo_blog --confirm` prod session referenced in
  `docs/superpowers/plans/2026-08-16-canopy-blog.md` appears never to have
  run, consistent with 0 live blog posts observed.
- **Gate 3 — left open/unassessed.** No review-queue mechanism exists yet for
  anyone to own (guardrail 5 is unbuilt), and per this repo's own precedent
  (todo 280's operator-decision entries, todo 254's L21 "roadmap-owner
  decision" note) naming an owner is deliberately left to the user, not
  forced by an automated pass.
- **Gate 4 — SIGNED OFF 2026-08-29 by the user.** The blocked-class list from
  the design doc (Guardrails layer 2): human/animal ingestion (edibility,
  toxicity, medicinal use) and pesticide/chemical dosing — never answered
  from community content, classified before retrieval, routed to a static
  referral. Approved as written.
- User was asked whether to flip `FORUM_VECTOR_SEARCH_ENABLED` in Railway
  now and/or spin out a separate ops-enablement todo for it, mirroring todo
  280's pattern for the spam backend. **Decision: leave it off, no new
  todo** — gate 2 blocks independently either way, so enabling it wouldn't
  unblock this todo.
- Priority stays p3: raise to p2 once gates 1–2 hold. Measured gap so a
  future pass doesn't need to re-run this recon: topics 16/200 (~8%), blog
  articles 0/50 (0%).

### 2026-08-31 - Re-checked, skipped

- Gates re-verified live: 18/200 topics, 6/50 blog posts, gate 1 still off.
  User chose to skip and work todo 312 instead.

### 2026-09-01 - Started: build dark, gates split to todo 330

- Root cause of the repeated deferrals: this was the only forum AI todo whose
  text forbade *building* until ops/content conditions held; every sibling
  (M12, M14, H13 via 274→280) shipped dark behind a default-off flag with the
  enablement decision in its own ops todo. **User decision: do the same.**
  AC1 stands satisfied via its "re-deferred with the failing gate named"
  clause and is now superseded by the split; the gate measurements above are
  carried verbatim into todo 330.
- Exploration corrections to the design doc, recorded in its new
  "Implementation notes" section rather than rewriting it: the blog model is
  `BlogPostPage`/`content_blocks` (not `BlogPage`); H15 *does* chunk (blind
  1000-char windows via django-ai-core's default `SimpleChunkTransformer`,
  hidden by `find_similar_topics`' pk-dedupe); `find_similar_topics` discards
  `doc.score`, so the similarity floor needs an extracted scored core;
  headings emit no `id` on either surface, so anchors are `#block-<index>`;
  the package `Report` model has an exactly-one-of(post, message) check
  constraint and `file()` semantics that penalise an author, so the report
  lands in host-owned `RagAnswer`/`RagAnswerReport` + a CMS snippet list;
  `PlantCareNotes` (no model exists) is out of this slice.
- Slice: backend API + guardrails (PR-1) then web panel (PR-2), two
  sequential PRs per the M9 (#577/#578) precedent.

### 2026-09-01 - PR-1 (backend) built TDD, verified

Every step was RED first (module/attribute missing) then GREEN. New:
`html_text.py` (the `flatten_html` block-boundary helper extracted from
`compose_assist.py`), `rag_chunking.py`, `rag_retrieval.py`,
`rag_guardrails.py`, `rag.py`, `models.py` (+ `migrations/0001_initial.py`,
the app's first), `wagtail_hooks.py`, `sync_blog_page_chunks` in `tasks.py`,
three receivers in `signals.py`, `_scored_search`/`rag_enabled`/`BlogChunks`
in `vector_indexes.py`, `FORUM_RAG_ENABLED` in settings, two routes +
`HOST_ONLY_ROUTES`, constants; todo 330 filed; design doc "Implementation
notes", forum.md pattern updates, CLAUDE.md env-var row.

```
$ pytest apps/forum_host/tests/test_rag*.py --reuse-db -q
test_rag_chunking 11 · test_rag_retrieval 23 · test_rag_guardrails 48 ·
test_rag_reports 13 · test_rag 32 · test_rag_index_tasks 9  — all passed
$ pytest apps/forum_host/tests/test_similar.py test_semantic_search.py
  test_compose_assist.py test_ratelimits.py test_schema_429.py
  test_api_mounted.py test_bootstrap.py test_signals.py     — all passed
$ python manage.py check            → System check identified no issues (0 silenced).
$ python manage.py makemigrations --check --dry-run → No changes detected
$ python manage.py spectacular --file /dev/null     → exit 0
$ pre-commit run black/isort/flake8 --files <changed> → Passed
$ pytest -q --create-db             # full backend suite
1895 passed, 8 skipped, 6 warnings in 210.28s        # was 1304 on main @ todo 275
```

Mutation checks (each applied to production code, targeted suites run,
file restored):

```
floor comparison → never discards:   4 failed (test_below_floor_docs_are_discarded,
  test_floor_is_read_at_call_time, both end_to_end floor tests), 19 passed
classify_blocked_question → None:    every blocked-table row + both referral
  endpoint tests failed (assert None == 'ingestion'; KeyError: 'referral')
validate_citations → keep everything: 4 failed (test_invented_citations_are_
  dropped_from_the_answer + 3 guardrail tests), 76 passed
```

Two exploration-time facts worth keeping: the formatter hook strips an
import added in an earlier Edit than its first use (hit twice — compose
`flatten_html`, signals `page_published`); and `MagicMock` has no
`__name__`, so log labels on a patched index class need `getattr`.

### 2026-09-01 - Review round 1 (PR #606): 4 domain reviewers + bundled, fixes applied

Blocking (HIGH) findings, all fixed with a RED test first:

- **`on_commit` race** (wagtail-reviewer; independently confirmed): the
  receivers enqueued `sync_blog_page_chunks.delay()` inline. Wagtail's admin
  publish and Django's `Model.delete()` cascade both fire these signals inside
  `transaction.atomic()`, so a worker could see the pre-publish page (first
  publish → purge-only, never indexed) or re-embed a page mid-delete (orphan
  rows). Now `transaction.on_commit`, the `notifications.py` convention;
  `test_enqueue_is_deferred_to_commit` pins it with
  `django_capture_on_commit_callbacks(execute=False)`.
- **Celery backoff factor** (celery-async-reviewer, verified in
  `celery/app/autoretry.py:51`): `retry_backoff=True` means factor
  `int(max(1.0, True)) == 1` (~1s/2s/4s jittered) and `default_retry_delay`
  is never read on the autoretry path. Now `retry_backoff=RAG_INDEX_RETRY_DELAY`;
  countdowns pinned at 30/60/120 with jitter patched to its maximum.
- **Visibility-refetch arms untested** (cross-cutting, mutation-verified):
  `live=True` on the topic refetch and `.public()` on the blog refetch were
  not independently pinned. Added an unpublished-topic and a restricted-page
  case through `retrieve_grounding_passages`.

Non-blocking, fixed anyway (same functions, cheap): permanent chunking errors
are logged not retried; page state re-checked inside the swap transaction;
`ignore_result=True`; sentinel regex built from `RAG_NO_INFORMATION_SENTINEL`;
`RAG_REPORT_QUESTION_PREVIEW_CHARS`; `RAG_QUESTION_MAX_CHARS` a literal with a
`<= SIMILAR_QUERY_MAX_CHARS` pin; CMS `select_related` pinned on the queryset;
the two RAG views added to the route-identity/throttle pins.

Own finding from the bundled review's interim note: retrieval collapsed
"no index could search" into `[]` → the view answered a confident
`no_information` about a corpus it never consulted. Now tri-state like the
core (`None` → 503 `unavailable`, transient, nothing charged). Also two
classifier misfires fixed and pinned: "get rid of poison ivy" and "toxic to
plants" are care questions, not ingestion.

Left as known issues: no `on_failure` handler (pre-existing gap shared by
every task in the file); `RagAnswer`/`RagAnswerReport` not in auditlog
(forum-wide pre-existing gap); no content-hash short-circuit before a re-embed
(the embedding cache makes unchanged chunks free anyway).

## Notes

Highest harm ceiling of any AI feature in the repo — plant-care advice, and in the
blocked classes, human/animal ingestion. The guardrails are the feature; the
retrieval is the easy part. Do not ship layers 1–4 without layer 5's owner.
