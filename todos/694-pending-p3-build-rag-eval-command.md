---
status: pending
priority: p3
issue_id: "694"
tags: [ai, evals, rag, forum, backend]
dependencies: []
triage: ready
triaged: 2026-11-03
---

# Build the RAG eval command (phase 1, judge-free)

## Problem

RAG plant-care answers have no quality measurement. Changing the similarity floor, the prompt or the model
needs a hand-run session on production (todo 330, 2026-10-17). The design is in
`docs/superpowers/specs/2026-11-03-llm-eval-design.md` (todo 653). This todo builds its phase 1: a
judge-free check run locally against a dev DB with the corpus.

## Findings

- The whole pipeline lives inside `PlantCareAskView.post` (`backend/apps/forum_host/rag.py`). Each call
  writes a `RagAnswer` row and charges `RAG_BUDGET_LIMIT`, so the eval cannot call the view.
- Phase 1 needs no LLM completion: blocked questions are classified before retrieval, and covered and
  off-corpus questions are settled by retrieval scores. The only spend is question embeddings
  (`EMBED_BUDGET`, about 2 units per non-blocked case, about 38 of 1000 per run).
- The spec's §8 lists 24 draft cases. All 24 were checked against `classify_blocked_question` on
  2026-11-03 and match their class.
- Phase 2 (judged paired comparison) is not part of this todo. The owner settled its judge model, spend
  cap and key storage on 2026-11-03 (spec §7); only the cap's dollar figure is still the owner's to set, before phase 2 is built.

## Recommended Action

Follow the spec's §9 steps 1–4:

1. Extract `answer_question()` from `PlantCareAskView.post` (spec §4). The view keeps the flag check, body
   validation and HTTP mapping; the budget peek moves inside `answer_question()` after
   `classify_blocked_question`, skipped when `charge=False`, and `budget_exhausted` maps to today's 429 with
   `Retry-After`. The view's responses do not change.
2. Add `backend/evals/datasets/rag-cases.json` from spec §8, and a pytest test that validates it (schema,
   `care_topics.py` slugs, the blocked class of every case).
3. Add `manage.py rag_eval` (spec §5): `--cases`, `--floor`, `--json`; refuse when `BlogChunks` is empty;
   print the per-case table and per-class pass counts.
4. Write the recipe for loading the corpus into a dev DB and building the indexes.

## Technical Details

- Code: `backend/apps/forum_host/rag.py`, `rag_retrieval.py`, `rag_guardrails.py`, `constants.py`
  (`RAG_SIMILARITY_FLOOR`, `RAG_MAX_PASSAGES`, `RAG_PROMPT_VERSION`).
- Ground truth for covered cases: `backend/apps/blog/care_topics.py`.
- Guardrails are product rules: `backend/docs/patterns/domain/forum.md` §"RAG guardrails are product
  rules, not prompt instructions".
- Never run the command on a production shell.

## Acceptance Criteria

- [ ] `answer_question()` is extracted; the existing `apps/forum_host/tests -k "rag or care"` tests pass
      unchanged, and a new test shows that with `persist=False, charge=False` it writes no `RagAnswer` row
      and does not charge `RAG_BUDGET_LIMIT`.
- [ ] With `generate=None`, `answer_question()` returns after retrieval and the passage merge and makes no
      completion call (a test asserts zero calls on the completion client itself, not on a patched default), and with the RAG budget exhausted a blocked question still returns its referral.
- [ ] `backend/evals/datasets/rag-cases.json` holds at least 20 cases and a pytest test validates it.
- [ ] `manage.py rag_eval` runs against a dev DB with the corpus and prints a pass count per class;
      it refuses to run when `BlogChunks` is empty, when `FORUM_VECTOR_SEARCH_ENABLED` is off, and when
      `DEBUG` is False or a Railway environment is detected (a test covers each refusal; the test runner forces `DEBUG=False`, so the happy-path tests use
      `@override_settings(DEBUG=True)` and one separate test asserts the DEBUG refusal); an `unavailable`
      retrieval aborts the run; `backend/evals/results/` is in `.gitignore`.
- [ ] The dev-DB corpus recipe is written down.

## Work Log

### 2026-11-03 - Filed

Filed by the todo sweep (run 2026-11-03-2214) from todo 653's design, as its build. Phase 2 is out of
scope here; the owner settled its decisions on 2026-11-03 (spec §7).
