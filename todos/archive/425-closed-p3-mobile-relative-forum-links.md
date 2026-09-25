---
status: closed
resolution: wont-fix
priority: p3
issue_id: "425"
tags: [forum, flutter, mobile]
dependencies: ["424"]
---

# Relative links in forum posts can't open on mobile

## Problem

Todo 424 made forum links open in the in-app browser, but only for absolute
`http`/`https` URLs (`openableForumLink` in
`plant_community_mobile/lib/features/forum/services/forum_link_launcher.dart`).
A relative href such as `<a href="/forum/topics/3/">` shows "Couldn't open
this link." on mobile, while the web opens it against its own origin.

The server keeps relative hrefs. `sanitize_rich_text`
(`wagtail_forum/api/sanitize.py`) limits schemes, and nh3 applies that only
to absolute URLs. So a body written through the API, the CMS, or an import
can hold one.

Raised by the bundled `/code-review` of todo 424 (low severity). Before 424
these links didn't open either: the app showed the raw href in a SnackBar.

## Findings

- It's unknown how often real posts hold relative links. Both composers write
  absolute links: the web's TipTap link dialog and the mobile
  `[text](url)` grammar, which `isAllowedForumLinkHref` limits to an
  absolute `http`/`https`/`mailto` URL. Check production first:
  `Post.objects.filter(body__icontains='href="/')`.
- The mobile app knows the API origin (`api.houseplant-md.com`), not the web
  origin that relative forum paths belong to. So a fix needs the web origin
  as config, or needs to map known paths (`/forum/topics/<id>/`) to in-app
  routes.

## Recommended Action

Count the relative links in production first. If there are none, close this
as won't-fix and keep the refusal. If there are some, choose one:

- resolve relative hrefs against a configured web origin, then apply the
  same http(s) check; or
- route `/forum/topics/<id>/` to the in-app thread screen and refuse
  everything else.

## Acceptance Criteria

- [x] The production count of posts holding a relative href is recorded here.
- [x] Either a decision to keep the refusal (with that count as the reason),
      or a fix pinned by a widget test that a relative forum link opens or
      navigates.

## Work Log

### 2026-09-24 - Filed from todo 424's review

### 2026-09-24 - Owner action needed: production count

The count is a production read, which the auto-mode classifier denies an
agent. Owner step: run the read-only query given in the session (counts posts
whose body holds `href="/`) and record the number here. Zero → close as
won't-fix; non-zero → a sweep routes `/forum/topics/<id>/` in-app.

### 2026-09-24 - Production count: 0 — closed, keep the refusal

Production read (`railway ssh` → `manage.py shell`): **0 of 148** forum posts
hold a relative href (`href="/`). Decision per AC 2's first branch: keep the
mobile http(s)-only refusal; there is nothing to route. Reopen if a relative
link ever appears in a post.
