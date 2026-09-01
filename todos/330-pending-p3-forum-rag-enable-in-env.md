---
status: pending
priority: p3
issue_id: "330"
tags: [forum, ai, rag, premium, safety, ops, deploy]
dependencies: ["289"]
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M13"
---

# Enable RAG plant-care answers in a target environment

Split out of todo 289 on 2026-09-01. **289 is the engineering work** — the
feature ships dark behind `FORUM_RAG_ENABLED` (default `False` → 503) — and
this todo is the remaining *operator* action: a production config change with
real LLM spend, a content prerequisite, and a human commitment attached,
deliberately not performed by an automated run. Mirrors the 274→280 split for
the LLM spam backend.

## Why this is separate

289's original text forbade *starting* until four enablement gates held. The
gates are ops/content conditions no engineering pass can satisfy, so every
pickup (2026-08-29, 2026-08-31) re-deferred it. Every sibling forum AI feature
(M12 semantic search, M14 compose assist, H13 spam via 274→280) shipped dark
with the operator decision in its own todo; 289 now does the same. Only the
operator can grow the corpus, name the review-queue owner, and accept the
spend.

## Prerequisites (satisfied by todo 289)

- `POST /api/v1/forum/care/ask/` + `POST /api/v1/forum/care/answers/<id>/report/`
  mounted, premium-gated, throttled (`care_ask` 10/h per user), own budget
  (`RAG_BUDGET_LIMIT` 100/h forum-wide, peek-then-consume).
- Two-flag gate: `FORUM_RAG_ENABLED` **and** `FORUM_VECTOR_SEARCH_ENABLED`.
- `BlogChunks` index (block-boundary chunks, `#block-N` anchors) + per-page
  `sync_blog_page_chunks` on publish/unpublish/delete; `rebuild_indexes`
  purges its own rows before rebuilding.
- Guardrails test-pinned: blocked classes → static referral with no retrieval
  and no LLM call; nothing above the similarity floor → `no_information` with
  no LLM call; invented `[n]` dropped; zero valid citations → `passages_only`.
- The wrong-answer review queue exists: CMS `/cms/` → "AI answer reports"
  (list + inspect view showing the answer and its sources).

## Enablement gates (from the design doc §Disposition; measured state carried from 289)

Measured against live prod on 2026-08-29 (todo 289 Work Log); re-measure
before flipping anything:

1. **Gate 1 — FAIL as of 2026-08-29.** `FORUM_VECTOR_SEARCH_ENABLED` absent
   from the prod `plant_id_community` Railway service (resolves to `False`);
   no `SimilarTopics` index ever built; no M12 real-traffic evidence.
2. **Gate 2 — FAIL as of 2026-08-29.** Corpus: 16/200 live topics (~8%),
   0/50 blog articles (`/api/v2/blog-posts/` total 0; 6 seeded on 2026-08-31),
   0 care guides. Threshold: ≥200 live topics **or** ≥50 blog articles covering
   the common care questions. **This is a content problem** — do not
   AI-generate articles to ground a RAG in (circular; hallucinated "site
   data").
3. **Gate 3 — OPEN.** A named owner for the wrong-answer review queue. Without
   a human reading "AI answer reports", guardrails 1–4 are unfalsifiable in
   production. Deliberately left to the user, never forced by an automated
   pass.
4. **Gate 4 — SIGNED OFF 2026-08-29 by the user.** Blocked-class list
   (ingestion/toxicity/medicinal use; pesticide/chemical dosing) approved as
   written; implemented as the deterministic classifier in
   `apps/forum_host/rag_guardrails.py`.

## Recommended Action

In this order — each step is a precondition of the next:

1. Confirm `OPENAI_API_KEY` is set and funded on the target service (it is
   on prod as of 2026-08-30, per todo 280).
2. Set `FORUM_VECTOR_SEARCH_ENABLED=True` (Railway dashboard — the CLI/MCP
   variable writes have misreported success before, see
   `project_cloudflare_deploy_state`).
3. Build BOTH indexes by name — a bare `rebuild_indexes` now builds both, but
   name them so the log is unambiguous:
   `python manage.py rebuild_indexes SimilarTopics BlogChunks`
   (needs the service's `OPENAI_API_KEY`; embeds every live topic + article
   once, cached by content hash thereafter).
4. Name the review-queue owner (gate 3) and record it here: who reads
   `/cms/` → "AI answer reports", how often, and what "actioned" means.
5. Set `FORUM_RAG_ENABLED=True`. Verify: `POST /api/v1/forum/care/ask/` as a
   premium user returns a `status` envelope, not 503; as a non-premium user
   returns 403.
6. Tune `RAG_SIMILARITY_FLOOR` (`apps/forum_host/constants.py`, default 0.35
   — a starting point, NOT a measurement) from the `[RAG] retrieval top
   scores …` log lines over the first real questions: too many
   `no_information` for questions the corpus clearly covers → lower it; any
   `answered` grounded in an unrelated passage → raise it.
7. Rollback = unset `FORUM_RAG_ENABLED` (the routes 503 `code: disabled`
   again; the report endpoint keeps working so existing answers stay
   reportable). Unsetting `FORUM_VECTOR_SEARCH_ENABLED` also disables M12/H15.

## Technical Details

- Flags: `backend/plant_community_backend/settings.py` (`FORUM_RAG_ENABLED`,
  `FORUM_VECTOR_SEARCH_ENABLED`); gate helper `vector_indexes.rag_enabled()`.
- Tunables: `apps/forum_host/constants.py` — `RAG_SIMILARITY_FLOOR`,
  `RAG_BUDGET_LIMIT`, `DEFAULT_FORUM_RATELIMITS["care_ask"]`,
  `RAG_MAX_PASSAGES` / `RAG_MAX_CONTEXT_CHARS`.
- Design + implementation notes:
  `docs/superpowers/specs/2026-07-29-forum-rag-plant-care-design.md`.
- Pattern: `backend/docs/patterns/domain/forum.md` §"RAG guardrails are
  product rules, not prompt instructions".
- Known follow-ups not blocking enablement: `SimilarTopics` never purges
  stale chunk tails after a topic edit (same latent issue `BlogChunks.build()`
  now avoids); `RagAnswer` rows are retained indefinitely (a 90-day prune that
  keeps rows with open reports is a reasonable follow-up); the
  `PlantCareNotes` staff-curated corpus from the design doc has no model yet.

## Acceptance Criteria

- [ ] Gate 1 holds: `FORUM_VECTOR_SEARCH_ENABLED=True` on the target service
      with both indexes built (`rebuild_indexes SimilarTopics BlogChunks`
      output quoted)
- [ ] Gate 2 holds: corpus re-measured and at/above threshold (≥200 live
      topics or ≥50 blog articles), counts quoted
- [ ] Gate 3 holds: the review-queue owner is named in this file
- [ ] `FORUM_RAG_ENABLED=True` and the first real `answered` response observed
      (question class + cited sources quoted, no PII)
- [ ] `RAG_SIMILARITY_FLOOR` reviewed against real `[RAG]` top-score lines and
      either confirmed or changed via PR

## Work Log

### 2026-09-01 - Split out of todo 289 (decision: build dark)

- User decision: 289 builds the feature dark; the four gates move here. Gate
  measurements above are carried verbatim from 289's 2026-08-29 gate-check.
  Priority p3 like 289; raise once gates 1–2 are close.

## Notes

Highest harm ceiling of any AI feature in the repo. Do not flip step 5 before
step 4 — layers 1–4 of the guardrails are only falsifiable if someone reads
the reports.
