---
status: completed
priority: p3
issue_id: "416"
tags: [backend, email, forum]
dependencies: []
source_review: "todos/archive/408-completed-p2-email-unsubscribe-signed-token-and-pages.md"
source_finding: "follow-up filed 2026-09-23"
---

# Give the forum digest an unsubscribe link, and add one-click unsubscribe

## Problem

Todo 408 built signed unsubscribe links for the one email `EmailService` sends
today, the forum reply notification. Two gaps remain:

- **The weekly forum digest has no unsubscribe link.** It is sent by the
  package (`wagtail_forum/digest.py`) from its own templates, not through
  `EmailService`, so it gets no `unsubscribe_url` and no `List-Unsubscribe`
  header.
- **No RFC 8058 one-click unsubscribe.** Todo 408 sends
  `List-Unsubscribe: <https://…/unsubscribe?token=…>`, which opens the web
  page. Gmail and Yahoo require `List-Unsubscribe-Post: List-Unsubscribe=One-Click`
  for bulk senders (above about 5,000 messages a day). That needs a URL on the
  **API** origin that accepts a bare POST, and the backend has no setting for
  its own public origin (`SITE_URL` is the web app's).

## Findings

- `apps/users/email_unsubscribe.py` has a `LISTS` registry. A digest list would
  set `ForumProfile.digest_frequency` to off, which the Settings page's
  "Email digest" select can turn back on.
- The reply email's HTML body links "Unsubscribe from Topic" to
  `{{ topic_url }}#unsubscribe` (`templates/emails/forum_reply.html:50`). Check
  that the SPA topic page does something with that fragment. If it doesn't,
  point the link at the topic itself and say "unfollow".

## Recommended Action

1. Register a `forum_digest` list. Have the host shadow the package's digest
   templates, or add a context hook, so the digest gets a signed link and the
   header.
2. For one-click: add a backend public-origin setting (`API_PUBLIC_URL`), a
   `POST` endpoint that takes the token from the query string, and the
   `List-Unsubscribe-Post` header. Add the new variable to `.railway/railway.ts`.

## Technical Details

- `backend/packages/wagtail_forum/wagtail_forum/digest.py`
- `backend/apps/users/email_unsubscribe.py`
- `backend/apps/core/services/email_service.py` (`UNSUBSCRIBE_LISTS`, headers)
- RFC 8058; RFC 2369

## Acceptance Criteria

- [x] A digest email carries a signed unsubscribe link that turns the digest off (test).
- [x] Emails carry `List-Unsubscribe-Post: List-Unsubscribe=One-Click`, and a
      bare POST to the header's URL unsubscribes (test).

## Work Log

### 2026-09-23 - Filed from todo 408

Left out of todo 408 to keep it to the reply email, the only live
`EmailService` path.

### 2026-09-24 - Done: digest link + RFC 8058 one-click (dark until API_PUBLIC_URL)

- **Digest (AC 1).** New list `forum_digest` in `email_unsubscribe.LISTS`:
  unsubscribing sets `ForumProfile.digest_frequency` to `off`, which the
  Settings "Email digest" select turns back on. The package can't mint tokens,
  so it gained one setting, `WAGTAILFORUM_DIGEST_UNSUBSCRIBE`: a dotted path
  to a host callable `(user) -> {"url", "headers"}`. The host sets it to
  `email_unsubscribe.digest_unsubscribe`; the digest templates show the link
  and `send_digest` sends the headers. README documents the setting
  (`test_docs` passes).
- **One-click (AC 2).** New `POST /api/v1/auth/unsubscribe/one-click/?token=…`:
  no auth, no CSRF, same token, rate limit and idempotent unsubscribe as the
  body-token endpoint; the form body `List-Unsubscribe=One-Click` is ignored.
  `unsubscribe_headers(user, list_id)` is the one header policy for both the
  reply email (`EmailService`) and the digest: with `API_PUBLIC_URL` set,
  `List-Unsubscribe: <api one-click URL>` + `List-Unsubscribe-Post:
  List-Unsubscribe=One-Click`; unset, `List-Unsubscribe: <web page>` as
  before. The body link stays the web page (a person's click is a GET).
- **Why a new setting.** The backend had no setting for its own public
  origin: `SITE_URL` is the web app's, and `WAGTAILADMIN_BASE_URL` is not in
  `.railway/railway.ts`, so production still has its localhost default. Until
  the owner sets `API_PUBLIC_URL` on Railway, one-click ships dark (todo 437).
- **Findings bullet 2.** The SPA topic page ignores `#unsubscribe` (it only
  reads `#post-<id>`), so the reply email's "Unsubscribe from Topic" link just
  opened the topic. As the todo suggested, it now links the topic and says
  "View topic to unfollow" (`templates/emails/forum_reply.html`); pinned by
  `test_reply_email_offers_unfollow_not_a_dead_fragment`.
- Tests, each red with its fix removed (mutation-checked):
  `test_digest_carries_the_hosts_unsubscribe_link_and_header` (drop the
  header), `test_digest_link_turns_the_weekly_digest_off` (no-op
  unsubscribe), `test_one_click_header_accepts_a_bare_post` (drop
  `List-Unsubscribe-Post`; no-op one-click view),
  `test_digest_callable_carries_one_click_headers`. Plus
  `test_digest_without_a_host_callable_has_no_unsubscribe_link`,
  `test_without_api_public_url_there_is_no_one_click_header`,
  `test_one_click_rejects_a_forged_token`. The one-click POST uses
  `Client(enforce_csrf_checks=True)` with no session.
- `pytest apps/core apps/users packages/wagtail_forum apps/forum_host
  --create-db`: 3092 passed.

### 2026-09-24 - Review round 1 (bundled /code-review, PR #819): 9 repaired

- **Per-IP limit on one-click would drop real unsubscribes.** Providers POST
  from a few shared egress IPs; after 30/h per IP every later user's
  one-click got a 403. The one-click limit is now keyed on the token
  (`get:token`); a forged token fails the signature before any DB work.
  Test: 40 users' one-clicks from one IP all return 200 (red with the IP key).
- **GET on the one-click URL returned 405.** Clients without RFC 8058 open
  the header URL. GET now 302s to the web `/unsubscribe` page with the same
  token and changes nothing (scanners prefetch GETs). Test red with GET
  removed.
- **Two tokens per email.** Body and header links were minted separately
  (timestamped, so they could differ). One token is minted per email in
  `EmailService` and `digest_unsubscribe`, and passed to both builders.
  Pinned by `test_one_click_header_and_body_carry_the_same_token`; the
  mutation can't be forced red reliably (two signings in one second match).
- The existing header==body test now pins `API_PUBLIC_URL=""`.
- **A broken host hook aborted every digest.** `unsubscribe_links` now logs
  and returns None, so the digest still sends with its manage link. Test red
  with the guard removed.
- `validate_environment()` warns when `API_PUBLIC_URL` isn't a bare https
  origin (providers ignore non-https one-click URIs).
- The reply email link says "View topic to unfollow" (it opens the topic;
  it doesn't unfollow).
- The legacy `EmailType.FORUM_DIGEST` now maps to the `forum_digest` list,
  so `forum_digest.html`'s `{{ unsubscribe_url }}` is no longer empty.
- The new settings block moved below `WAGTAILFORUM_SPAM_BACKEND`, rejoining
  that setting and its comment.
- `pytest apps/core apps/users packages/wagtail_forum apps/forum_host
  --create-db`: 3097 passed.
