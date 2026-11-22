---
status: pending
priority: p2
issue_id: "731"
tags: [blog, privacy, api, users]
dependencies: []
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

- [ ] An anonymous `GET` of blog comments returns no `first_name`/`last_name` for any author, and a `display_name` that is never `get_full_name()` (a test using a user with both names set).
- [ ] The owner's decision on blog post bylines is recorded here with its date.

## Work Log

### 2026-11-21 - Filed from the forum backend audit

- Found while confirming the reach of `docs/audits/2026-11-21-forum-backend.md` H1. P2: real names reach anonymous readers, but the app is not live and has one real user.

### 2026-11-22 - Owner decision

- Offered the forum rule for blog commenters, the owner answered "Forum rule". Blog post bylines (CMS staff) were not part of that question and are still open: the second acceptance criterion stands.

### 2026-11-22 - Owner decision on bylines

- Asked whether staff bylines should follow the forum rule or keep showing full names, the owner answered "Keep the naming rule": bylines follow it too. This settles the second acceptance criterion; the box is left for whoever completes the todo.
