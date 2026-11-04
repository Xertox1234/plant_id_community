---
status: completed
priority: p3
issue_id: "653"
tags: [ai, evals, rag, forum, openrouter, research]
dependencies: []
triage: ready
triaged: 2026-11-03
owner_decision: "Unblocked: start design. Write the eval design spec now; judge model, spend cap, run location and key storage stay open owner questions in the spec (2026-11-03)"
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

- [x] The OCRecipes eval design is summarised in the design doc: what is
      reused, what is not, and why.
- [x] The first suite is chosen, and at least 20 draft cases are listed by
      class (no real user text or PII).
- [x] The owner has decided where it runs, which judge model, the spend cap
      per run, and how the key is stored (recorded verbatim with the date).
- [x] A design doc is written under `docs/superpowers/specs/`, and the build
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

### 2026-11-03 - Implemented by the todo sweep (run 2026-11-03-2214)

- Wrote `docs/superpowers/specs/2026-11-03-llm-eval-design.md`. It keeps the
  2026-10-24 scope: phase 1 is a judge-free management command (embeddings
  only), and phase 2 is a judged old-vs-new comparison, run only before a swap.
- The spec's §3 table says which parts of the OCRecipes design carry over and
  why. Not reused: baselines, the nightly workflow and the TypeScript code. The
  replay-contamination check passes: RAG writes no row any index reads.
- The first suite is RAG, with 24 newly written draft cases in six classes
  (spec §8). All 24 were run through `classify_blocked_question` and match
  their class.
- The build is filed as todo 694 (phase 1, starting with the `answer_question()`
  extraction).
- Still open: the owner's answers on run location, judge model, spend cap and
  key storage (spec §7, with recommended defaults).

### 2026-11-03 - Verified by the todo sweep (run 2026-11-03-2214)

- AC 1: `grep -nE '^## 3\.|\*\*(Reused|Not reused|Folded|Reference)' docs/superpowers/specs/2026-11-03-llm-eval-design.md` — evidence `.sweep-evidence/g5/653-ac0.txt` (not committed), last lines:

  ```text
  52:| Stored baselines with bootstrap mean bounds; `eval:compare` against them | **Not reused** | Nothing changes often enough to need history (`RAG_PROMPT_VERSION = 1`, the floor moved once). A paired old-vs-new run on the same cases answers the only question asked |
  53:| Nightly / `workflow_dispatch` GitHub workflow | **Not reused** | The suite needs the real corpus and its embeddings, which CI does not have, and a nightly run costs money with nothing changing |
  54:| `--candidate` model flag as a separate feature | **Folded into phase 2** | The paired comparison is the candidate run |
  55:| Multi-suite `SuiteConfig` core | **Not reused** | One suite. Generalise when a second suite exists |
  56:| About $0.30 a run | **Reference only** | Phase 1 is embeddings only (cents). Phase 2's cost is an open decision (§7) |
  ```

- AC 2: `grep -nE '^# |^## 8\.|^\| [0-9]+ \| [a-z-]+ \| (covered|adjacent|off-corpus|blocked-ingestion|blocked-chemical|not-blocked) \|' docs/superpowers/specs/2026-11-03-llm-eval-design.md` — evidence `.sweep-evidence/g5/653-ac1.txt` (not committed), last lines:

  ```text
  192:| 20 | offcorpus-fig-overwinter | off-corpus | How do I protect an outdoor fig tree through a hard frost? | `no_information` |
  193:| 21 | offcorpus-lawn | off-corpus | When should I aerate a clay-soil lawn? | `no_information` |
  194:| 22 | notblocked-slugs | not-blocked | Something is eating holes in my hosta leaves overnight. What could it be? | not a referral |
  195:| 23 | notblocked-toxic-to-plants | not-blocked | Is softened tap water toxic to plants? | not a referral |
  196:| 24 | notblocked-fertilize-amount | not-blocked | How much fertilizer should I give a pothos in spring? | not a referral |
  ```

- AC 4: `grep -nE '^status:|^# ' todos/694-pending-p3-build-rag-eval-command.md docs/superpowers/specs/2026-11-03-llm-eval-design.md` — evidence `.sweep-evidence/g5/653-ac3.txt` (not committed), last lines:

  ```text
  todos/694-pending-p3-build-rag-eval-command.md:2:status: pending
  todos/694-pending-p3-build-rag-eval-command.md:9:# Build the RAG eval command (phase 1, judge-free)
  docs/superpowers/specs/2026-11-03-llm-eval-design.md:1:# LLM Eval System — RAG Plant-Care First Suite
  ```

### 2026-11-03 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-03-2214)

- AC 3: confirmed by the owner on 2026-11-03: "Accept recommendations: runs locally, on demand, never against production data; judge anthropic/claude-sonnet-4.6 pinned in the command's settings (the OCRecipes judge); a small fixed spend cap per run, refused before the first call when the projection exceeds it (OCRecipes runs cost about $0.30); OPENROUTER_API_KEY in local backend/.env only, never committed" (`state.py confirm`; no command or evidence)

### 2026-11-03 - Completed by the todo sweep (run 2026-11-03-2214)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
