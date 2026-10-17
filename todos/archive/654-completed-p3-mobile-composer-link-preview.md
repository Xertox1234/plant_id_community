---
status: completed
priority: p3
issue_id: "654"
tags: [forum, mobile, link-preview]
dependencies: ["655"]
triage: ready
triaged: 2026-10-17
owner_decision: "Run after 655 in the same run; the hint caps at 5 per 655's spam-limit decision (2026-10-17)"
---

# The mobile composer shows no link preview while writing

## Problem

When you paste a link into the web composer, it shows a preview card under
the editor. The Flutter composer shows nothing. Readers on both platforms
already get the card, because the server builds it at write time (todo 428).
A mobile author only finds out what the post will look like after posting it.
Todo 428 left this out as its optional item 4 ("slice E").

## Findings

- **The endpoint exists and needs nothing new:**
  - `GET /forum/link-preview/?url=` (`backend/apps/forum_host/api_urls.py:87`,
    `LinkPreviewView` in `backend/apps/forum_host/link_preview.py`);
  - authenticated, throttled at `link_preview: 30/m`
    (`backend/apps/forum_host/constants.py:97`);
  - SSRF-hardened, with results cached for 1 h;
  - returns `{url, title, description, image_url, site_name, domain, available}`.
- **The web reference is `web/src/components/forum/TipTapEditor.tsx:142–185`:**
  - waits 450 ms after the last keystroke, then fetches;
  - aborts the previous request when the URL changes, and ignores a reply for
    a URL that is no longer current;
  - renders nothing when `available: false`;
  - a failure is logged as a warning and nothing is shown.

  The URL it previews comes from `previewUrlFromHtml`
  (`web/src/utils/forumBody.ts:338`): the **last** link anywhere in the
  body.
- **The server's conversion rule is different** (todo 428, slice A):
  - only a paragraph whose sole content is one non-video `http(s)` URL
    becomes a card;
  - at most 5 per post;
  - a link inside prose stays a link.

  So the web composer can preview a link that will never become a card (one
  inside a sentence). That gap is out of scope here, but the mobile composer
  should not copy it (see Recommended Action 2).
- **Mobile pieces to reuse:**
  - `LinkPreviewBlock` and `LinkPreviewDisplay`
    (`plant_community_mobile/lib/features/forum/models/forum_body_block.dart:254`, `:304`);
  - the reader card `_LinkPreviewCard`
    (`plant_community_mobile/lib/features/forum/widgets/forum_body_renderer.dart:586`),
    which is private today;
  - `linkPreviewShortAddress` for the address line.

  The composer is `plant_community_mobile/lib/features/forum/screens/forum_composer_screen.dart`
  (716 lines), and its API client is `.../services/forum_api.dart`.
- **Image hotlinking needs an owner decision.** The endpoint's `image_url` is
  the linked site's own `og:image`, not our cached copy (that copy exists
  only after the post is saved). The web composer shows it as-is (https
  only, `LinkPreviewCard.tsx:10`). Todo 428's owner rule says *"a reader's
  device must never contact the linked site."* That rule covers readers; it
  doesn't say whether the author's own device may load the image while
  composing.

## Recommended Action

1. **The composer image: DECIDED 2026-10-17 (owner): "show the image".**
   The composer card shows the site's `og:image` straight from the preview
   endpoint (https only), as the web composer does. This covers the author's
   own device while composing. Readers still get only our cached copy (todo
   428's rule is unchanged).
2. **Preview what readers will get.** Mirror the server's split rule from
   todo 655 in Dart: a composer **line** that is one sole `http(s)` URL, not
   inside a list item (a line starting "- ") or inline-code markers, and not a video.
   - Show the card for the **first** such line, plus a "+N more links will
     show as cards" hint for the rest, counted up to the server's real
     ceiling. That is `MAX_LINK_PREVIEWS_PER_BODY` (5), or the spam limit
     todo 655's owner decision settles, whichever is lower.
   - Only the first line is fetched; the hint is counted locally, so typing
     several links costs one preview request.
   - **Video:** there is no Dart video matcher today. Port the web's
     `embedUrlOf` table (YouTube + Vimeo, `web/src/utils/forumBody.ts`) and
     test both against the same cases, as `linkPreviewShortAddress` was.
     A video line gets no link card and does not count toward the hint.
3. Add `fetchLinkPreview(String url)` to `ForumApi` and its implementation. It
   returns `null` for `available: false` and maps 429 or errors to `null`
   with a debug log, never a user-facing error.
4. Use a Riverpod family provider, or controller state in
   `forum_composer_controller.dart`, with the web's behaviour:
   - a 450 ms debounce, held in a `Timer` field, never state;
   - stale replies dropped by comparing the URL;
   - the timer cancelled on dispose.
5. Make the reader card public (or extract a shared `LinkPreviewCardView`) so
   the composer and the reader render the **same** widget: the short address,
   one semantics node, the label `Link: {title}, {short address}`. In the
   composer, a tap does nothing.
6. Tests:
   - widget tests: card appears after the debounce; no card for a URL inside
     prose, a video URL, or `available: false`; a URL change replaces the
     card; dispose cancels the timer;
   - a test that `fetchLinkPreview` maps the API reply into the model.

## Technical Details

- Patterns: `plant_community_mobile/docs/patterns/riverpod.md` and
  `flutter-patterns.md`. A codegen provider needs `build_runner` (pre-commit
  `flutter-codegen` hook).
- No backend change. The composer's image goes through
  `CachedNetworkImage` like the reader's.

## Acceptance Criteria

- [x] A sole-URL paragraph in the mobile composer shows a preview card after
      the debounce, with the site's https `og:image`, rendered by the same
      widget the reader uses. Pinned by a widget test. A non-https image URL
      shows the card without an image.
- [x] A URL inside prose, a video URL, and an `available: false` reply show
      no card. Pinned by tests.
- [x] With several URL lines, the first gets the card and the hint counts the
      rest up to the server's ceiling. A video line is not counted. Pinned by
      a widget test.
- [x] The Dart video matcher agrees with the web's `embedUrlOf` on one shared
      case table. Pinned by a test.
- [x] Editing the URL replaces the card, a stale reply never shows, and the
      debounce timer is cancelled on dispose. Pinned by tests.
- [x] A failed or throttled preview request shows nothing and blocks nothing:
      the post still submits.
- [x] `flutter analyze` is clean, and the forum Flutter tests pass.
- [ ] On a device: pasting a Wikipedia link in the app composer shows the → todo 656 (re-pointed 2026-10-17)
      card before posting.

## Work Log

### 2026-10-17 - Filed from todo 428's close-out

- Split out of todo 428 (archived in #1144), where it was the optional
  item 4 / slice E. Readers on both platforms already get the card from the
  server; this todo is only author-side parity.
- The owner decided the composer image the same day: "show the image"
  (Recommended Action 1). The todo is ready to build.
- Rescoped the same day. Triage found that a mobile post can hold at most one
  card, because the composer sends one `<br>`-joined paragraph and the
  server's `_sole_url` rejects whitespace. The web has the same limit. The
  owner chose the server fix ("Server, new todo"): todo 655 splits link lines
  out into their own paragraphs. This todo now depends on 655, and its "+N
  more" hint is real.

### 2026-10-17 - Implemented by the todo sweep (run 2026-10-17-1622)

- The Flutter composer previews the first link line the server will card,
  after a 450 ms debounce (a `Timer` field cancelled in `dispose`, stale
  replies dropped by URL), with a "+N more links will show as cards" hint
  counted locally up to 5 (`kForumMaxLinkCardsPerPost`: the card cap and the
  new spam default from todo 655).
- The line rule is `forumComposerCardLinks` in
  `plant_community_mobile/lib/features/forum/utils/forum_embed_url.dart`: it
  renders each line with `generateForumRichHtml` and reads its text as the
  server does, skipping prose, list items, inline code and video links
  (`forumVideoUrlOf`, a port of the web's `PROVIDER_VIDEO_URL`). Both
  matchers read one case table,
  `plant_community_mobile/test/features/forum/support/video_url_cases.json`;
  the web side gained an exported `providerVideoUrl`.
- The reader card moved to the public `LinkPreviewCardView`
  (`widgets/link_preview_card_view.dart`), drawn by both the reader and the
  composer (no `onOpenLink` in the composer, so a tap does nothing). Its
  spoken label is unchanged ("title, short address"); the "Link:" prefix in
  Recommended Action 5 was not added, so reader and composer stay identical.
- `ForumApi.fetchLinkPreview` calls `GET /forum/link-preview/?url=`, keeps
  only an https `image_url`, and maps `available: false`, a 429 or any error
  to `null` with a debug log. The device check (AC8) is todo 656.

### 2026-10-17 - Verified by the todo sweep (run 2026-10-17-1622)

- AC 1: `cd plant_community_mobile && flutter test test/features/forum/forum_composer_link_preview_test.dart --plain-name 'shows the reader card after the debounce' && cd . && flutter test test/features/forum/forum_composer_link_preview_test.dart --plain-name 'not https shows without an image' && cd . && flutter test test/features/forum/forum_api_link_preview_test.dart --plain-name 'https image'` — evidence `.sweep-evidence/g2/654-ac0.txt` (not committed), last lines:

  ```text
  143 packages have newer versions incompatible with dependency constraints.
  Try `flutter pub outdated` for more information.
  00:00 +0: loading plant_community_mobile/test/features/forum/forum_api_link_preview_test.dart
  00:00 +0: keeps only an https image
  00:00 +1: All tests passed!
  ```

- AC 2: `cd plant_community_mobile && flutter test test/features/forum/forum_composer_link_preview_test.dart --plain-name 'shows no card'` — evidence `.sweep-evidence/g2/654-ac1.txt` (not committed), last lines:

  ```text
  00:00 +1: the composer link preview (todo 654) a list item shows no card and is never fetched
  00:00 +2: the composer link preview (todo 654) inline code shows no card and is never fetched
  00:00 +3: the composer link preview (todo 654) a video URL shows no card and is never fetched
  00:00 +4: the composer link preview (todo 654) an available: false reply shows no card
  00:00 +5: All tests passed!
  ```

- AC 3: `cd plant_community_mobile && flutter test test/features/forum/forum_composer_link_preview_test.dart --plain-name 'with several link lines'` — evidence `.sweep-evidence/g2/654-ac2.txt` (not committed), last lines:

  ```text
  143 packages have newer versions incompatible with dependency constraints.
  Try `flutter pub outdated` for more information.
  00:00 +0: loading plant_community_mobile/test/features/forum/forum_composer_link_preview_test.dart
  00:00 +0: the composer link preview (todo 654) with several link lines the first gets the card and the hint counts the rest up to the ceiling, not a video
  00:00 +1: All tests passed!
  ```

- AC 4: `cd plant_community_mobile && flutter test test/features/forum/forum_embed_url_test.dart --plain-name 'forumVideoUrlOf agrees' && cd ../web && npx vitest --run src/utils/forumBody.test.ts -t 'providerVideoUrl matches'` — evidence `.sweep-evidence/g2/654-ac3.txt` (not committed), last lines:

  ```text

   Test Files  1 passed (1)
        Tests  27 passed | 99 skipped (126)
     Start at  15:26:32
     Duration  957ms (transform 77ms, setup 118ms, import 235ms, tests 10ms, environment 519ms)
  ```

- AC 5: `cd plant_community_mobile && flutter test test/features/forum/forum_composer_link_preview_test.dart --plain-name 'editing the URL replaces the card' && cd . && flutter test test/features/forum/forum_composer_link_preview_test.dart --plain-name 'a stale reply never shows' && cd . && flutter test test/features/forum/forum_composer_link_preview_test.dart --plain-name 'dispose cancels the debounce timer'` — evidence `.sweep-evidence/g2/654-ac4.txt` (not committed), last lines:

  ```text
  143 packages have newer versions incompatible with dependency constraints.
  Try `flutter pub outdated` for more information.
  00:00 +0: loading plant_community_mobile/test/features/forum/forum_composer_link_preview_test.dart
  00:00 +0: the composer link preview (todo 654) dispose cancels the debounce timer
  00:00 +1: All tests passed!
  ```

- AC 6: `cd plant_community_mobile && flutter test test/features/forum/forum_composer_link_preview_test.dart --plain-name 'shows nothing and the post still submits' && cd . && flutter test test/features/forum/forum_api_link_preview_test.dart --plain-name 'throttled or failed'` — evidence `.sweep-evidence/g2/654-ac5.txt` (not committed), last lines:

  ```text
  00:00 +0: a throttled or failed request is no card, never an error
  [FORUM] link preview unavailable: ApiException(429): Too many requests
  [FORUM] link preview unavailable: ApiException(500): Server error
  [FORUM] link preview unavailable: ApiException: No connection
  00:00 +1: All tests passed!
  ```

- AC 7: `cd plant_community_mobile && flutter analyze && flutter test test/features/forum` — evidence `.sweep-evidence/g2/654-ac6.txt` (not committed), last lines:

  ```text
  00:26 +633: plant_community_mobile/test/features/forum/widgets/forum_body_renderer_test.dart: link preview card (todo 428) a long-press shows the full address with "Copy link"
  00:27 +634: plant_community_mobile/test/features/forum/widgets/forum_body_renderer_test.dart: link preview card (todo 428) a screen reader reaches the full address and "Copy link" as custom actions, with no gesture
  00:27 +635: plant_community_mobile/test/features/forum/widgets/forum_body_renderer_test.dart: link preview card (todo 428) a card with no usable link renders nothing
  00:27 +636: plant_community_mobile/test/features/forum/widgets/forum_body_renderer_test.dart: link preview card (todo 428) a stored card image is shown from its own URL
  00:27 +637: All tests passed!
  ```

### 2026-10-17 - Completed by the todo sweep (run 2026-10-17-1622)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-17 - Repaired by the todo sweep (run 2026-10-17-1622)

- No change to this todo's code: the round-1 finding was in todo 655's
  server split (`backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py`),
  which now splits out only link lines within the card and embed caps.
- Evidence for every open criterion was re-run against the repaired tree.

## Notes

- P3: no reader-facing gap; it's a composer convenience.
- The web composer previews the last link anywhere in the body, not what the
  server will turn into a card. After todo 655 that mismatch is smaller but
  still there; this todo doesn't change the web.

### 2026-10-17 - Review rounds 1 and 2: non-blocking findings

- **Declined, with reasons:**
  - *With `FORUM_EMBEDS_ENABLED=False` the composer still skips video lines*,
    so the preview and "+N more" undercount. Embeds are on in production; the
    client has no embeds flag to read. The doc comment states the
    assumption.
  - *The card-link scan runs on every keystroke* (only the fetch is
    debounced): composer drafts are short. Declined until a long-draft
    slowdown is seen.
  - *`forumBody.test.ts` reads the shared `video_url_cases.json` across
    packages*: deliberate, since one table pins both matchers. It needs the
    monorepo checkout, which every CI job uses.
