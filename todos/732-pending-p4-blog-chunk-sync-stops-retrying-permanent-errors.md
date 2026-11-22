---
status: pending
priority: p4
issue_id: "732"
tags: [celery, rag, blog, embeddings]
dependencies: []
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

- [ ] An authentication error from the provider is not retried and is logged once (a test).
- [ ] A transient provider error and `SoftTimeLimitExceeded` are still retried (a test each).

## Work Log

### 2026-11-22 - Filed on the owner's decision

- Asked whether to track L12's permanent-provider-error half, the owner answered "Yes".
