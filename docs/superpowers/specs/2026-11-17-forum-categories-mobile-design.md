# Forum categories on mobile — design

Date: 2026-11-17. Status: draft for owner approval.
Builds on `docs/superpowers/specs/2026-10-28-forum-categories-design.md` (web and backend,
todos 665–681, all merged) and `docs/superpowers/specs/2026-11-02-forum-home-redesign-design.md`
(the current mobile forum home).

## 1. Intent

The owner's words: "I prefer the forum to look like a traditional forum with categories and
forums." The web forum index already shows categories (live: General with four forums,
Community with Show & tell). The Flutter app still shows one flat "Boards" card. This work
brings the category index to the phone.

The earlier decision to hide link forums and password forums from the app (2026-10-30) is
withdrawn. Owner, 2026-11-17: "We can build screens for them, that decision was made because
I was not focused on mobile aspect of the project."

## 2. Goals

1. The forum tab opens on a traditional index: each category is a header with its forums
   listed under it, in the order set in `/cms/`.
2. The index is the first thing on the forum tab (owner: "Yes, top").
3. A forum created or restyled in `/cms/` looks right on the phone without an app release:
   its name, description, icon and colour come from the server.
4. Link forums and password forums appear on the phone and work.
5. A member can collapse a category, and the choice follows their account between web and
   phone.

## 3. Non-goals

- Subforums (owner dropped them on 2026-10-28 and again on 2026-11-17).
- A category page (a screen listing one category). The web has none either.
- Changing `/forum/boards/`. Installed TestFlight builds call it; its keys and its rules
  (no links, no locked forums) stay exactly as they are.
- These per-forum extras that the feed already carries but the app does not show yet:
  the moderators line, the forum image, rules, themes, watch levels, the tracked unread
  count, topic templates, per-forum page size and default sort. Each can be a later slice.
- A "mark forum read" action on the phone.

## 4. Anti-goals

- An older installed build breaks or shows a locked forum's content.
- The phone shows anything about a locked forum beyond its name and description.
- The forum tab gets slower to open: no extra round trip before the index paints.
- A forum made in `/cms/` shows as a generic leaf row, as it does today.

## 5. How it works today

- `plant_community_mobile/lib/features/forum/forum_screen.dart`: the forum tab is one
  column. Order: Your season (signed-in only), Experts, Boards, Recent activity.
- `widgets/home/forum_boards_section.dart`: one `CanopyGroupedCard`, a row per board.
- `services/forum_api.dart` `fetchBoards()` calls `GET /forum/boards/`, a flat list.
  `models/forum_board.dart` has id, title, slug, description, topic and post counts.
- `providers/forum_providers.dart` `boardsProvider` also feeds the topic screen's header
  (`screens/forum_topics_screen.dart`) and the search screen's Board filter.
- `utils/board_identity.dart` hardcodes an icon and tone for five slugs. Any other slug
  gets a leaf and a hashed tone.
- Backend `GET /forum/categories/` (`CategoryListView`,
  `backend/packages/wagtail_forum/wagtail_forum/api/views.py`) returns
  `{results: [category]}`. A category has `id, title, slug, description, icon, colour,
  position, topic_count, post_count, last_post_at, has_unread, forums, links`. A forum row
  is the board shape plus `has_unread, is_locked, is_closed, icon, colour, can_post` and the
  extras in §3. Forums and links arrive as two separate lists with no shared position. A
  link row has `id, title, slug, description, link_url, track_clicks,
  click_count`. Categories with nothing visible are left out. Anonymous responses are
  edge-cached; signed-in ones are `private, no-store`.
- Password unlock: `POST /forum/boards/{slug}/unlock/` stores the unlock in the Django
  session (`services/forum_permissions.py` `remember_unlocked`, `unlocked_forum_ids`). The
  app signs in with a bearer token and keeps no cookies (no cookie handling found in
  `plant_community_mobile/lib/core` or `lib/services`), so an unlock made from the app
  would be forgotten on the next request.

## 6. Approaches

**A. The app reads `/forum/categories/` (chosen).** One feed, already built and tested for
the web, carries everything in §2. `/forum/boards/` is left alone for old builds. The app's
flat forum list (search filter, topic header) is derived from the same response, so the
forum tab makes one request for forums, as it does now.

**B. Add category fields to each `/forum/boards/` row and group in the app.** Smaller app
change, but it alters the feed old builds depend on and still has no links, no locked
forums and no unread marks. Rejected.

**C. A new mobile-only endpoint.** A second copy of the same rules to keep in step with the
web's. Rejected.

The owner was shown A and B on 2026-11-17 and raised no objection to A.

## 7. Design

### 7.1 Layout

New order on the forum tab: **Forums**, Your season (signed-in only), Experts, Recent
activity. The section title "Boards" goes; the category names are the headings.

```
GENERAL                                ⌄
┌──────────────────────────────────────┐
│ 🌿 Plant identification        ● ›  │
│    Name that plant                   │
│    12 topics · 80 posts · 2h ago     │
│ 💧 Care & problems               ›  │
│ …                                    │
└──────────────────────────────────────┘
COMMUNITY                              ⌄
┌──────────────────────────────────────┐
│ 📷 Show & tell                   ›  │
│ 🔒 Members' corner               ›  │
│ ↗  Seed swap site                    │
└──────────────────────────────────────┘
```

- One `CanopyGroupedCard` per category, under a header with the category's name, its emoji
  icon when set, and a collapse chevron. Rows keep today's design (accent tile, title,
  one-line description, counts, chevron, whole-row tap target of at least 48pt).
- Forum row additions: an unread dot when `has_unread`; the last activity time after the
  counts when `last_post_at` is set.
- Within a category, forums come first and links after them: the feed gives the two as
  separate lists.
- `is_closed` and `can_post` are parsed into the model but change nothing on screen in this
  work; the server already refuses a post to a closed forum.
- Loading, error and empty states keep today's patterns: a row-shaped skeleton, "Could not
  load forums." with Retry, "No forums yet."
- Follow `plant_community_mobile/docs/patterns/flutter-ui-design.md` and work in light and
  dark mode.

### 7.2 Icon and colour

For a forum row, in this order: the server's `icon` (an emoji) and `colour` (`sage`,
`pollen`, `bloom`, `orchid`, the same names as `CanopyTone`); else the hardcoded identity
for its slug; else today's leaf and hashed tone. Icon and colour fall back independently.
The same rule applies wherever `boardIdentity` is used (topic screen header, chips).

### 7.3 Link forums

A link row shows an external-link icon, title and description, no counts and no chevron.
Tapping opens the system browser with `url_launcher`. An untracked link opens `link_url`.
For a tracked link the app itself calls `/forum/links/{id}/go/` with the member's sign-in,
without following the redirect, and opens the address in the `Location` header. That counts
the click and also works for a link only members may see, which the browser alone (it has
no sign-in) would get a 404 for. If that call fails, the row opens `link_url`. Only `http`
and `https` are opened. No backend change.

### 7.4 Password forums

- A locked row (`is_locked`) shows a lock icon, the name and description, nothing else.
  The feed still sends a locked row's counts and colour; the app does not show them.
- Tapping it as a guest asks them to sign in, as other member-only actions do.
- Tapping it signed in opens an unlock screen: the forum's name, one password field,
  an Unlock button. Wrong password: an inline error. 429: "Too many tries. Try again in N
  minutes." from `Retry-After`. Success: the index refreshes and the forum opens.
- A topic list that answers 403 `forum_locked` (a link into a locked forum) shows the same
  unlock screen instead of an error. A single topic inside a locked forum keeps answering
  404, as a hidden topic does everywhere in this API; that rule is not changed.

**Backend change, so an unlock sticks for the app.** On success the unlock endpoint also
returns a signed unlock token. The app keeps it in secure storage and sends it back in a
request header on forum calls. The server accepts a token only when it is for the signed-in
member, for that forum, and made against the forum's current password; it expires after
30 days. Changing the forum's password ends it everywhere. Signing out or switching
account ends it on that phone, because the app deletes its copy; the server has no list
of tokens to cancel. The
web's session unlock is unchanged. The one place that reads the session unlock
(`_visible_rows` in `api/views.py`) honours both. Tokens are never accepted on anonymous
requests.

Reach, the same as a web unlock today: it opens the forum's topic lists, topics, posts and
search through the REST API. Notifications, push and live replies stay off for a password
forum (those paths skip it on purpose, for web sessions too), and that is not changed here.

One thing must be fixed for this to hold. The live socket answers a topic in a password
forum with close code 4404 (`apps/forum_host/consumers.py`, `_topic_is_visible`), and the
app reads 4404 as "this topic is gone" (`live/forum_live_client.dart`). A member reading a
topic they unlocked must not be told it was removed. Either the app does not open the
socket for a topic in a password forum, or the server closes it the way it does when live
updates are off (4503); the builder picks, and §10 has the check.

Posting in an unlocked forum is expected to work: topic create resolves the forum with
`_get_board(slug, request)` and replies resolve the topic with
`visible_topics(request=request)`, the same request-scoped checks the token feeds. The
builder confirms this with a test instead of taking it on trust.

The app does not send the token on `/forum/sync/`, so an unlocked forum's topics are never
written to the on-device offline copy, which is not cleared on sign-out.

This is permission code: no cheap-worker tools on it, and it gets its own tests for a
wrong member, a wrong forum, a changed password, an expired token and a guest.

### 7.5 Collapsing

Tapping a category header collapses or expands its card. A collapsed header shows an unread
dot when the category `has_unread`. Signed in, the list is read from
`collapsed_categories` on `/forum/me/profile/` and written with
`PUT /forum/me/collapsed-categories/` (the whole list), so it matches the web. The change
shows at once and is rolled back with a message if the save fails. For a guest it is kept
on the device only.

The forum tab does not fetch the profile today. It is fetched alongside the categories, not
before them; the index paints from a copy of the list kept on the device and corrects
itself when the profile arrives.

### 7.6 Data in the app

- New models for a category, a forum row and a link row; the forum row extends what
  `ForumBoard` has.
- `ForumApi.fetchCategories()` and a `categoriesProvider`. `boardsProvider` stays as the
  flat list of unlocked forums but is derived from `categoriesProvider`, so its three users
  keep working and one request serves both. `fetchBoards()` and the `/forum/boards/` call
  leave the app.
- Everything that invalidates `boardsProvider` today (pull to refresh, Retry, the topic
  screen's refresh) invalidates the categories instead.
- New: sign-in, sign-out and account switch also invalidate the categories. Today
  `_resetForViewer` in `forum_screen.dart` leaves boards alone because the flat list is the
  same for everyone; this feed is per member (unread, locked).

## 8. Slices

Each is one PR that leaves the app working.

1. **Category index.** The feed, models and providers; headers; the new section order;
   icon and colour from the server; unread dot and last activity. Links and locked forums
   are not shown yet.
2. **Link forums.** §7.3.
3. **Password forums.** §7.4: backend token first, then the row and the unlock screen.
4. **Collapsing.** §7.5.

## 9. Constraints

- `/forum/boards/` response and behaviour unchanged (§3).
- Riverpod 3 patterns per `plant_community_mobile/docs/patterns/riverpod.md`; codegen
  output committed.
- The forum home keeps its single-Column structure (see the comment in `forum_screen.dart`
  on why sections are not lazy list children).
- No destructive commands, feature branch and PR per slice, per the repo `CLAUDE.md`.

## 10. Verification

- `flutter analyze` and `flutter test` clean; widget tests for: two categories render in
  order; an empty feed; server icon and colour win over the slug map; unread dot; link row
  opens the right address for tracked and untracked; locked row leads to the unlock screen;
  wrong password and 429 messages; collapse survives a reload and rolls back on failure.
- More widget and unit tests: the categories refetch on sign-in, sign-out and account
  switch; a locked row shows no counts; a tracked link falls back to `link_url` when the
  go call fails; a topic list answering 403 `forum_locked` shows the unlock screen; the
  unlock token is not sent on `/forum/sync/`; opening a topic in an unlocked password
  forum never shows the "topic removed" state.
- Backend tests for the unlock token (§7.4), including a topic create and a reply with a
  valid token, and a test that `/forum/boards/` output is unchanged.
- On the simulator against live data: General and Community show as on the web, in both
  light and dark mode.
- Owner check on a TestFlight build before each slice is called done.

## 11. Decisions

Owner:

- Traditional index of categories and forums on the phone (2026-11-17).
- Link forums and password forums get phone screens (2026-11-17).
- The index goes at the top of the forum tab (2026-11-17).

Proposed by Claude, for the owner to check:

- The app reads `/forum/categories/` (approach A).
- Unlocks reach the app as a signed token that lasts 30 days and ends on sign-out, account
  switch or a password change.
- Forum rows show the last activity time; the moderators line, forum image and the other
  extras in §3 wait.
- Guests' collapsed categories are kept on the device only.
- An unlock on the phone reaches what a web unlock reaches: reading and (to be confirmed by test) posting, but no
  notifications, push or live replies from a password forum, and nothing kept offline.
- A single topic in a locked forum stays "not found"; only a forum's topic list leads to
  the unlock screen.
- A tracked link is counted by the app calling the server, then opened in the browser.
- Closed forums look the same as open ones on the index for now.
- Slice order in §8.

## 12. Left to the builder

- Exact header typography and spacing within Canopy tokens; the collapse animation.
- The header name and token format for the unlock token, and where it is attached in the
  API client.
- Whether the tracked link row shows its click count, matching what the web does.
- File and class names.
