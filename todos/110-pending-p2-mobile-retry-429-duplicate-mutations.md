---
status: pending
priority: p2
issue_id: "110"
tags: [mobile, flutter, networking]
dependencies: []
---

# Mobile: _shouldRetry returns true for 429 — retrying mutations on rate limit creates duplicates

## Problem

`api_service.dart` (~140): `_shouldRetry` returns `true` for `429` status codes on
requests marked `retryUnsafeRequestKey=true`. The client will re-submit the mutation
up to 3 times while the server is explicitly asking it to back off. For non-idempotent
POSTs (create forum post, create topic, upload image), this can create duplicate records.

## Recommended Action

`_shouldRetry` should NOT retry on 429 — the server has explicitly asked the client to
wait. The correct response to 429 is to propagate the error to the caller (or surface
it in the UI) and let the user retry manually after the rate window resets.

```dart
// _shouldRetry — exclude 429
if (statusCode == 429) return false;
```

If Retry-After header handling is desired, implement it separately as a deliberate
policy (delay + single retry), not the general retry loop.

## Acceptance Criteria

- [ ] `_shouldRetry` returns `false` for `429` status regardless of `retryUnsafeRequestKey`.
- [ ] 429 responses are propagated to the UI as a rate-limit error, not silently retried.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.
