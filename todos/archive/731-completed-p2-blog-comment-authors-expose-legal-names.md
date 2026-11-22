---
status: completed
priority: p2
issue_id: "731"
tags: [blog, privacy, api, users]
dependencies: []
triage: ready
triaged: 2026-11-22
---

# Blog comment authors expose members' legal names to anonymous readers

## Problem

Anyone, signed in or not, can list approved blog comments. Each comment
embeds its author through `UserSerializer`, which returns `first_name`,
`last_name`, and a `display_name` that prefers the full name. Sign in with
Apple, Google or Firebase copies the provider's name into `first_name`, so a
member who comments shows up to anonymous readers under their legal name. The
forum had the same leak (audit 2026-11-21 H1). There, the owner decided that a
public name is the chosen display name, else the username, and never the full
name.

## Findings

- `backend/apps/blog/views.py`: `BlogCommentViewSet` has `permission_classes = [permissions.IsAuthenticatedOrReadOnly]` and lists `BlogComment.objects.filter(is_approved=True)`. It is routed at `blog/comments/` (`apps/blog/urls.py:18`).
- `backend/apps/blog/serializers.py:178-181`: `BlogCommentSerializer.author = UserSerializer(read_only=True)`. That `UserSerializer` (blog `serializers.py:114`, and the users one at `apps/users/serializers.py:100`) includes `first_name`, `last_name` and `display_name`, and `User.display_name` returns `get_full_name()` first (`apps/users/models.py:268-272`).
- The name source is `apps/users/firebase_auth_views.py:773-775, 824` and the OAuth adapters (`given_name`/`family_name`).
- Blog *post* authors (`BlogPostPageSerializer`, `apps/blog/api/serializers.py:239-241, 357-359, 566`) are CMS staff. Owner decision 2026-11-22: bylines follow the same rule as members (chosen name, else username, never the legal name).
- Found 2026-11-21 while checking the H1 fix's reach. Out of the forum audit's scope, so not fixed there.

## Recommended Action

1. Owner decision 2026-11-22: blog commenters follow the forum rule (chosen name, else username, never the legal name).
2. Give comment authors a public author serializer with no `first_name`/`last_name`, and a `display_name` that follows that rule. Keep the full `UserSerializer` for the user's own profile endpoints.
3. Apply the same rule to blog post bylines (`BlogPostPageSerializer` author fields), per the owner's 2026-11-22 decision.
4. Grep every other public use of `UserSerializer` and `User.display_name` (blog post list/detail, any follower or following lists), and apply the same rule there, staff included.

## Acceptance Criteria

- [x] An anonymous `GET` of blog comments returns no `first_name`/`last_name` for any author, and a `display_name` that is never `get_full_name()` (a test using a user with both names set).
- [x] The owner's decision on blog post bylines is recorded here with its date.

## Work Log

### 2026-11-21 - Filed from the forum backend audit

- Found while confirming the reach of `docs/audits/2026-11-21-forum-backend.md` H1. P2: real names reach anonymous readers, but the app is not live and has one real user.

### 2026-11-22 - Owner decision

- Offered the forum rule for blog commenters, the owner answered "Forum rule". Blog post bylines (CMS staff) were not part of that question and are still open: the second acceptance criterion stands.

### 2026-11-22 - Owner decision on bylines

- Asked whether staff bylines should follow the forum rule or keep showing full names, the owner answered "Keep the naming rule": bylines follow it too. This settles the second acceptance criterion; the box is left for whoever completes the todo.

### 2026-11-22 - Implemented by the todo sweep (run 2026-11-22-1957)

- New `User.public_name` (`backend/apps/users/models.py`): the forum display name, else the username, via `wagtail_forum.api.serializers.forum_display_name`, the same resolver as the forum H1 fix. `User.display_name` is unchanged: only the member's own profile and the register/login responses use it.
- Blog `UserSerializer` (`backend/apps/blog/serializers.py`; comments, post list/detail, author pages: all public) drops `first_name`/`last_name` and serves `display_name = public_name`. The Wagtail API v2 bylines (`backend/apps/blog/api/serializers.py`, 3 sites) do the same, and the templates `blog/blog_post_page.html`, `blog/components/post_card.html`, `emails/blog_post.html` and the staff-only `blog/admin/search.html` read `public_name` (staff search changed too, for one rule). `emails/blog_post.html` still greets the recipient by their own `first_name`.
- Every `select_related("author")` feeding an author payload in `backend/apps/blog/views.py` (10), `api/serializers.py` (4) and `api/viewsets.py` (5) also joins `author__wagtail_forum_profile`, so the name costs no query per row. The seeded author page title reads `public_name` (seed users' forum names equal their seeded full names).
- Grep: no other public use of `UserSerializer` or `User.display_name` (no follower/following list endpoint exists; `apps/users` `UserSerializer` returns only the caller's own data). Web `web/src/types/blog.ts` drops the two fields; the `blogService.test.ts` fixture's author changed shape with it.
- Tests: `backend/apps/blog/tests/test_comment_author_privacy.py` (anonymous comments with a reply, v1 and v2 post list/detail bylines, the rule itself); all 4 fail when `public_name` falls back to `get_full_name()`.

### 2026-11-22 - Verified by the todo sweep (run 2026-11-22-1957)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 2 -- backend/venv/bin/python -m pytest backend/apps/blog/tests/test_comment_author_privacy.py -v -p no:cacheprovider --create-db` — evidence `.sweep-evidence/g2/731-ac0.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 4 passed, 3 warnings in 20.98s ========================
  ```

- AC 2: `grep -n "Owner decision 2026-11-22: bylines\|Owner decision on bylines\|Keep the naming rule" todos/archive/731-completed-p2-blog-comment-authors-expose-legal-names.md` — evidence `.sweep-evidence/g2/731-ac1.txt` (not committed), last lines:

  ```text
  29:- Blog *post* authors (`BlogPostPageSerializer`, `apps/blog/api/serializers.py:239-241, 357-359, 566`) are CMS staff. Owner decision 2026-11-22: bylines follow the same rule as members (chosen name, else username, never the legal name).
  54:### 2026-11-22 - Owner decision on bylines
  56:- Asked whether staff bylines should follow the forum rule or keep showing full names, the owner answered "Keep the naming rule": bylines follow it too. This settles the second acceptance criterion; the box is left for whoever completes the todo.
  ```

### 2026-11-22 - Completed by the todo sweep (run 2026-11-22-1957)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-22 - Review round 1: non-blocking findings

Round 1 was clean (no blocking findings). The non-blocking ones, each fixed or declined:

- **Fixed: cached responses kept legal names for up to 24 h (medium, two reviewers).** v2 post
  detail and list responses are cached under `blog:post:v2` / `blog:list:v2`, so entries cached
  before deploy would have kept serving `first_name`/`last_name`. Bumped `CACHE_PREFIX_BLOG_POST`
  and `CACHE_PREFIX_BLOG_LIST` to v3, `CACHE_PREFIX_BLOG_CATEGORY` to `blog:category:v2` and
  `CACHE_PREFIX_POPULAR_POSTS` to `blog:popular:v2`. New test
  `test_a_post_cached_before_the_fix_is_not_served` seeds an old-key, legal-name entry and checks
  it is not served. Mutation check: with the post prefix set back to v2 the test fails; restored,
  privacy + cache-service tests 23 passed.
- **Fixed: comment fixture modelled the old payload (low).** `blogCommentService.test.ts` no
  longer has `first_name`/`last_name`; `display_name` is the username. Vitest 37 passed.
- **Declined: untested author-page, index and category paths (medium/low).** A grep of
  `apps/blog` (non-test, non-migration) finds no remaining `first_name`, `last_name` or
  `get_full_name` in any author payload. Every byline goes through `User.public_name`. The one
  `first_name` left is `BlogNewsletter`'s own field, used to greet the recipient.
- **Declined: a rename shows for up to 24 h in cached bylines (low).** That is the normal cache
  staleness for any byline. The old name was the member's own chosen name, not a legal name.
- **Declined: `public_name` imports a forum serializer module (low).** It is a function-local
  import of the single forum naming rule. Moving it would duplicate the rule the owner wants
  shared.
- **Declined: whitespace-only template edits (low).** They come from the trailing-whitespace and
  end-of-file pre-commit fixers.
- **Declined: N+1 flatness test for `select_related` (low), demo seed titles use the username
  (low, intended per the naming rule), no unit test for ForumCard's `data-testid` (belongs to
  #1408).**

### 2026-11-22 - Review round 2: non-blocking findings

- **Declined: a forum rename leaves cached bylines stale up to the TTL (low, three reviewers).**
  As in round 1, the cached value is the member's own chosen name, and main had the same gap.
- **Declined: existing BlogAuthorPage titles may hold a legal name (low).** Those titles are
  editorial content typed by staff, not copied from the provider. This PR changes only computed
  author payloads. Staff can retitle a page in /cms/.
- **Declined: admin search does one more query per row (low).** Staff-only page, at most 20
  rows.
- **Declined: `apps/users/constants.py` comment still shows `blog:post:v2` (low).** It is a
  format example.
- **Declined: `public_name` imports a forum serializer module (low).** Same as round 1.
