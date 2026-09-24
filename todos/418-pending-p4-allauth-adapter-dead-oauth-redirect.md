---
status: pending
priority: p4
issue_id: "418"
tags: [backend, users, auth, dead-code]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
source_finding: "slice 4 discovery"
---

# allauth social adapter: its post-login redirect is unreachable, and broken if reached

## Problem

`CustomSocialAccountAdapter.get_login_redirect_url()`
(`backend/apps/users/oauth_adapters.py`) sends allauth's post-login redirect to
`/api/auth/oauth/<provider>/callback/`, taking `provider` from
`request._oauth_provider`. **Nothing sets that attribute.** A grep of
`backend/` finds only the `getattr(..., "unknown")` read, so the redirect is
always `/api/auth/oauth/unknown/callback/`. `oauth_callback` 400s on any
provider that is not in `SUPPORTED_PROVIDERS`.

It does not break sign-in today, because the real flow never reaches it.
`oauth_login` builds Google's authorize URL itself, with
`redirect_uri=<host>/api/auth/oauth/google/callback/`, and does not go through
allauth. The adapter is reachable only via allauth's own `/accounts/<provider>/`
routes, which no client uses. Production had 0 requests to
`/api/auth/oauth/unknown/callback/` in the 7 days to 2026-09-24 (Railway
`http-requests`).

## Recommended Action

Decide whether allauth's social-login routes are needed at all.

- If not, drop `SOCIALACCOUNT_ADAPTER` or the whole `accounts/` mount, and
  whatever allauth pieces only it uses.
- If they are needed, derive the provider from the social login
  (`sociallogin.account.provider`, via `pre_social_login`/`save_user`) instead of
  a request attribute nobody sets.

## Technical Details

- `backend/apps/users/oauth_adapters.py` (`get_login_redirect_url`)
- `backend/apps/users/oauth_views.py` (`oauth_login` builds its own redirect URI)
- `backend/plant_community_backend/settings.py` (`SOCIALACCOUNT_ADAPTER`)
- `backend/plant_community_backend/urls.py` (`accounts/` mount)
- Todo 405 slice 4 moved the reverse to the root `oauth_callback` name, keeping
  the emitted URL byte-identical. It is pinned in
  `apps/core/tests/test_legacy_api_mount_removed.py`.

## Acceptance Criteria

- [ ] The allauth social redirect is either removed or returns a supported
      provider's callback, with a test that drives it.

## Work Log

### 2026-09-23 - Filed from todo 405 slice 4 discovery

Found while moving `reverse("users:oauth_callback")`. That name was registered
only by the removed legacy `/api/` mount.
