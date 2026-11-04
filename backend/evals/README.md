# Evals

LLM evals are a separate tier: never in pre-commit, never in the pytest run,
run by hand. Design: `docs/superpowers/specs/2026-11-03-llm-eval-design.md`
(todo 653); phase 1 was built by todo 694.

| Path | What |
|---|---|
| `datasets/rag-cases.json` | The RAG plant-care cases (spec §8). Validated on every pytest run by `apps/forum_host/tests/test_rag_eval_dataset.py` |
| `results/` | `rag_eval --json` output. Gitignored |

## Phase 1: `manage.py rag_eval` (judge-free)

Runs every case through `answer_question(..., generate=None, persist=False,
charge=False)`: no completion call, no `RagAnswer` row, none of the live
`RAG_BUDGET_LIMIT`. The only spend is the question embeddings, charged to
`EMBED_BUDGET` (about 2 units per non-blocked case, so about 38 of its 1000 for
the 24 cases).

```bash
cd backend
python manage.py rag_eval                       # the shipped cases, RAG_SIMILARITY_FLOOR
python manage.py rag_eval --floor 0.5           # measure a floor before changing it
python manage.py rag_eval --json run-0.5.json   # also writes evals/results/run-0.5.json
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
