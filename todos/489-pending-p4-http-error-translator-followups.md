---
status: pending
priority: p4
issue_id: "489"
tags: [web, backend, blog]
dependencies: []
source_review: "PR #882"
---

# HTTP error translator and preview expiry: non-blocking findings from PR #882 (todo 434)

## Problem

PR #882 merged the web HTTP error translators into `toHttpError` and moved preview-token expiry
into the model. Both review rounds were clean. These are the non-blocking findings.

## Findings

1. **`BlogPostPreviewAPIViewSet.PREVIEW_TOKEN_MAX_AGE` is dead.** The model now reads the
   constant, so overriding the attribute does nothing. `test_expired_token_is_404`
   (`test_page_preview.py:225`) still reads it, so it looks like a working security setting
   (`viewsets.py:838`).
2. **Client bugs read as connection problems.** Every response-less `AxiosError` becomes
   `NETWORK_ERROR_MESSAGE`, including `ERR_INVALID_URL`, `ERR_BAD_OPTION_VALUE` and interceptor
   rejections (`httpError.ts:48`).
3. **Stale test rows.** The `notificationService.test.ts` `it.each` rows still pass by substring
   against `'Request failed (HTTP 500)'`, and their labels describe the old wording
   (`notificationService.test.ts:94`).
4. **A stale header comment** in `httpClient.test.ts:7` says the tests avoid the full axios
   instance. The new Error logging block drives it.

## Acceptance Criteria

- [ ] The viewset attribute is removed, and the expiry test reads `constants.PREVIEW_TOKEN_MAX_AGE`.
- [ ] Only `ERR_NETWORK`, `ECONNABORTED` and `ETIMEDOUT` get the connection message, with a test
      for another code.
- [ ] The notification rows assert the full message.
- [ ] The header comment is corrected.

## Work Log

### 2026-09-28 - Filed from PR #882 rounds 1 and 2 (todo sweep run 2026-09-28-2018)
