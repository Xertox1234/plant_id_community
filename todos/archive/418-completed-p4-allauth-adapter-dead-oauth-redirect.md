---
status: completed
priority: p4
issue_id: "418"
tags: [backend, users, auth, dead-code]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
source_finding: "slice 4 discovery"
triage: needs-design
triaged: 2026-10-02
blocked_on: "Owner re-decides with the new fact: the social adapter's get_login_redirect_url is dead code allauth never calls, so option (b) as worded cannot change any redirect"
owner_decision: "Option (b): keep the allauth social routes and derive the provider from the sociallogin (2026-09-28); re-decided 2026-10-02: allauth never calls CustomSocialAccountAdapter.get_login_redirect_url (the ACCOUNT adapter answers), so keep the routes and delete the dead override plus the pinned SocialLoginRedirectTests test (2026-10-02)"
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

- [x] The allauth social redirect is either removed or returns a supported
      provider's callback, with a test that drives it.

## Work Log

### 2026-09-23 - Filed from todo 405 slice 4 discovery

Found while moving `reverse("users:oauth_callback")`. That name was registered
only by the removed legacy `/api/` mount.

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Deleted `CustomSocialAccountAdapter.get_login_redirect_url` and its
  `reverse` import (owner decision 2026-10-02). Verified against allauth
  65.19.2: no `socialaccount` module defines or calls
  `get_login_redirect_url`; `complete_social_login` ends in `perform_login`,
  whose redirect comes from `allauth.account.utils.get_login_redirect_url`,
  and that asks the ACCOUNT adapter (`CustomAccountAdapter`, which answers
  `/`). The social adapter's class docstring now says so.
- Deleted the pinned `SocialLoginRedirectTests` from
  `apps/core/tests/test_legacy_api_mount_removed.py`: it drove the dead
  override directly, with a hand-set `request._oauth_provider`, so it was the
  only caller the override ever had.
- New `SocialLoginRedirectTest` in `apps/users/tests/test_allauth_surface.py`
  drives the real chain: the account adapter allauth resolves is ours and
  returns `/`, `DefaultSocialAccountAdapter` has no login-redirect hook, and
  `CustomSocialAccountAdapter` no longer overrides one. That is the "removed"
  arm of the acceptance criterion, with the test that drives it.
- The allauth `/accounts/` routes stay mounted, as decided (todo 447 relies on
  the password reset).

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py 1 -- backend/venv/bin/python -m pytest apps/users/tests/test_allauth_surface.py apps/core/tests/test_legacy_api_mount_removed.py --create-db` — evidence `.sweep-evidence/g1/418-ac0.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ============= 33 passed, 3 warnings, 27 subtests passed in 18.84s ==============
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
