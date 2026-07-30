# Design — RAG plant-care answers grounded in site data (todo 275 / M13)

Todo `todos/275-*-forum-ai-round2.md`. Source finding **M13** of the 2026-07-11
forum-modernization audit ("RAG plant-care answers grounded in the site's
plant-ID + blog data — highest differentiation, long-horizon big bet; strict
superset of H15 infra; needs citation UX + hallucination guardrails (plant-care
advice has real-world consequences). Do not start before H15").

This is the **design round** the todo's AC3 asked for. Its conclusion is a
deliberate **descope of implementation** with the preconditions written down as
objective, checkable gates — see [Disposition](#disposition). The design is
recorded now, while the H15 substrate is fresh, so the eventual build is an
execution task rather than a fresh research round.

## Problem

Plant-care questions are the forum's dominant intent, and the site already holds
three bodies of relevant text nobody can search across: blog articles
(`apps/blog`, Wagtail pages), forum threads (`wagtail_forum`, already vectorized
by H15), and plant-identification results (`apps/plant_identification`). A member
asking "why are my tomato leaves curling" gets keyword search over one of those
three at a time.

RAG's differentiation is *grounding*: an answer assembled from, and citing, this
site's own content — not a general model's parametric recall, which any chatbot
already provides for free.

## Substrate this builds on (already shipped, todo 255 slice 4 / H15)

- `django_ai_core.contrib.index` active; `CREATE EXTENSION vector` migrated.
- `apps/forum_host/vector_indexes.py` — `SimilarTopics(VectorIndex)` over live,
  publicly-visible topics: `PgVectorProvider` storage, `CachedEmbeddingTransformer`
  over OpenAI `text-embedding-3-small`, `ModelSource` with a `get_content`
  override for StreamField plaintext.
- `find_similar_topics()` — the single embedding entry point, carrying the
  `FORUM_VECTOR_SEARCH_ENABLED` gate, the board-visibility refetch, the
  never-raises contract, and (todo 275 / AC4) the dedicated
  `EMBED_BUDGET_CACHE_KEY` query-embedding budget.
- `apps/blog/wagtail_ai_v3_integration.generate_ai_text(prompt, *, alias, timeout)`
  — the completion substrate, with a per-request provider deadline.
- `AIRateLimiter.peek_budget` / `consume_budget` — per-feature cost counters with
  the peek-then-consume posture (never charge a call that did not reach the
  provider).

M13 is a strict superset: same storage, same embedder, plus two new corpora,
chunking, a retrieval merge step, a grounded-generation step, and citation UX.

## Architecture

### 1. Corpora and indexes

Three registered indexes rather than one, so each source keeps its own content
extraction, visibility predicate and rebuild cadence:

| Index | Source | Visibility predicate |
|-------|--------|----------------------|
| `SimilarTopics` (exists) | live topics + opening post | `board__in=_visible_boards()` |
| `BlogChunks` (new) | live, public `BlogPage` bodies, chunked | `.live().public()` |
| `PlantCareNotes` (new) | curated plant-care text keyed to a species | staff-curated only |

**`PlantCareNotes` is deliberately NOT "plant-ID results".** The audit phrased
M13's corpus as "plant-ID + blog data", but identification records are per-user
diagnostic artifacts (uploaded photos, health assessments, and in the diagnosis
path user-supplied symptom text). Embedding them into a corpus that answers other
members' questions crosses a privacy boundary that no forum-visibility predicate
covers — the data was never submitted for publication. What *is* safe and useful
is the species-level reference text the ID providers return, promoted into a
curated, staff-reviewed snippet per species. This is a **correction to the
audit's framing**, not an omission; treat "plant-ID data" as "species reference
text, not user identifications".

### 2. Chunking (new; H15 does not chunk)

`SimilarTopics` embeds a whole topic because a topic is already short and its
citation target is the topic itself. Blog articles are long, so a whole-article
embedding both dilutes the vector and gives a useless citation ("somewhere in
this 2000-word article").

- Chunk on StreamField block boundaries, packing to ~1000 characters with a
  ~150-character overlap, never splitting mid-block.
- Each chunk stores `{page_id, block_index, heading_path, url_with_anchor}` in
  index metadata — the anchor is what makes a citation land on the passage.
- Re-chunk on page publish (`page_published` signal), not on a cron:
  `CachedEmbeddingTransformer` already makes unchanged chunks free.

### 3. Retrieval

1. Embed the question once (through a `find_similar_*`-style helper, so the AC4
   embedding budget covers it — never call `search_documents` directly).
2. Query all three indexes, overfetch (`SIMILAR_OVERFETCH` precedent).
3. **Similarity floor.** Discard any chunk whose score is below a tuned floor.
   This is the single most important knob in the design — see
   [Guardrails](#guardrails).
4. Refetch through each corpus's visibility predicate (never trust the index: a
   page may have been unpublished or a board restricted after indexing).
5. Merge, dedupe by source object, cap at N chunks / M total characters.

### 4. Generation

One `generate_ai_text` call with a bounded prompt: the question, the numbered
retrieved passages, and instructions to answer **only** from those passages,
citing each claim as `[n]`, and to state that the site has no information rather
than answering unsourced. The question and the passages are both framed as
untrusted data (the established `SPAM_LLM_PROMPT_TEMPLATE` /
`SUMMARY_PROMPT_TEMPLATE` / `COMPOSE_PROMPT_TEMPLATE` posture) — passages are
user-authored forum text and can contain injection attempts.

### 5. Surface

An explicit, opt-in "ask about plant care" panel that returns an answer *to the
asker*. **Not** an AI reply auto-posted into threads: a wrong auto-answer in a
human thread is both a community-health decision nobody has made and the
worst-case blast radius for a wrong plant-care claim. Revisit only after the
answer quality is measured.

## Guardrails

Plant-care advice can cause real harm — a wrong watering claim kills a plant, a
wrong edibility or toxicity claim harms a person or a pet. Five layers, in
descending importance:

1. **Refuse when unsourced (the primary guardrail).** If retrieval returns
   nothing above the similarity floor, return "no information on this" and do not
   call the LLM at all. Ungrounded generation is the failure mode RAG exists to
   prevent; an empty corpus must produce silence, not fluent invention.
2. **Hard-blocked question classes, answered by nobody.** Human or animal
   ingestion (edibility, toxicity, medicinal use) and pesticide/chemical dosing
   are never answered from community content — they route to a static referral
   (poison control / a professional). Classified before retrieval, so a blocked
   question costs nothing. This is a product rule, not a model instruction: a
   prompt-level "don't answer toxicity questions" is not a control.
3. **Citation validation, post-generation.** Parse `[n]` markers; drop any that
   does not resolve to a retrieved passage (a model can invent indices). If zero
   valid citations survive, suppress the answer and fall back to the retrieved
   passages as plain search results — a citation-free answer is exactly the
   ungrounded output this feature must not emit.
4. **Provenance-forward UX.** Every claim's `[n]` links to the cited passage;
   the answer is visibly labelled as assembled from community content and not
   expert advice; sources are listed with titles and dates (a 2019 thread and a
   staff-reviewed note should not look equally authoritative).
5. **Reporting affordance + review loop.** A one-click "this is wrong" on every
   answer, landing in the existing moderation queue. Without a human who reads
   these, layers 1–4 are unfalsifiable in production.

## Cost model

| Component | Per question | Bound |
|-----------|--------------|-------|
| Question embedding | 1 embedding (~125 tok) | existing `EMBED_BUDGET_LIMIT` (AC4) |
| Generation | 1 completion, ~2–4k input tok | new `RAG_BUDGET_*` counter, own key |
| Index build | 1 embedding per changed chunk | content-hash cache; publish-triggered |

Premium-gated (`IsPremiumUser`), per-user throttled, forum-wide budget counter on
its own cache key — the pattern established by `SPAM_LLM_BUDGET_CACHE_KEY`,
`COMPOSE_BUDGET_CACHE_KEY` and `EMBED_BUDGET_CACHE_KEY`, and the reason those
counters are separate: non-commensurable unit costs and independent degrade
postures. Ships behind `FORUM_RAG_ENABLED` (default off → 503), like every other
AI feature in this repo.

## Disposition

**Implementation is descoped from todo 275.** Not because it is hard, but because
shipping it now would be actively worse than not shipping it:

1. **The corpus is empty.** The forum is deployed with near-zero content and the
   blog corpus is unchunked. RAG's entire value proposition is grounding in site
   data; over an empty corpus a correct implementation refuses every question
   (guardrail 1) and an incorrect one hallucinates. There is nothing to ground
   *in* yet, so no amount of engineering produces a good answer today.
2. **Its own prerequisite is not enabled.** M13 is a strict superset of H15, and
   H15 is dormant in prod: `FORUM_VECTOR_SEARCH_ENABLED=False` with no built
   index. Building a superset of an unexercised substrate means debugging both at
   once, in the feature with the highest harm ceiling.
3. **Guardrail 5 has no owner.** Layers 1–4 are code and can be written in a few
   days. The review loop is a human commitment — someone must read wrong-answer
   reports and act. Shipping 1–4 without 5 means no one would find out the
   guardrails had failed.

### Enablement gates (all four, objectively checkable)

- [ ] `FORUM_VECTOR_SEARCH_ENABLED=True` in prod with a built `SimilarTopics`
      index, and the M12 semantic-search section exercised by real traffic.
- [ ] A corpus worth grounding in: ≥200 live topics **or** ≥50 chunked blog
      articles covering the common care questions.
- [ ] A named owner for the wrong-answer review queue (guardrail 5).
- [ ] The blocked-class list (guardrail 2) reviewed and signed off by a human,
      since it is the layer standing between this feature and a real-harm answer.

Tracked for implementation as **todo 289**; the audit's `#M13` finding stays
open and re-pointed there (per CLAUDE.md: a finding that *moved* is re-pointed,
never checked off — `- [x]` means shipped).
