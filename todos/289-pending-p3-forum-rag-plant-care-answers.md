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

- [ ] All four enablement gates confirmed and recorded in the Work Log (or the
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

## Notes

Highest harm ceiling of any AI feature in the repo — plant-care advice, and in the
blocked classes, human/animal ingestion. The guardrails are the feature; the
retrieval is the easy part. Do not ship layers 1–4 without layer 5's owner.
