---
status: blocked
priority: p3
issue_id: "653"
tags: [ai, evals, rag, forum, openrouter, research]
dependencies: []
---

# Explore an LLM eval system for the backend's AI features

## Problem

The backend ships four LLM features, and none of them has a way to measure
output *quality*. Unit tests mock the model, so they prove the code paths, not
that an answer is right, grounded or safe. Todo 330 showed the cost of that.
The RAG similarity floor shipped as a guess (0.35), and it took a hand-run,
8-question session on production (2026-10-17) to find that the floor filtered
nothing and to tune it to 0.45. Any change to a prompt, model, floor or corpus
is unmeasured until someone repeats that by hand.

The owner already built an eval system for the nutrition coach in the
OCRecipes project, running through OpenRouter, and has an OpenRouter API key
available for this one. This todo explores whether that design carries over,
and decides what to build. It does not build it.

## Findings

**AI features that could be evaluated (all `gpt-4o-mini` via django-ai-core
unless noted):**

| Feature | Code | What "good" means | Harm ceiling |
|---|---|---|---|
| RAG plant-care answers (premium, LIVE since 2026-10-11) | `backend/apps/forum_host/rag.py`, `rag_retrieval.py` | answers grounded in cited sources; off-corpus → `no_information`; blocked classes → referral | highest in the repo (todo 330 Notes) |
| Compose assist (premium, flag off) | `backend/apps/forum_host/compose_assist.py` | helpful rewrite, keeps author meaning, no invented facts | medium |
| LLM spam screen (dormant) | `backend/apps/forum_host/spam.py` `LLMSpamBackend` | precision/recall against labelled posts | false positives silence real users |
| Blog care-article generation | `manage.py generate_care_drafts` (todo 445) | accurate care advice; owner spot-checks today | published content |

RAG is the obvious first suite. It is the only live one, its harm ceiling is
highest, and todo 330 left a ready seed: 8 question classes with
`[RAG]` top scores and outcomes (in `todos/archive/330-…`'s Work Log).

**OCRecipes reference (`~/projects/OCRecipes/evals/`):**

- A separate tier, not part of the unit tests: `evals/` at the root, with a
  runner per suite (`npm run eval:coach`, …). Never pre-commit; manual runs
  plus a nightly / `workflow_dispatch` GitHub workflow
  (`.github/workflows/evals-nightly.yml`).
- Hybrid scoring: hard assertions (`mustContain` / `mustNotContain`,
  safety refusals) where one failure fails the case, plus LLM-as-judge rubric
  scores (1–10) from a stronger model (`EVAL_JUDGE_MODEL`, default
  `anthropic/claude-sonnet-4.6` through OpenRouter at
  `https://openrouter.ai/api/v1`).
- Datasets as JSON cases (`evals/datasets/*-cases.json`), validated by unit
  tests. Baselines per suite (`evals/baselines/*.json`: mean with confidence
  bounds, assertion pass rate, judge model), and `eval:compare` / `--paired`
  to compare a run against the baseline. A `--candidate` flag runs an
  alternative model by OpenRouter id.
- Written-up lessons worth reading first: `docs/solutions/` entries on
  assertion gotchas, dataset validation as unit tests, field forwarding,
  ground truth mutated by the feature under test, and the judge hiding new
  prompt fields; design specs
  `docs/superpowers/specs/2026-04-13-nutrition-coach-evaluation-design.md`
  and `2026-05-04-eval-framework-extension-design.md`.
- Cost noted there: about $0.30 a run.

**Differences that matter here:**

- This backend is Python/Django. The OCRecipes framework is TypeScript, so the
  *design* carries over, not the code.
- RAG quality depends on retrieval as well as generation. A suite needs the
  real corpus (59 blog articles plus forum topics) and real embeddings, so it
  cannot run against the empty test DB.
- `kimi-review.yml` already reads an `OPENROUTER_API_KEY` repository secret
  and notes that none is set, so the run self-skips. Adding the secret would
  turn that workflow on too.

## Recommended Action

Research and design only. Produce a short design doc and an owner decision.
Then file the build as its own todo(s).

1. Read the OCRecipes eval specs and `docs/solutions/` lessons listed above.
2. Pick the first suite (RAG is the default) and draft about 20–30 cases: the
   8 classes from todo 330, plus blocked classes (ingestion, pet toxicity,
   dosing → referral), off-corpus questions, and adjacent ones.
3. Decide, with the owner:
   - **Where it runs.** Locally against a dev DB loaded with a corpus snapshot,
     or a CI workflow, or on demand only. Never against production data.
   - **What is scored.** Hard assertions (status, citations exist and resolve,
     referral for blocked classes), plus judge rubrics (groundedness,
     relevance, safety). Also a retrieval-only metric (expected source in the
     top-k), which needs no LLM call and no judge.
   - **Judge model and spend cap** per run, through OpenRouter.
   - **Baselines.** How regressions are flagged (copy OCRecipes'
     mean-with-bounds baseline, or something simpler).
   - **Key handling.** Where `OPENROUTER_API_KEY` lives (local `.env` only, or
     a repo secret, which also enables `kimi-review.yml`).
4. Write the design to `docs/superpowers/specs/` and file the implementation
   todo(s).

## Technical Details

- Floor and tunables: `backend/apps/forum_host/constants.py`
  (`RAG_SIMILARITY_FLOOR` 0.45 since todo 330, `RAG_MAX_PASSAGES`,
  `RAG_PROMPT_VERSION`).
- RAG design: `docs/superpowers/specs/2026-07-29-forum-rag-plant-care-design.md`;
  guardrails: `backend/docs/patterns/domain/forum.md` §"RAG guardrails are
  product rules, not prompt instructions".
- Care topic list (ground truth for "covered" questions):
  `backend/apps/blog/care_topics.py` (53 topics).
- Never commit the OpenRouter key. `.secrets.baseline` is hand-maintained.

## Acceptance Criteria

- [ ] The OCRecipes eval design is summarised in the design doc: what is
      reused, what is not, and why.
- [ ] The first suite is chosen, and at least 20 draft cases are listed by
      class (no real user text or PII).
- [ ] The owner has decided where it runs, which judge model, the spend cap
      per run, and how the key is stored (recorded verbatim with the date).
- [ ] A design doc is written under `docs/superpowers/specs/`, and the build
      is filed as its own todo(s).

## Work Log

### 2026-10-16 - Filed

Filed at the owner's request after todo 330 closed (PR #1142). The owner
pointed at the OCRecipes coach eval system and has an OpenRouter API key to
use. OCRecipes facts above were read from that repo on 2026-10-16.

### 2026-10-24 - Deferred by the owner

Owner decision (2026-10-24): "I'm not sure we need it yet." Status set to
`blocked` so todo sweeps leave it alone. Nothing is changing that an eval
would measure: the prompt is at `RAG_PROMPT_VERSION = 1`, the floor has
moved once, and RAG is the only live AI feature (compose assist is
flag-off, the LLM spam screen dormant, blog drafts owner spot-checked).

**Revisit when any of these happens:**

- `gpt-4o-mini` is deprecated or retired, or another model is to be tried
- `RAG_PROMPT_VERSION` changes, or `RAG_SIMILARITY_FLOOR` needs re-tuning
- RAG usage grows enough that a bad answer reaches real people
- compose assist or the LLM spam screen is turned on

**Scope agreed when it comes back** (smaller than the full OCRecipes design):

1. First, a judge-free check: ~25 cases run by one management command,
   locally against a dev DB with the corpus. Blocked questions → `referral`
   (no API spend, `classify_blocked_question` runs before any provider call);
   covered questions → expected source in the top-k above the floor;
   off-corpus questions → nothing above it (embedding calls only). This
   automates the todo 330 hand session.
2. Only before a model or prompt swap: judged generation scoring through
   OpenRouter, as a plain old-vs-new paired comparison on the same cases.
   No stored baselines or nightly CI until changes are frequent.

**Prerequisite found 2026-10-24:** the whole pipeline lives inside
`PlantCareAskView.post` (`backend/apps/forum_host/rag.py`), and each call
writes a `RagAnswer` row and charges `RAG_BUDGET_LIMIT`. Extract an
`answer_question()`-style function the view and the eval both call, so
eval runs neither write rows nor spend the live budget.
