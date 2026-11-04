---
status: completed
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

- [x] `answer_question()` is extracted; the existing `apps/forum_host/tests -k "rag or care"` tests pass
      unchanged, and a new test shows that with `persist=False, charge=False` it writes no `RagAnswer` row
      and does not charge `RAG_BUDGET_LIMIT`.
- [x] With `generate=None`, `answer_question()` returns after retrieval and the passage merge and makes no
      completion call (a test asserts zero calls on the completion client itself, not on a patched default), and with the RAG budget exhausted a blocked question still returns its referral.
- [x] `backend/evals/datasets/rag-cases.json` holds at least 20 cases and a pytest test validates it.
- [x] `manage.py rag_eval` runs against a dev DB with the corpus and prints a pass count per class;
      it refuses to run when `BlogChunks` is empty, when `FORUM_VECTOR_SEARCH_ENABLED` is off, and when
      `DEBUG` is False or a Railway environment is detected (a test covers each refusal; the test runner forces `DEBUG=False`, so the happy-path tests use
      `@override_settings(DEBUG=True)` and one separate test asserts the DEBUG refusal); an `unavailable`
      retrieval aborts the run; `backend/evals/results/` is in `.gitignore`.
- [x] The dev-DB corpus recipe is written down.

## Work Log

### 2026-11-03 - Filed

Filed by the todo sweep (run 2026-11-03-2214) from todo 653's design, as its build. Phase 2 is out of
scope here; the owner settled its decisions on 2026-11-03 (spec §7).

### 2026-11-04 - Implemented by the todo sweep (run 2026-11-04-0327)

- Extracted `answer_question()` and `RagOutcome` from `PlantCareAskView.post` in
  `backend/apps/forum_host/rag.py`; the view keeps the flag gate, body validation and an HTTP mapping
  (`budget_exhausted` is the 429 with `Retry-After`). The default `generate` resolves `generate_ai_text`
  at call time through a sentinel, so existing patches of the module global still reach it.
- `retrieve_grounding_passages` gained `floor=` (call-time default unchanged) and a `top_scores=`
  out-parameter, so its `list | None` return, and every patch of it, stay as they were.
- Added `backend/evals/datasets/rag-cases.json` (the spec's 24 cases), `manage.py rag_eval` with the
  DEBUG / Railway / vector-search / empty-`BlogChunks` refusals and the `unavailable` abort, and
  `backend/evals/results/` in `.gitignore`.
- Wrote the dev-DB corpus recipe in `backend/evals/README.md`. No live-corpus run was made: the slot DB
  has no corpus, and loading one spends about 50 completions; the command tests fake retrieval only.

### 2026-11-04 - Verified by the todo sweep (run 2026-11-04-0327)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/forum_host/tests -k "rag or care" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/694-ac0.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  =============== 190 passed, 728 deselected, 3 warnings in 27.72s ===============
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/forum_host/tests/test_rag_answer_question.py -v --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/694-ac1.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 10 passed, 3 warnings in 24.68s ========================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/forum_host/tests/test_rag_eval_dataset.py -v --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/694-ac2.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 11 passed, 3 warnings in 0.37s ========================
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/forum_host/tests/test_rag_eval_command.py -v --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/694-ac3.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 17 passed, 3 warnings in 24.50s ========================
  ```

- AC 5: `grep -n -E "Loading the corpus|generate_care_drafts --author|publish\(\)|rebuild_indexes SimilarTopics BlogChunks|python manage.py rag_eval$" backend/evals/README.md` — evidence `.sweep-evidence/g1/694-ac4.txt` (not committed), last lines:

  ```text
  48:## Loading the corpus into a dev DB
  63:   python manage.py generate_care_drafts --author <username>
  74:       page.save_revision().publish()
  80:   python manage.py rebuild_indexes SimilarTopics BlogChunks
  ```

### 2026-11-04 - Completed by the todo sweep (run 2026-11-04-0327)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-04 - Review round 1 (PR #1270): no blocking findings; non-blocking ones fixed or declined

Fixed by hand, each with a test that was mutation-checked (fails with the fix reverted):

- **Medium: partial retrieval read as a result.** When SimilarTopics searched but BlogChunks could not, `answer_question` did not report `unavailable`, so an off-corpus case read as a pass and a covered case as a miss. Fixed:
  - `retrieve_grounding_passages` now writes a `top_scores` key only for an index that searched (`None` = searched, found nothing).
  - `rag_eval` aborts any non-referral case that has no `BlogChunks` key.
  - Tests: `test_blog_chunks_not_searching_aborts_the_run` and `test_floor_argument_and_top_scores_out_parameter`. The second also covers the low finding that the new `floor=`/`top_scores` had no direct retrieval test.
- **Medium/low (three reviewers): bogus expected rank.** Topic passages carry slug `None`, so `None in slugs` gave non-covered rows a bogus `expected_rank` and `expected_score`. Fixed by matching only a real expected slug. Test: `test_a_topic_passage_gives_a_non_covered_case_no_expected_rank`.
- **Low (two reviewers): unhashable `expected_slug`.** A list or object raised `TypeError`, a traceback instead of a `CommandError`. Fixed with an `isinstance(str)` check first. Test: `test_a_non_string_expected_slug_is_a_value_error`.
- **Low: question whitespace.** A question with surrounding whitespace broke `answer_question`'s stripped-input precondition. It is now refused by `validate_cases`. Test: `test_a_question_with_surrounding_whitespace_is_refused`.

Declined:

- **Low: `--json ../..` can write outside `evals/results/`.** Declined: this is a local dev command run by the person who types the path. A path they choose is not an attack surface, and the default lands in the gitignored directory.
- **Low: the command imports the private `vector_indexes._index_name`.** Declined: it is the same app (`forum_host`), and the eval's own tests import it too. Making it public is a rename with no behaviour change, outside this todo.

Verification: `pytest apps/forum_host/tests -k "rag or care"` gave 197 passed (190 before plus 7 new).

Land-time hand fix: `test_eval_results_directory_is_gitignored` failed under the pytest-staged pre-commit hook. Git exports `GIT_DIR` to hooks, so a `git check-ignore` run from `backend/` treats `backend/` as the repo top and misses the root `.gitignore` (reproduced). The test now removes `GIT_*` from the subprocess environment. Mutation-checked.

### 2026-11-04 - Review round 2 (PR #1270): no blocking findings

Fixed by hand:

- **Low: SimilarTopics not searching.** This is the mirror of the round-1 fix. If SimilarTopics could not search while BlogChunks did, the topic corpus went unchecked. `rag_eval` now requires every index in `SEARCHED_INDEXES` to have searched before it scores a non-referral case. Test: `test_similar_topics_not_searching_aborts_the_run`. Mutation-checked: it fails with only BlogChunks required.

Declined:

- **Rows from cases already run are lost when a later case aborts.** Declined: an abort means the environment is broken (budget or provider), so a partial table would be compared against a full run. Re-run once the environment is fixed. That costs about 2 embedding units per case.
- **`--json` path escape and overwrite (three reviewers).** Declined for the same reason as round 1: it is an operator-chosen path on a DEBUG-only local command.
- **The happy-path `assert_not_called` on the LLM service is vacuous.** Declined: it is harmless. The real zero-completion guard is `test_rag_answer_question.py`, which acceptance criterion 2 pins.
- **The calibration log no longer lists an index that could not search (two reviewers).** Accepted as intended: a missing key now means "could not search", and the docstrings say so.
- **Private `_index_name` import.** Declined for the same reason as round 1.
- **Direct `answer_question` tests for provider error, empty reply and zero citations.** Declined: those branches moved unchanged, and the view tests in `test_rag.py` still pin them (190 passing, unedited).

Verification: `pytest apps/forum_host/tests -k "rag or care"` gave 198 passed.
