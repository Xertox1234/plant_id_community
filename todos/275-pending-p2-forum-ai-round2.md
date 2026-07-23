---
status: pending
priority: p2
issue_id: "275"
tags: [forum, ai, premium, wagtail-ai, rag]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M12, M13, M14"
---

# Forum AI features, round 2: semantic search upgrade, composer assist, RAG

## Problem

Todo 255 (forum AI & premium epic) shipped the H15 pgvector "similar topics"
infra: `django_ai_core.contrib.index` is now active (INSTALLED_APPS + the
`CREATE EXTENSION vector` migration), a `SimilarTopics` `VectorIndex` over forum
topics, an OpenAI embedder, and a `find_similar_topics()` helper — all behind
`FORUM_VECTOR_SEARCH_ENABLED`. Three findings from the 2026-07-11 audit were
bundled into 255 but fell OUTSIDE its acceptance criteria (M12/M14 deferred; M13
explicitly gated to stay unstarted until H15 landed). H15 has now landed, so all
three are unblocked.

## Findings (carried from 255)

- **M12 — Semantic search upgrade (premium):** a marginal add now that the H15
  infra exists. `SimilarTopics.search_documents()` is generic; blend semantic
  hits into the existing forum `SearchView` (already Postgres FTS with ranking,
  per H22) so the value-add is synonym/meaning matching. Premium-gated per audit.
- **M14 — AI-assisted composer (draft improvement):** wagtail-ai's editor
  machinery is admin-only, so only the backend `generate_ai_text` substrate
  applies → a bespoke host endpoint + a TipTap toolbar action in `web`. Least
  favorable cost profile (interactive, uncacheable) — throttle + gate.
- **M13 — RAG plant-care answers grounded in the site's plant-ID + blog data:**
  the long-horizon big bet; a strict superset of the H15 infra (which now
  exists). Needs citation UX + hallucination guardrails (plant-care advice has
  real-world consequences). Own design round; do it LAST.

## Recommended Action

1. **Before enabling any of these in prod:** land the todo-255 slice-4
   pre-enablement follow-up — a **dedicated embedding budget** (separate from the
   shared `ai_rate_limit:global` completion counter) so query embeddings can't
   run up unbounded cost. Applies to M12 and M13 too (both embed queries).
2. **M12** first (thinnest): reuse `find_similar_topics`/`search_documents`.
3. **M14** (bespoke endpoint + web TipTap action).
4. **M13** RAG last, with its own design round + guardrails.

## Acceptance Criteria

- [ ] M12 semantic search upgrade shipped (premium-gated) or descoped w/ rationale
- [ ] M14 composer-assist endpoint + web toolbar action, throttled + gated
- [ ] M13 RAG: own design round completed; shipped with citations + hallucination
      guardrails, or explicitly descoped with rationale
- [ ] Dedicated embedding budget in place before any of these is enabled in prod

## Notes

Spun out of todo 255 at its completion (2026-07-22): 255's AC covered H12–H15 +
L6/L7 + the M13-unstarted gate; M12/M13/M14 were bundled in `source_finding` but
not in 255's AC. The 2026-07-11 audit Finding Status re-points M12/M13/M14 here.
