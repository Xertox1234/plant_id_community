# Forum home redesign (mobile) — design

Date: 2026-11-02 · Owner: Will Tower · Status: draft for owner approval

Approved mockup: [`2026-11-02-forum-home-redesign-mockup.html`](2026-11-02-forum-home-redesign-mockup.html)
(open it in a browser; the text-only activity cards expand on tap). Where this document and
the mockup disagree, this document wins: the mockup's numbers, board descriptions and
reply text are placeholders.

## 1. Intent

The owner's words: the Flutter forum home "feels green and crammed together". The boards
"appear jammed together", Recent activity "appears as if no thought at all went into" it,
there is no logo or branding, no footer, and none of the community stats most forums show
on their front page. The "Your season" block in the hero position is liked and stays.

This matches the on-device audit in `plant_community_mobile/docs/patterns/flutter-ui-design.md`
Part 1b: §2 "Everything is one teal … The five forum boards are five identical text rows"
and §3 "No brand presence". The fix direction written there is followed here.

The redesign is for the person who opens the Forum tab several times a day: they want to
see at a glance where things are happening and catch up on busy topics without opening
each one. The owner's reason for the expanding cards: "sometimes a topic gets multiple
replies and I think this is a good way to keep that under control."

## 2. Goals

1. The screen stops reading as one shade of green, using Canopy's own accents (pollen,
   bloom, orchid, sage) on small elements: board icon tiles, board chips, the streak
   number, unread dots.
2. Brand presence: the Houseplant MD mark in the app bar and in a footer.
3. Room to breathe: sections clearly separated, boards and activity grouped instead of
   stacked loose cards.
4. Recent activity that tells you what is happening: board, reply count, last activity,
   unread, solved, a photo when the topic has one, and the latest replies on demand.
5. A "Who's online" panel with community stats, members only.

## 3. Non-goals

- Guest (anonymous visitor) counts. Owner decision 2026-11-02: "a lot of work for very
  little gain". Guest forum reads are publicly cached, so a server-side count would
  undercount, and counting would put a write on the cached read path, which
  `docs/rules/caching.md` forbids.
- Footer links. None of Guidelines, About, Privacy or Terms exist as pages on web or
  mobile today. Owner decision: the footer ships with the logo, tagline and copyright only
  "for now". Adding the pages is separate work.
- The board topic list, topic detail, search, bookmarks, DMs and notification screens.
  Only the Forum tab's home screen (`lib/features/forum/forum_screen.dart`) is redesigned.
- The web forum. No web changes, except that the board identity map is copied from the web
  (§6.1).
- Token changes. Canopy tokens are generated from `web/src/index.css` and pinned by
  `test/core/theme/canopy_parity_test.dart`; nothing here edits them.

## 4. Anti-goals (would make this a failure even if it works)

- Accent colour on large surfaces or body text (Canopy: accents on small elements only).
  Swapping "all green" for "all colours" is not the goal.
- A forum home that loads slower than today. The expanded-card replies load on tap, never
  up front.
- The camera FAB covering the last activity card, the Who's online panel or the footer
  (the bug fixed in #1174; see flutter-ui-design.md Part 1b §1).
- Text that clips or overlaps at 320pt width or 2.0× text size.
- A red cross on a white or light ground anywhere (binding brand constraint, `BrandMark`).
- An online panel that shows members a viewer has blocked.

## 5. Layout, top to bottom (owner-approved: direction A with B's Recent activity)

1. **App bar.** `BrandMark` (small) + "Community" title left-aligned, then the existing
   search, bookmarks, messages and notifications buttons with their badges unchanged.
2. **Your season** (signed-in only, as today). One `CanopyCard` with a faint leaf
   watermark, a Geist Mono eyebrow "YOUR SEASON", four stats in one row separated by
   hairlines (IDs, Posts, Solutions, Day streak, the streak number in pollen), and the next
   badge as a labelled progress bar ("Botanist badge · 0 / 20 IDs"). Same data as today's
   `ForumStatsGrid` (`meStatsProvider`); the earned-badge chips stay underneath when present.
3. **Experts** (as today, `expertsProvider`, self-hides when empty): larger avatars with the
   online dot, "· N online" after the heading.
4. **Boards.** One grouped `CanopyCard` with hairline dividers between rows. Each row: a
   40pt accent icon tile (§6.1), title, one-line description, "N topics · N posts" in Geist
   Mono, chevron. The whole row is the tap target.
5. **Recent activity** with a "View all" link (target: §6.4). Separate cards, one per topic,
   10 topics maximum (today's cap):
   - **Picture card** (the topic has an image): board chip, title in the display face, a
     wide photo, reply count and time. Tapping opens the topic. It never expands.
   - **Text card** (no image): board chip, unread dot or "Solved" tag, title, reply count,
     time, "New replies" when unread, and a chevron. Tapping expands it in place (§7).
6. **Who's online** (§6.3): members online now with a live dot, registered members, an
   avatar cluster of up to 5 online members with a names line, then "N topics · N posts" and
   "Newest: name".
7. **Footer.** `BrandMark`, "Houseplant MD", the "THE PLANT CLINIC" eyebrow, "© 2026 Houseplant
   MD". No links (§3). The year comes from the clock, not a literal.

Signed out: Your season is hidden (as today); everything else shows. Who's online and the
recent feed are public reads.

### 5.1 Light mode (owner: "let's also not forget about light mode")

Light mode is a first-class target: every section is built, tested and checked on the simulator in
both modes. The mockup shows both side by side. Everything comes from `CanopyColors.light` via
`context.canopy` / `colorScheme`, with no per-mode hex in widgets:

- Ground `CDE9D4`, cards on the light card gradient (`FDFFFD → F2FAF4 → E9F5EC`), lighter shadows
  (the light `shadowAlphas`), hairlines in sage at 38/62% alpha.
- **Accents use the darkened light-mode set**, not the dark-mode pastels: leaf `3C6B50` (sage),
  clay `8A6011` (pollen), berry `B0503A` (bloom), sky `6B4FA0` (orchid). Board tiles, chips, the
  streak number and unread dots read through the same semantic mapping in both modes, so no widget
  picks a tone by brightness itself.
- Foreground on accent fills (avatars, badges) flips to the light ink `F2FAF4`, matching the
  palette's `onClay`/`onError`.
- "Open topic" uses the light CTA gradient (`163832 → 235347`, `ClayButton` already does this).
- **`BrandMark` keeps its deep-pine tile in light mode, in the app bar and the footer.** The coral
  cross must never sit on a light ground (binding brand constraint). Verify both placements in a
  light-mode golden.
- Contrast is checked in light mode separately: ink3 (`5E8271`) meta text on the near-white card,
  the darkened accents on their 12–17% tinted tiles, and the chip labels, each at least 4.5:1
  (3:1 for the large stats). Fix a failing pair by using ink2 or the accent at full strength, not
  by adding new colours.

## 6. Data

### 6.1 Board identity (no backend change)

Copy the web's map from `web/src/utils/forumTones.ts` into a Dart helper so web and mobile
match:

| Board slug | Tone | Icon (Lucide) | Chip label |
|---|---|---|---|
| `plant-identification` | sage | leaf | Identification |
| `care-problems` | pollen | droplet | Care |
| `pests-diseases` | bloom | bug | Pests |
| `garden-design` | orchid | layout-dashboard | Design |
| `show-tell` | sage | camera | Show & tell |

Unknown slugs: tone from the same string hash the web uses (`web/src/utils/hashString.ts`,
same tone order sage/pollen/bloom/orchid) so a board gets the same colour on both platforms,
leaf icon, chip label = board title.

The five slugs match `apps/forum_host/seed_content.py`. Prod has six forums (ids 11–16, from
the categories work, todos 665–681), so at least one prod board will use the fallback.
**My call:** the builder confirms the live slugs on the simulator during the on-device check
(the app is already signed in against prod there; no direct prod database or API access).
If a prod slug differs from the seed, or a sixth board reads badly with the fallback, report it
to the owner. Giving it a deliberate identity changes web `forumTones.ts` and this map
together, as a separate small change. This redesign does not edit the web.

### 6.2 Recent activity feed (backend: extend an existing endpoint)

Switch the home's Recent activity from the offline sync stub (`recentTopicsProvider`,
`ForumTopicStub`: id/slug/title/updatedAt only) to `GET forum/topics/recent/?limit=10`
(`RecentTopicsView`, already used by the web rail). It already returns board, reply count,
last-post time, pinned and an 80×80 thumbnail, and is already block- and mute-aware.

Add to each row:

- `is_solved` (bool)
- `is_unread` (bool; always `false` for anonymous). The view already serves authenticated
  responses `private, no-store` (`PublicForumReadCacheMixin`), so a per-user field cannot
  leak into the shared anonymous cache. Use the same read-state source the board topic
  list uses for `is_unread`, batched, no per-row queries.
- `image_url`: a wide rendition for the picture card (e.g. `fill-720x400`), prefetched in
  the same batch as the existing `fill-80x80`. Keep `thumbnail_url` for the web rail.
  With no uploaded image, it falls back to the first link card's cached preview image
  (owner decision 2026-11-03); `thumbnail_url` stays uploads-only.

Keep the offline sync mirror as is. It still feeds offline reading. The home just stops
using it for this list; if the recent request fails, show the section error with Retry
(today's behaviour).

Update `RECENT_TOPICS_SCHEMA` and the web `RecentTopic` type comment so the OpenAPI contract
stays accurate. The web ignores the new fields.

### 6.3 Who's online + community stats (backend: new endpoint)

New public endpoint, e.g. `GET forum/community/stats/` in the `wagtail_forum` package:

```json
{
  "members_online": 3,
  "online_sample": [ /* up to 5 serialize_forum_author() rows */ ],
  "registered_members": 148,
  "topic_count": 19,
  "post_count": 72,
  "newest_member": { /* serialize_forum_author() row */ }
}
```

- Online = `ForumProfile.last_seen` within `effective_online_window_seconds()` (15 min by
  default), the same rule the Experts dot uses. `last_seen` only moves on authenticated
  forum API requests, throttled to once per 5 min; that is accepted.
- **Counts are site-wide, not per viewer (my call).** `topic_count` and `post_count` cover
  live topics and posts in fully public boards only: boards with no permission grant and no
  password (todo 680). The panel is then one number for everyone, never reveals that private
  forums are active, and caches as a single value. `members_online` and `registered_members`
  are site-wide member counts (active accounts with a `ForumProfile`; document the definition
  in the schema). Viewer-specific board visibility is deliberately not applied to these totals.
- `online_sample` and `newest_member`: exclude inactive accounts, and per request exclude
  members the viewer has blocked (`_exclude_blocked_authors` semantics). When the newest member
  is blocked, show the next newest. Muted members are excluded the same way (my call: mute
  already hides a member from Experts, so it hides them here too).
- Cache the counts server-side for about 60 s as one shared value. Build the sample and the
  newest member per request after the block/mute filter, or shared-cache only the anonymous
  response, as `PublicForumReadCacheMixin` already does. A per-viewer filter must never reach
  the shared cache.
- Rate-limit like the other public forum reads.
- On error or while loading, the panel hides (same self-hiding behaviour as Experts), so
  the home never shows a broken stats box.

### 6.4 Latest replies for an expanded card (backend: new endpoint)

Posts paginate oldest-first only (`PostCursorPagination`), and the global `?ordering=` was
deliberately disabled (views.py around line 648), so "latest 3" needs its own read, e.g.
`GET forum/topics/{id}/latest-replies/`:

```json
{
  "replies": [ /* up to 3 newest live replies (not the opening post), newest first:
                  id, author (serialize_forum_author), created_at, excerpt */ ],
  "solution": { /* the accepted answer in the same shape, or null */ },
  "participant_count": 3,
  "participants": [ /* up to 5 authors */ ],
  "started_by": { /* author */ }
}
```

- Hard maximum of 3 replies (owner decision 2026-11-02). Excerpt: plain text built from the
  post body by the same helper the mobile app already uses for previews, about 160
  characters, server-side so the client doesn't download full bodies.
- Visibility: 404 if the viewer cannot see the topic, using the topic detail's own check.
  Does not mark the topic read (it is a peek).
- **Blocked and muted members are hidden from the peek, not shown collapsed (my call).** The
  topic's own post list annotates blocked authors (`_annotate_author_blocked`) and lets the
  reader "show anyway"; mute is not applied there at all. The peek is a home-screen summary
  like the recent feed, which already hides blocked authors' topics, so it follows the hide
  style: replies, the solution and participants from members the viewer blocked or muted are
  left out (`_exclude_blocked_authors` semantics, plus the mute filter the Experts list uses).
  No `is_blocked` flag is needed in the response. If the solution's author is hidden, the
  card shows only the newest visible replies, with no Solution tag. `started_by` cannot be
  blocked in practice, because the recent feed already drops blocked authors' topics. If it
  is (the block happened after the feed loaded), omit "started by".
- "+N more replies" = the topic's visible reply count minus the replies shown, computed
  server-side as `more_count` after the same filter, so hidden replies are never counted.
  Add `more_count` to the response.
- Solved topic: show `solution` first, tagged "Solution", then the newest replies up to 3
  items in total.
- `replies` empty (a topic with no replies yet): the card shows "No replies yet" and the
  Open topic button.

Client: a family provider keyed by topic id, fetched on first expand, kept while the screen
is alive, refreshed by pull-to-refresh.

## 7. The expanding card (owner-approved)

- Tap a text card: it expands in place and the cards below move down. Tap the card again
  to collapse it. **One card open at a time** (my call, to keep the list under control);
  opening another collapses the first.
- Expanded content: up to 3 replies (poster avatar, name, relative time, about two lines of
  excerpt), the participant avatars with "N people in this thread · started by name", and
  an "Open topic" `ClayButton`. If the topic has more replies than shown: "+N more replies"
  above the button.
- While replies load: two shaped skeleton lines in place of the replies, not a spinner.
  On failure: one line "Couldn't load replies" with Retry; the Open topic button still works.
- Accessibility: the card announces as a button with expanded/collapsed state; "Open topic"
  is its own control.

## 8. Design record (crafting-ui parts 2–4)

The direction is the project's design system, Canopy (`docs/superpowers/specs/2026-08-13-canopy-design.md`:
"liveliness comes from light, not noise"). No new direction is invented; part 1 of the
crafting-ui record is skipped as that skill allows when a project brief exists. Honest note: the
owner's "too green" complaint is partly the system itself (one green world). This design answers it
inside Canopy's rules (accents on small elements). If it still reads as too green on device, the
next step is an identity pass on Canopy's surfaces, raised with the owner, not more colour here.

### 8.1 Concept → everything people touch

- **Section headings:** display face (Bricolage Grotesque 600); counts in Geist Mono.
- **Board rows:** grouped list, accent tile carries the board's identity; pressed = row
  highlight (surface3), not scale.
- **Activity cards:** pressed = slight scale (0.98) with the existing spring; chevron rotates
  on expand.
- **Loading:** skeletons shaped like the real rows for boards and activity (replace the
  centred spinners on this screen).
- **Empty:** "No boards yet." / "Nothing here yet." stay, styled as Canopy empty lines with
  the leaf mark.
- **Error:** today's message + Retry per section.
- **Footer:** quiet, centred, on the ground colour with a faint gradient.

### 8.2 Moments and their budget

| Moment | How often | Meaning | Budget |
|---|---|---|---|
| Scrolling the home | Many times a session | Browsing | None. No entrance animation on scroll |
| Press a board or card | Many times a session | "I'm going there" | Highlight/scale only, ≤100 ms, no overshoot |
| Expand/collapse a card | A few times a session | "Show me what's new" | Short and settled: size + fade, about 250 ms |
| Replies arrive | Once per expand | Content ready | Cross-fade from skeleton, about 150 ms |
| First open of the screen | Once per visit | Arriving | Allowed: one staggered fade-in of sections, 40 ms stagger, skipped on refresh |

### 8.3 Motion plan

| Element | Trigger | What changes | Easing | First | Haptic | Reduced motion |
|---|---|---|---|---|---|---|
| Text card | Tap | Height grows (`AnimatedSize`); content fades in after 80 ms | `Easing.emphasizedDecelerate`, ~250 ms | Height, then content | `selectionClick` | Instant size; content still fades (opacity only) |
| Other open card | Another card opens | Collapses at the same time | `Easing.emphasizedAccelerate`, ~200 ms | Content fades out first | none | Instant |
| Chevron | Expand/collapse | Rotates 180° | same as card | with height | none | Swap icon, no rotation |
| Skeleton → replies | Fetch completes | Cross-fade (`AnimatedSwitcher`) | `Durations.short4` | old out as new in | none | Kept (opacity only) |
| Card / row press | Pointer down | Scale 0.98 / row highlight | spring, no overshoot | — | none | Dim instead of scale |
| Sections | First build per visit | Fade + 8 pt rise, staggered 40 ms | `Easing.emphasizedDecelerate` | top first | none | Fade only |

All durations go through `MediaQuery.disableAnimationsOf(context)`. Interrupting an expand by
tapping again reverses it from where it is; taps are never queued.

### 8.4 States

idle · pressed · focus (keyboard/switch access) · loading (skeletons) · loaded · empty ·
section error with Retry · replies loading · replies failed · no replies · signed out (no Your
season, Who's online still public) · offline (sections show their error; the offline mirror
still serves topics elsewhere) · dark (primary) and light · reduced motion · text scale 2.0 ·
320pt width. Keyboard-up: n/a (no input on this screen).

## 9. Constraints (project rules that bind this work)

- `docs/rules/flutter.md`, `docs/rules/caching.md`, `docs/rules/api.md`, and the
  `flutter-ui-designer` agent rules: colours only from `colorScheme`/`context.canopy`, type
  from theme roles, `CanopyCard`/`ClayButton`/`BrandMark` rather than raw Material widgets.
- Riverpod 3 `Notifier`/`@riverpod` and regenerated `*.g.dart` for any provider change.
- New backend views get the `get_permissions()`/`super()` treatment if they use `@action`,
  OpenAPI schemas, query-count tests (`performance/query-optimization.md`: strict
  assertions), and block/visibility tests.
- The scroll view keeps `MainShell.fabClearanceOf(context)` padding so the footer clears the
  camera FAB.

## 10. Verification (what "done" means)

- Backend: tests for each new or extended endpoint covering visibility, blocks, mutes,
  anonymous vs signed-in, caching headers, query counts, the 3-reply limit, a solved topic and
  a topic with no replies.
- Mobile: widget tests at 320×640 and 375×812, text scale 1.0 and 2.0, dark and light, no
  overflow; the four accessibility guidelines; expand/collapse and one-open-at-a-time behaviour;
  reduced motion. Goldens for any new shared widget.
- On the iOS simulator: before/after screenshots of the whole home, an expanded card, a picture
  card, and the footer above the FAB, each in dark AND light mode.
- `flutter analyze` clean; backend tests run repo-wide (an app-scoped run is not enough here).

## 11. Decisions

**Owner's (2026-11-02):** direction A with B's Recent activity; B's picture card; A's Who's
online and footer; text cards expand on tap to show detailed activity; at most 3 latest
replies; footer without links for now; members only, no guest count; light mode gets the
same care as dark (§5.1).

**My calls (owner can override):** one card open at a time; 10 activity cards; a solution
counts toward the 3; blocked and muted members are hidden from the expanded card and the
online panel, not shown collapsed (§6.3, §6.4); Who's online totals are site-wide over fully
public boards (§6.3); live board slugs are checked on the simulator and a sixth board's
identity is a separate web+mobile change (§6.1); up to 5 avatars in the online sample; "View all" opens the existing forum
search sorted by latest activity if it supports that, otherwise the link is left out (builder
to check); skeletons replace spinners on this screen only.

## 12. Left to the builder

Exact endpoint paths and module placement in `wagtail_forum`; whether the new shared pieces
(accent tile, chip, grouped list card) live in `lib/shared/widgets/` or the forum feature;
rendition sizes; cache key design; how the work is split into PRs (backend first is the
natural order, since the app needs the new fields).
