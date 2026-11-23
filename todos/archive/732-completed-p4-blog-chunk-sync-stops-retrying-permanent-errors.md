---
status: completed
priority: p4
issue_id: "732"
tags: [celery, rag, blog, embeddings]
dependencies: []
triage: ready
triaged: 2026-11-22
---

# The blog chunk sync stops retrying permanent provider errors

## Problem

`sync_blog_page_chunks` retries every exception up to its retry limit,
including a provider error that cannot succeed on retry: a bad or revoked API
key, or a 400 for a malformed request. Each retry re-runs the embed for one
page. The cost is small, because `CachedEmbeddingTransformer` makes unchanged
chunks free, but the retries add noise and delay the log line that matters.

## Findings

- `backend/apps/forum_host/tasks.py`, `sync_blog_page_chunks`: `autoretry_for=(Exception,)`, `retry_backoff=constants.RAG_INDEX_RETRY_DELAY`, `max_retries=constants.RAG_INDEX_MAX_RETRIES`.
- Source: audit 2026-11-21 L12 (`docs/audits/2026-11-21-forum-backend.md`). That audit declined the soft-time-limit half: a soft-limit timeout on one page's embed is usually transient provider slowness, and retrying it is right. Only the permanent-error half is tracked here.

## Recommended Action

1. Find the exception types the embedding provider raises for authentication failures and for 4xx request errors (check the client library's docs, through Context7).
2. Add them to `dont_autoretry_for` (Celery checks it before `autoretry_for`), and log them once at `[ERROR]` with the page id.
3. Leave transient errors (timeouts, 5xx, 429, connection errors, `SoftTimeLimitExceeded`) on the retry path.

## Technical Details

- Celery `app/autoretry.py`: `dont_autoretry_for` is checked first.
- The task is idempotent (purge-then-add on the page's key prefix), so retrying is safe; this change is about not wasting retries.

## Acceptance Criteria

- [x] An authentication error from the provider is not retried and is logged once (a test).
- [x] A transient provider error and `SoftTimeLimitExceeded` are still retried (a test each).

## Work Log

### 2026-11-22 - Filed on the owner's decision

- Asked whether to track L12's permanent-provider-error half, the owner answered "Yes".

### 2026-11-23 - Implemented by the todo sweep (run 2026-11-22-1957)

- `sync_blog_page_chunks` no longer retries a provider error a retry cannot fix: the OpenAI SDK's 400, 401, 403, 404 and 422 classes and the matching `any_llm` classes (`_permanent_embedding_errors` in `backend/apps/forum_host/tasks.py`). Both families are listed because `any_llm` raises the SDK's own classes unless its unified exceptions are on. The classes were read from the installed `openai` 3.57.0 and `any_llm` 1.53.1 packages, not from Context7.
- The error is logged once at ERROR with the page id and the error's class name, and the existing chunks are kept. The provider's message is not logged: it can quote the key it rejected.
- Different from the Recommended Action: the classes are caught in the task body, not listed in `dont_autoretry_for`. That option re-raises, and Celery's failure trace would log the same error a second time. It also needs the SDK imported when the tasks module loads, in every web process.
- Timeouts, connection errors, 429, 5xx and `SoftTimeLimitExceeded` are still retried.

### 2026-11-23 - Verified by the todo sweep (run 2026-11-22-1957)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/apps/forum_host/tests/test_rag_index_tasks.py::test_a_permanent_provider_error_is_not_retried_and_is_logged_once --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/732-ac0.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 6 passed, 2 warnings in 21.52s ========================

  exit code: 0
  ```

- AC 2: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/apps/forum_host/tests/test_rag_index_tasks.py::test_a_transient_provider_error_is_still_retried backend/apps/forum_host/tests/test_rag_index_tasks.py::test_a_soft_time_limit_during_the_embed_is_still_retried --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/732-ac1.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 7 passed, 2 warnings in 21.73s ========================

  exit code: 0
  ```

### 2026-11-23 - Completed by the todo sweep (run 2026-11-22-1957)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
