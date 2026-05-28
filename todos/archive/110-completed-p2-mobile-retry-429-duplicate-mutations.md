---
status: completed
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

- [x] `_shouldRetry` returns `false` for `429` status regardless of `retryUnsafeRequestKey`.
- [x] 429 responses are propagated to the UI as a rate-limit error, not silently retried.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

- **Codegen check (was a flagged risk):** `api_service.dart` is a plain Dio
  service — no `@riverpod`/`@freezed`/`part` directives — so NO `build_runner`
  regen required. The CI codegen gate does not apply here.
- Removed `statusCode == 429` from `shouldRetry`'s `retryableStatus` set (+ a
  comment on why 429 must never retry). Renamed `_shouldRetry` → `shouldRetry`
  + `@visibleForTesting` (mirrors the existing `handleDioException`) to enable a
  unit test; updated the single internal call site.
- 429 now falls through to `handler.next(error)` → caller's `handleDioException`
  → `ApiException(statusCode: 429, "Too many requests...")` (AC2).
- Verification: `flutter test test/api_service_test.dart` → **all 23 pass**
  (+5 new: 429-not-retried-when-unsafe, 429-not-retried-on-GET, 500-still-retries
  regression guard, unmarked-500-not-retried, 429→ApiException). `flutter analyze`
  on both files: "No issues found!".
- Review (feature-dev:code-reviewer): 0 critical/high/medium; 1 low (test comment
  overclaimed interceptor coverage) — **fixed** (comment tightened).
