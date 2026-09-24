---
status: pending
priority: p2
issue_id: "409"
tags: [backend, web, blog, security, email]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
source_finding: "owner decision 2026-09-23"
---

# Blog newsletter: close the abuse surface, then wire it up

## Problem

Blog v1 `newsletter/` is `AllowAny` with no rate limit:

- Anyone can subscribe any email address, with no double opt-in.
- The "already subscribed" response versus a 201 lets anyone enumerate which
  addresses are subscribed.
- `POST newsletter/unsubscribe/ {"email": …}` unsubscribes any address, and its
  404 is a second enumeration oracle.
- No code ever sends a newsletter. `BlogNewsletter` has no sender.

The owner decided (todo 405) to **wire it up**, not remove it.

## Findings

Evidence is recorded in todo 405's 2026-09-23 Work Log. It came from a
`get_resolver()` route walk, client greps, and an adversarial verifier that ran
the endpoints against a test DB.

## Recommended Action

1. **Security first:** add double opt-in (a confirmation email with a signed
   token), rate limits, and responses that are identical whether or not the
   email is subscribed. Unsubscribing should use a signed token, sharing todo
   408's design.
2. Add a signup UI on the web: a blog footer or sidebar.
3. Add a sender. Decide the cadence, the content (new posts?), and the
   provider. Check with the owner before any recurring send.

## Technical Details

See the file references above, and todo 405's Work Log.

## Acceptance Criteria

- [ ] No endpoint lets a caller learn whether an email is subscribed. A test pins it.
- [ ] Subscribing takes effect only after email confirmation.
- [ ] The owner has agreed a sending cadence, and it is implemented or explicitly deferred.

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.
