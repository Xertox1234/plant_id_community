---
status: pending
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

Do **not** start until all four enablement gates hold (design doc §Disposition):

1. `FORUM_VECTOR_SEARCH_ENABLED=True` in prod with a built `SimilarTopics` index,
   and the M12 semantic-search section (todo 275) exercised by real traffic.
2. A corpus worth grounding in: ≥200 live topics **or** ≥50 chunked blog articles
   covering the common care questions.
3. A named owner for the wrong-answer review queue (guardrail 5) — without a
   human reading reports, guardrails 1–4 are unfalsifiable in production.
4. The blocked-class list (guardrail 2 — ingestion/toxicity/medicinal use,
   pesticide dosing) reviewed and signed off by a human.

Then build in the design doc's order: chunked `BlogChunks` index → retrieval
merge with a similarity floor → blocked-class classifier → grounded generation →
citation validation → provenance UX → report affordance.

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
      todo is re-deferred with the failing gate named)
- [ ] `BlogChunks` index shipped with block-boundary chunking + anchor metadata,
      rebuilt on `page_published`
- [ ] Retrieval returns nothing below the similarity floor, and a below-floor
      question returns "no information" **without** an LLM call (test-pinned)
- [ ] Blocked question classes (ingestion/toxicity/medicinal, pesticide dosing)
      return a static referral with no retrieval and no LLM call (test-pinned)
- [ ] Invented `[n]` citations are dropped; an answer with zero valid citations is
      suppressed and degrades to plain passage results (test-pinned)
- [ ] Premium-gated, throttled, own budget counter, `FORUM_RAG_ENABLED` default
      off → 503 (test-pinned, mirroring `test_compose_assist.py`)
- [ ] Report-a-wrong-answer affordance lands in the moderation queue

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

## Notes

Highest harm ceiling of any AI feature in the repo — plant-care advice, and in the
blocked classes, human/animal ingestion. The guardrails are the feature; the
retrieval is the easy part. Do not ship layers 1–4 without layer 5's owner.
