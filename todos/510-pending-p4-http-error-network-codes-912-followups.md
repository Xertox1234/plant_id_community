---
status: pending
priority: p4
issue_id: "510"
tags: [web, backend]
dependencies: []
triage: ready
triaged: 2026-10-01
---

# HTTP error network codes: non-blocking findings from PR #912 (todo 489)

## Problem

PR #912 (todo 489) merged after two review rounds in todo-sweep run 2026-10-01-0121. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`web/src/services/notificationService.ts:23`** (low, round 1). The comments still promise every failure becomes a plain Error with a readable message: notificationService.ts:23, profileService.ts:23 ('never axios's ... text') and the httpError.ts module header. A non-connection AxiosError (ERR\_INVALID\_URL and the like) now passes through with axios's own message, and ProfilePage/ProfileStats display it.
   Suggested: Update the three comments to say a non-connection, response-less AxiosError (a client bug) is rethrown unchanged with axios's own message (todo 489 owner decision).

2. **`web/src/utils/httpError.ts:2`** (low, round 2). Module header still says toHttpError turns an apiClient failure 'into a plain Error' with a user-fit message, but after todo 489 a non-connection response-less AxiosError (ERR\_INVALID\_URL, code-less) is returned unchanged, raw axios text and all.
   Suggested: Reword the header to say HTTP and connection failures become a plain Error with a user-fit message, while cancellations, non-axios errors and other response-less axios errors pass through unchanged (todo 489).
   Also reported: Header says toHttpError returns 'a plain Error whose message is fit to show a user', and profileService.ts:23 says callers never get axios's text. Neither holds now: a non-connection AxiosError comes back raw with axios's own message.

3. **`web/src/utils/httpError.ts:21`** (low, round 2). The allowlist covers only browser/XHR codes (ERR\_NETWORK, ECONNABORTED, ETIMEDOUT). A Node-adapter failure (ECONNREFUSED, ENOTFOUND) would now pass through untranslated. Fine for the browser-only web client.
   Suggested: No change needed; add a comment that the allowlist assumes the XHR adapter.

4. **`web/src/utils/httpError.ts:63`** (low, round 1). Response-less axios errors with any other code now pass through with axios's raw message (e.g. Node-adapter ECONNREFUSED/ENOTFOUND, ERR\_BAD\_REQUEST without response) instead of the friendly connection text. Browsers emit ERR\_NETWORK so impact is small.
   Suggested: Accept the tradeoff (owner decision), or add the Node network codes to CONNECTION\_ERROR\_CODES if SSR/Node callers exist.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #912 review rounds 1-2.
