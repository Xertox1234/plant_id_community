# Evals

LLM evals are a separate tier: never in pre-commit, never in the pytest run,
run by hand. Design: `docs/superpowers/specs/2026-11-03-llm-eval-design.md`
(todo 653); phase 1 was built by todo 694, phase 2 on 2026-11-04.

| Path | What |
|---|---|
| `datasets/rag-cases.json` | The RAG plant-care cases (spec §8). Validated on every pytest run by `apps/forum_host/tests/test_rag_eval_dataset.py` |
| `results/` | `rag_eval --json` and `rag_eval_judged --json` output. Gitignored |

## Phase 1: `manage.py rag_eval` (judge-free)

Runs every case through `answer_question(..., generate=None, persist=False,
charge=False)`: no completion call, no `RagAnswer` row, none of the live
`RAG_BUDGET_LIMIT`. The only spend is the question embeddings, charged to
`EMBED_BUDGET` (about 2 units per non-blocked case, so about 38 of its 1000 for
the 24 cases).

```bash
cd backend
python manage.py rag_eval                       # the shipped cases, RAG_SIMILARITY_FLOOR
python manage.py rag_eval --floor 0.55          # measure a floor before changing it
python manage.py rag_eval --json run-0.55.json  # also writes evals/results/run-0.55.json
python manage.py rag_eval --cases path/to/other-cases.json
```

It prints one row per case (id, class, outcome, top `BlogChunks` score, top
`SimilarTopics` score, the expected slug's rank, pass), a pass count per class,
the weakest covered case's margin over the floor, and the strongest off-corpus
score's margin under it. Case failures are reported, not an error exit.

| Class | Passes when |
|---|---|
| `covered` | not a referral, and `expected_slug` is among the merged passages the prompt would see |
| `adjacent` | reported only: the class the floor is tuned on |
| `off-corpus` | nothing clears the floor (`no_information`) |
| `blocked-ingestion` / `blocked-chemical` | a referral with reason `ingestion` / `chemical_dosing`, before any retrieval |
| `not-blocked` | not a referral |

**It refuses to run** when `DEBUG` is False, when a Railway environment is
detected (any of `RAILWAY_ENVIRONMENT`, `RAILWAY_ENVIRONMENT_NAME`,
`RAILWAY_PROJECT_ID`, `RAILWAY_SERVICE_ID`), when `FORUM_VECTOR_SEARCH_ENABLED`
is off, and when the `BlogChunks` index is empty. A case whose retrieval comes
back unavailable (embedding budget exhausted, provider down) aborts the run.
**Never run it on a production shell.** Nothing here reads production data.

**The floor moved 0.45 → 0.5 on 2026-11-04** from this command's numbers
(local corpus): at 0.45 the off-corpus fig-overwintering case (top 0.487)
cleared the floor; at 0.5 all 3 off-corpus cases refuse, and the weakest
covered case keeps a 0.055 margin. `covered-snake-root-rot` fails at both
floors: its expected article is not among the merged passages, a retrieval
ranking issue the floor cannot fix.

## Phase 2: `manage.py rag_eval_judged` (judged, before a model or prompt swap)

A paired comparison on the `covered` and `adjacent` cases only (blocked and
off-corpus cases never reach the model). Each case runs through
`answer_question(..., persist=False, charge=False)` twice, once per arm. An arm
is a model and a prompt template. The **old** arm defaults to the production
model (`WAGTAIL_AI["PROVIDERS"]["default"]["model"]`) and `RAG_PROMPT_TEMPLATE`;
`--old-model`/`--old-prompt` override it. The **new** arm takes the old arm's
values unless `--new-model`/`--new-prompt` say otherwise, and must change at
least one. The judge, `EVAL_JUDGE_MODEL` (`claude-sonnet-5-5`, pinned in
`apps/forum_host/constants.py`), then scores each answer 1-10, with a one-line
reason, on groundedness, relevance and safety. It reads the exact prompt the
answering model received: rules, question and numbered passages.

```bash
cd backend
python manage.py rag_eval_judged --new-model gpt-4o-mini                 # A/A: measures noise
python manage.py rag_eval_judged --new-model <candidate> --runs 3 --json swap.json
python manage.py rag_eval_judged --new-prompt prompt-v2.txt --runs 3 --json prompt-v2.json
```

- **A prompt file** is a text file holding a whole template, like
  `RAG_PROMPT_TEMPLATE`: exactly the `{question}` and `{passages}` fields (a
  literal brace is written `{{` or `}}`) and the `NO_INFORMATION` sentinel.
  Anything else is refused before a call. The output names each arm's prompt
  as `production@<hash>` or `<file>@<hash>` (first 12 hex of its SHA-256), so a
  result records the exact text it ran. The judge's rubric is fixed, so a
  candidate that drops a rule (safety, citations) is still scored against it.
  Shipping a winner means editing `RAG_PROMPT_TEMPLATE` and bumping
  `RAG_PROMPT_VERSION`, which every `RagAnswer` row records.

- **Keys.** The judge needs `ANTHROPIC_API_KEY` in `backend/.env`, local only:
  never committed, never a repository or Railway secret. Generation uses the
  production `OPENAI_API_KEY`.
- **Generation bypasses the answer cache.** It calls the OpenAI SDK directly,
  sending what the production provider sends (one user message, the model id,
  the timeout). `generate_ai_text` goes through `CachedLLMService`, whose Redis
  key is the prompt alone, so the new arm would get the old arm's cached answer
  and a repeat run would replay answers instead of sampling.
- **Hard assertions first,** on the raw reply (`answer_question` strips
  invented citations, so its answer cannot show them): status `answered` or
  `passages_only`, and every `[n]` resolves to a passage. A failed arm is not
  judged. `passages_only` passes but has no answer to score: it is counted, and
  more of them from the new arm is itself a signal. A case retrieval stops
  (`no_information`) is reported `not_reached`. A case whose arms saw different
  passages is reported and not judged.
- **Output:** a row per case and arm (status, the three scores, any failure),
  the per-dimension mean per arm, the paired difference per case, and every
  case where the new arm scored lower by 2 or more on any dimension. **One run
  is one sample:** read a difference only across 3 runs (`--runs 3` averages
  the paired difference per case; OCRecipes measured about +/-0.5 run-to-run).
- **Spend cap: $3.00 per invocation** (`EVAL_SPEND_CAP_USD`), judge and
  generation together (the spec prices only the judge; counting generation
  too is the safer reading). It refuses before the first call when the projection is over the cap,
  and stops after any call that pushes the measured total (from each
  response's usage) past it, printing the partial results. A model with no row
  in `EVAL_PRICES_PER_MTOK` is refused: add its price first. Embeddings are
  not counted (cents; about 4 `EMBED_BUDGET` units per case per run).
- **Measured, first run 2026-11-04** (A/A: `gpt-4o-mini` against itself, local
  corpus of 53 AI-drafted care articles): 13 cases, 50 calls, **$0.15**
  (judge $0.146, about $0.006 a call; generation $0.004), against a $0.56
  projection. Means per arm differed by up to 0.42, and one case moved 3
  points on groundedness with no change at all: a single run can show a false
  regression, which is why a difference is read across 3 runs.
  The first prompt comparison the same day (the production prompt with "at
  most 3 sentences" for 5, one run) cost $0.14 for 50 calls: means moved by
  under 0.2 and one case dropped 2 points, the same size as the A/A noise.
- **It refuses to run** under the same conditions as phase 1, plus a missing
  `ANTHROPIC_API_KEY`.
- **A/A first.** Before reading a model or prompt difference, an A/A run
  (`--new-model` set to the production model) shows the noise on the same
  corpus.

## Loading the corpus into a dev DB

The corpus is the live, public blog articles (`BlogChunks`) and forum topics
(`SimilarTopics`). The covered cases expect the care articles from
`apps/blog/care_topics.py`. In a local dev DB:

1. In `backend/.env`: `DEBUG=True`, `FORUM_VECTOR_SEARCH_ENABLED=True` and an
   `OPENAI_API_KEY` (drafting and embedding both need it). Never commit the key.
2. Make sure a `BlogIndexPage` exists (`/cms/`), and a user to author the
   drafts.
3. Draft the care articles. This spends completions, one per topic (about 50);
   it is idempotent, so a re-run fills only what is missing:

   ```bash
   python manage.py generate_care_drafts --dry-run          # list what it would draft
   python manage.py generate_care_drafts --author <username>
   ```

4. Publish the drafts. In `/cms/` one by one, or, for a throwaway dev DB, all
   at once from `python manage.py shell`:

   ```python
   from apps.blog.care_topics import CARE_GUIDE_TAG
   from apps.blog.models import BlogPostPage

   for page in BlogPostPage.objects.filter(live=False, tags__name=CARE_GUIDE_TAG):
       page.save_revision().publish()
   ```

5. Build both indexes (embeds every chunk once):

   ```bash
   python manage.py rebuild_indexes SimilarTopics BlogChunks
   ```

6. Run `python manage.py rag_eval`.

The drafts are AI-written, so the local corpus is close to, not identical with,
the articles the owner reviewed and published in production. A covered case
that fails locally on a slug production has is worth checking against the local
article's text before tuning anything on it.
