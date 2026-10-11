---
status: pending
priority: p4
issue_id: "553"
tags: [todo-sweep, follow-ups, backend]
dependencies: []
owner_decision: "Finding 2 and the finding-5 re-check: make SecurityMonitor._get_client_ip use the trusted-proxy resolver the login rate limit already uses (apps.core.ratelimit.get_trusted_client_ip), and keep the raw IP, now the real client's, in the brute-force alert as the 2026-10-02 finding-5 decision intended (2026-10-10) Fix both guards properly: narrow the ImportError guard to the .constants Try nodes, and drive the real complete_social_login chain in the allauth test (2026-10-11)"
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #941 (todos 418, 435), run 2026-10-02-0335

## Problem

Promoted out of todo 527 on 2026-10-10 (owner decision: slice it per PR). Todo-sweep run 2026-10-02-0335
merged PR #941; its review rounds reported the non-blocking findings below, which a curation pass
checked against main and a refuter failed to refute. Line numbers are as of 2026-10-02, so re-check each
finding against main before acting on it.

## Findings

### PR #941 (todos 418, 435)

1. **`backend/apps/core/security.py:241`** (low, defect). The account\_lockout alert payload logs the raw login identifier (often an email) at ERROR. Pre-existing; the finding-5 pass fixed only the sibling brute\_force\_login alert. \_lock\_account passes the raw identifier to \_trigger\_security\_alert, which json.dumps the payload into an ERROR log line. sentry\_sdk.init leaves the default integrations on, so that ERROR record also becomes a Sentry event and the identifier goes to a third party. docs/rules/security.md requires log\_safe\_username for a failed-login alert.
   Suggested: Use log\_safe\_username(username) in the account\_lockout alert dict only; the lockout email at 249-290 still needs the real account. Add a lockout case beside test\_failed\_login\_logs\_and\_alerts\_only\_a\_pseudonym asserting the identifier is absent from the alert payload.
   Seen on main: security.py:238-246 `_trigger_security_alert("account_lockout", {"username": username, ...})`; security.py:529-531 `logger.error(... json.dumps(details, indent=2))`; settings.py:1306-1327 sets no default\_integrations=False; docs/rules/security.md:372-374: a failed-login 'alert or log line gets log\_safe\_username(...), never the raw value'.

2. **`backend/apps/core/security.py:560`** (low, defect). The per-IP brute-force tracker keys on the proxy address: \_get\_client\_ip reads X-Forwarded-For only under USE\_X\_FORWARDED\_HOST, which nothing sets. Pre-existing; the login view now feeds it directly. Under gunicorn REMOTE\_ADDR is Railway's proxy, so in prod all clients share one per-IP failed-login bucket. Any user's successful login clears it, brute\_force\_login fires on combined failures from all users, and lockout emails list the proxy. It also undercuts finding 5's reason: the raw IP kept 'so an operator can block it' is the proxy's. That alert is an ERROR log line plus a 24h cache, not the email the decision assumed. No pending todo covers this.
   Suggested: Make SecurityMonitor.\_get\_client\_ip delegate to apps.core.ratelimit.get\_trusted\_client\_ip (fallback UNKNOWN\_IP\_ADDRESS), the resolver the login rate limit already uses. Pin it under RATELIMIT\_TRUSTED\_PROXY\_COUNT=2 with a spoofed left-prepended XFF entry, and update test\_ip\_spoofing\_protection.py. Then re-check the finding-5 owner decision against the corrected facts.
   Seen on main: security.py:560 `if getattr(settings, "USE_X_FORWARDED_HOST", False):` else REMOTE\_ADDR (580); only security.py and tests reference the setting; bin/start.sh:49 runs gunicorn; ratelimit.py:78-80 documents REMOTE\_ADDR as the proxy; track\_successful\_login deletes the key (431-433); views.py:298,321,332 use \_get\_client\_ip.

3. **`backend/apps/core/utils/pii_safe_logging.py:40`** (low, defect). The control-character strip covers only track\_failed\_login; log\_safe\_username still copies a raw 3-character prefix into the other login log lines. Pre-existing, and the forging is bounded. \_printable guards only the per-IP tracker. The same raw request identifier also reaches track\_failed\_login\_attempt (views.py:333) and the [SIGNUP] lines. There log\_safe\_username keeps username[:3] verbatim, so a newline in the first three characters splits the [AUTH]/[LOCKOUT] warnings. The new test cannot tell the isprintable allowlist from a naive newline strip. \_printable's non-str branch is untested: without the isinstance guard, ["abc"] logs 'abc\*\*\*hash' instead of None.
   Suggested: Strip non-printables inside log\_safe\_username before taking the prefix. That covers every caller and leaves cache keys raw, so is\_account\_locked still matches; \_printable then needs only its non-str guard. Extend the test with \\r, \\x85, and \\x1b specimens, a non-str identifier asserting username=None, and a view-driven [AUTH] line case.
   Seen on main: pii\_safe\_logging.py:40 `prefix = username[:3] if len(username) >= 3 else username`; security.py:131,178,196,227 log log\_safe\_username(username) of the raw value passed at views.py:333; views.py:116,163 same for [SIGNUP]; \_printable applied only at security.py:377; test\_legacy\_api\_mount\_removed.py:283-289 uses only 'x\\n[SECURITY] ...'.

4. **`backend/apps/users/tests/test_firebase_auth.py:252`** (low, defect). The Firebase not-tracked test drives only InvalidIdTokenError; the ExpiredIdTokenError 401 branch is unpinned. The docstring says a 401 from the token exchange is deliberately not brute-force input, but the test runs only one of the view's two 401 branches. A track\_failed\_login call added to the expired-token branch keeps the suite green. The path-level assertion this test replaced covered every 401 on the route.
   Suggested: Loop with subTest over InvalidIdTokenError and ExpiredIdTokenError, asserting the response's error message (which branch ran) and track.assert\_not\_called() in each.
   Seen on main: test\_firebase\_auth.py:259 `mock_verify.side_effect = InvalidIdTokenError(...)` is the only specimen; firebase\_auth\_views.py:337-344 is a separate `except firebase_auth.ExpiredIdTokenError` returning 401 'Firebase token has expired'.

5. **`backend/apps/users/views.py:342`** (low, defect). Where the tracker call sits is unpinned (the lock-crossing 429 counts, the locked and disabled returns don't); the comment gives the wrong reason for the disabled branch. The PR makes one deliberate semantic change: the attempt that locks the account (a 429) now feeds track\_failed\_login, while the already-locked 429 and the disabled 403 do not. No test covers it. Moving the call below `if account_locked:`, or above the locked check, keeps the suite green. The comment's reason is also wrong for the disabled branch: that 403 is reached only after check\_password matched. It goes uncounted because the credential was right, not because the check was skipped. A wrong password on a disabled account falls through and is counted.
   Suggested: Add view tests (RATELIMIT\_ENABLE=False, track\_failed\_login patched): ACCOUNT\_LOCKOUT\_THRESHOLD wrong passwords -> call\_count equals the threshold, the 429 included; a POST while locked and a correct-password POST for an inactive user -> no new call. Assert the IP, not mock.ANY. Reword the comment: the locked return comes before the password check, the disabled return after a matching one, so neither is a rejected credential.
   Seen on main: views.py:333-342 tracker call sits above `if account_locked:` (344); 339-341 say both early returns 'never check the password', but the 403 (316-329) is under `if user:`, set at 283 only when check\_password matched (282). test\_legacy\_api\_mount\_removed.py:155-207 drive only single-attempt 401s and 400s; test\_account\_lockout.py:378-417 drives the lockout without patching the tracker.

6. **`backend/apps/core/tests/test_legacy_api_mount_removed.py:325`** (low, polish). The ImportError drift guard bans every `except ImportError` in security.py and middleware.py, not just the dead constants fallback. test\_security\_modules\_import\_their\_constants\_unconditionally pins code shape. A later, legitimate optional-dependency guard in either module would fail it, although the fallback it targets was a try around `from .constants import`. A missing constant already fails loudly at import.
   Suggested: Narrow the walk to ast.Try nodes whose body holds an ImportFrom of `.constants`, or delete the test.
   Seen on main: test\_legacy\_api\_mount\_removed.py:337-342 collects ast.unparse(node.type) for every ExceptHandler in both modules and asserts 'ImportError' is not in the joined string (substring match).

7. **`backend/apps/users/tests/test_allauth_surface.py:108`** (low, polish). SocialLoginRedirectTest says it pins the redirect chain but never drives complete\_social\_login. The test checks only the premises: our account adapter answers, the account util returns '/', and neither the base nor our social adapter has get\_login\_redirect\_url. A social-side redirect hook under any other name would not trip it. So 'an allauth that grows a social-side hook shows up here', and the merge commit's 'drives the real chain', overstate what it guards.
   Suggested: Drive the chain: build a SocialLogin for a verified user, call complete\_social\_login and assert the 302 Location is '/'. Or soften the docstring to say only the premises are pinned, citing the allauth source as the evidence for the chain.
   Seen on main: test\_allauth\_surface.py:102-106 docstring claims the chain is pinned; 109-114 only call get\_account\_adapter, get\_login\_redirect\_url(request), hasattr(DefaultSocialAccountAdapter, ...) and vars(CustomSocialAccountAdapter); no complete\_social\_login call.

## Acceptance Criteria

- [ ] Each of its 7 findings is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).
