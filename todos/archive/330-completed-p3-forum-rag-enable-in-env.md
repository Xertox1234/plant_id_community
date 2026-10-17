---
status: completed
priority: p3
issue_id: "330"
tags: [forum, ai, rag, premium, safety, ops, deploy]
dependencies: ["289"]
source_review: "docs/audits/2026-07-11-forum-modernization-COMPLETED.md"
source_finding: "M13"
triage: blocked-prod
triaged: 2026-10-16
owner_decision: "Owner seeded 8 questions from a staff account on 2026-10-17; floor raised 0.35 -> 0.45 from the [RAG] lines; archive (2026-10-17)"
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
   the common care questions. **This is a content problem.** AI-generated
   articles ARE allowed (owner, 2026-09-24): an earlier "do not AI-generate"
   rule here was agent-written, not the owner's. The owner spot-checks each
   before it is published (todo 445).
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

- [x] Gate 1 holds: `FORUM_VECTOR_SEARCH_ENABLED=True` on the target service
      with both indexes built (`rebuild_indexes SimilarTopics BlogChunks`
      output quoted) (completed 2026-10-11: built 2026-09-25, BlogChunks rebuilt 2026-10-11, see the Work Log)
- [x] Gate 2 holds: corpus re-measured and at/above threshold (≥200 live
      topics or ≥50 blog articles), counts quoted (completed 2026-10-11: 59 live articles)
- [x] Gate 3 holds: the review-queue owner is named in this file (completed 2026-09-24: the owner, weekly)
- [x] `FORUM_RAG_ENABLED=True` and the first real `answered` response observed
      (question class + cited sources quoted, no PII) (completed 2026-10-17: a watering question cited the pothos care guide, see the Work Log)
- [x] `RAG_SIMILARITY_FLOOR` reviewed against real `[RAG]` top-score lines and
      either confirmed or changed via PR (completed 2026-10-17: raised 0.35 → 0.45 in this PR, see the Work Log)

## Work Log

### 2026-09-01 - Split out of todo 289 (decision: build dark)

- User decision: 289 builds the feature dark; the four gates move here. Gate
  measurements above are carried verbatim from 289's 2026-08-29 gate-check.
  Priority p3 like 289; raise once gates 1–2 are close.
- 289 shipped: backend PR #606 (merged 2026-09-01, squash b9a7617) and web
  PR #607. Both routes 503 `code: "disabled"` in prod until step 5 here. The
  audit doc this points at was renamed `…-COMPLETED.md` when #M13 closed.

### 2026-09-04 - Gates re-measured against prod (run 2026-09-04-0350)

User decision: leave pending until the corpus grows; no spend, no config
change. Measured today so the next pickup starts from current numbers:

| Gate | 2026-08-29 | 2026-09-04 | Verdict |
|------|-----------|-----------|---------|
| 1 — `FORUM_VECTOR_SEARCH_ENABLED` on the prod service | absent | absent (`FORUM_RAG_ENABLED` absent too; `OPENAI_API_KEY` present) | FAIL |
| 2 — live topics (threshold ≥200) | 16 | 18 (5 boards; `/api/v1/forum/boards/` topic_count sum) | FAIL |
| 2 — blog articles (threshold ≥50) | 0 | 6 (`/api/v2/blog-posts/` total) | FAIL |
| 3 — review-queue owner | open | open | OPEN |
| 4 — blocked-class list | signed off | signed off | PASS |

Source: Railway `list-variables` on `plant_id_community` (variable names
only) and the public API, both read-only. Re-file trigger unchanged: 200 live
topics **or** 50 articles, plus a named owner for `/cms/` → "AI answer
reports". AI-generated articles may fill the corpus, spot-checked by the owner (todo 445).

## Notes

Highest harm ceiling of any AI feature in the repo. Do not flip step 5 before
step 4 — layers 1–4 of the guardrails are only falsifiable if someone reads
the reports.

### 2026-09-24 - Owner decisions: gates 1 and 3 settled, gate 2 has a plan

- **Gate 3 — SETTLED.** The owner reads `/cms/` → "AI answer reports"
  **weekly**. "Actioned" = the answer is corrected, its source fixed, or the
  report dismissed with a note.
- **Gate 1 — IN PROGRESS.** `FORUM_VECTOR_SEARCH_ENABLED=True` set on the
  `plant_id_community` Railway service on 2026-09-24 (Railway MCP, owner
  approved). Remaining: confirm it took effect, then the owner builds the
  indexes (`railway ssh ... python manage.py rebuild_indexes SimilarTopics BlogChunks`).
- **Gate 2 — PLAN.** The owner allows AI-generated care articles (the earlier
  "do not AI-generate" rule was agent-written; corrected above). Todo 445
  drafts ~50 care articles in the CMS; the owner spot-checks and publishes
  them. Re-measure the corpus before flipping `FORUM_RAG_ENABLED`.
- **Spend:** accepted by the owner for the index build and, later, answers
  within `RAG_BUDGET_LIMIT`.
Still operator-ordered (Recommended Action steps 3, 5, 6); a sweep can only do
todo 445's drafting.

### 2026-09-24 - Gate 1 done: indexes built, vector search live

`FORUM_VECTOR_SEARCH_ENABLED` is declared in `.railway/railway.ts` (#828) and
live. `manage.py rebuild_indexes SimilarTopics BlogChunks` ran in production
2026-09-25 03:52 UTC: both rebuilt (1.59 s and 1.61 s), exit 0. The
similar-topics endpoint then returned relevant results. Remaining: gate 2 (the
corpus, via todo 445), then `FORUM_RAG_ENABLED` per steps 5–6.

### 2026-10-11 - RAG enabled in production

The owner approved the flip once todo 445's articles were published.

- **Gate 2, re-measured** (read-only prod shell): 59 `BlogPostPage`s are live and public, out of 59. That is
  at least 50 articles. Forum topics: 26.
- **Flag:** `FORUM_RAG_ENABLED=True` was set on `plant_id_community` through the Railway MCP. The redeployed
  container reports `rag_enabled() == True`. It is declared as `preserve()` in `.railway/railway.ts`, in a
  separate PR that the owner merges, because merging it applies the prod config.
- **BlogChunks rebuilt.** `sync_blog_page_chunks` only purges while the flag is off, so the pages published
  today had no chunks. `manage.py rebuild_indexes BlogChunks` then ran: `Successful rebuilds: 1`, 9.77 s,
  exit 0. Afterwards: `CHUNKS 302 PAGES 59 LIVE 59 MISSING []`.
- **Endpoint:** an anonymous `POST /api/v1/forum/care/ask/` returns 401. That says nothing about the flag,
  because the flag is checked inside the view after authentication (`rag.py:135`).
- **Still open:** AC 4 (a first real `answered` from a premium user) and AC 5 (review the floor against real
  `[RAG] retrieval top scores` lines). Both wait on real traffic, so they stay with the owner. Rollback:
  unset `FORUM_RAG_ENABLED`.

### 2026-10-17 - First answers observed; floor raised to 0.45

The owner chose to seed the first traffic rather than wait for it. Before
seeding, the prod logs since the 2026-10-11 flip held one `care/ask` call (an
anonymous 401 probe, 2026-10-12) and no `[RAG]` lines.

- **Seeding:** the owner asked 8 questions from a staff account (staff counts
  as premium) on the web `/forum/search` plant-care panel, 02:11–02:16 UTC.
  Five covered by the corpus, one adjacent, two off-corpus.
- **AC 4:** questions 1–5 came back `answered`. Question 1 (a pothos
  watering question) cited the pothos care guide.
- **AC 5:** the 8 `[RAG] retrieval top scores` lines (read-only Railway logs,
  owner-approved; they carry scores only, never question text):

| # | Question class | BlogChunks top | SimilarTopics top | Above 0.35 | Result |
|---|---|---|---|---|---|
| 1 | pothos watering | 0.81 | 0.57 | 14 | answered (pothos guide) |
| 2 | brown leaf tips | 0.65 | 0.51 | 15 | answered |
| 3 | fungus gnats | 0.65 | 0.35 | 9 | answered |
| 4 | monstera repotting | 0.63 | 0.57 | 14 | answered |
| 5 | snake plant root rot | 0.56 | 0.45 | 16 | answered |
| 6 | air plants (no article) | 0.53 | 0.33 | 8 | passages_only |
| 7 | tomato fertilizer (off-corpus) | 0.40 | 0.32 | 6 | passages_only |
| 8 | outdoor fig overwintering (off-corpus) | 0.50 | 0.34 | 8 | passages_only |

- **Reading:** at 0.35 the floor filtered nothing. Every question had 6+
  candidates above it, so no question got `no_information`. The off-corpus
  ones were caught only by the model's own `NO_INFORMATION` (`passages_only`),
  each after a paid call, and showed unrelated passages.
- **Decision:** `RAG_SIMILARITY_FLOOR` 0.35 → 0.45. Question 7 now gets
  `no_information` without an LLM call. The weakest answered question (0.56)
  keeps an 0.11 margin, and weak passages (question 3's 0.35 forum hit) drop
  out of the prompt context. 0.55 would also refuse 6 and 8 but sits 0.01
  under question 5, too tight for 8 samples; the model still declines those.
- **Verified:** `pytest apps/forum_host/tests -k "rag or care"` 152 passed
  (the tests read the constant, none pins 0.35). Re-check the floor against
  `[RAG]` lines as the corpus and real traffic grow.
