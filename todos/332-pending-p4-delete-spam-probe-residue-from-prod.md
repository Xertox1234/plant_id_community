---
status: pending
priority: p4
issue_id: "332"
tags: [forum, ops, cleanup, moderation]
dependencies: []
source_review: "todo 280 (spun out 2026-09-03)"
---

# Delete the todo-280 spam-probe residue from production

## Problem

Closing todo 280 required proving the LLM spam screen actually flags real
content in production. That meant a throwaway trust-0 account posting genuine
promotional spam, six times. The account and its six held drafts are still
there. They are moderation-queue clutter, not exposure — but nothing removes
them automatically, and only a human with `/cms/` access can.

## Findings

Created 2026-09-03 while verifying todo 280 AC3/AC4:

- Account `spam-screen-probe-280`, user id **20**, email
  `spam-screen-probe-280@example.com`, trust level NEW (0).
- Topics **37-42** in board `show-tell`, all rejected by the LLM screen and left
  as pending drafts. **Identify them by id, not by slug** — see the trap below.
  Ids, slugs and the titles actually stored:

  | id | slug | title |
  |----|------|-------|
  | 37 | `spam-screen-probe-280` | CHEAP DESIGNER WATCHES 90% OFF TODAY ONLY |
  | 38 | `spam-screen-probe-280-2` | CHEAP DESIGNER WATCHES probe 2 |
  | 39 | `spam-screen-probe-280-3` | CHEAP DESIGNER WATCHES probe 3 |
  | 40 | `spam-screen-probe-280-4` | CHEAP DESIGNER WATCHES probe 4 |
  | 41 | `spam-screen-probe-280-5` | CHEAP DESIGNER WATCHES probe 5 |
  | 42 | `spam-screen-probe-280-cold` | LIMITED TIME crypto seed vault clearance |

- **Trap: searching the admin for `spam-screen-probe-280` finds NOTHING.**
  `TopicViewSet.search_fields = ["title"]` (`wagtail_hooks.py:23`) — the Topics
  listing searches titles only, and `slug` is an independent client-supplied
  `SlugField` on `TopicCreateSerializer` (`api/serializers.py:1060`), not
  derived from the title. Every probe title is spam prose, so a slug-based
  search returns zero rows and every acceptance criterion below would pass with
  all six drafts still present.

- **Trap: delete the topics BEFORE the user.** `Topic.author` and `Post.author`
  are both `on_delete=models.SET_NULL` (`models/topics.py:39`,
  `models/posts.py:40`). Deleting user 20 first blanks the author column on all
  six rows, destroying the last handle that ties them to this cleanup.

**Not a public exposure** — verified anonymously against production the same
day, and this is the fail-closed path working correctly:

```
RSS mentions probe:                 0
sitemap mentions probe:             0
anon board topic list mentions:     0
anon topic detail id=37:            HTTP 404
```

**Why it needs a human.** There is no author-delete endpoint for a *pending*
topic (`topics/<id>/` is `TopicDetailView`, read-only for this case) and no
account-deletion endpoint in `apps/users/urls.py`. Railway's Postgres is on the
private network, so `railway run` from a laptop cannot reach it either. Wagtail
admin is the only route.

## Recommended Action

**Order matters — topics first, then the user** (see the SET_NULL trap above).

1. Delete topics 37-42 by id, not by search. Go straight to each snippet URL:

   ```
   /cms/snippets/wagtail_forum/topic/delete/37/
   /cms/snippets/wagtail_forum/topic/delete/38/
   /cms/snippets/wagtail_forum/topic/delete/39/
   /cms/snippets/wagtail_forum/topic/delete/40/
   /cms/snippets/wagtail_forum/topic/delete/41/
   /cms/snippets/wagtail_forum/topic/delete/42/
   ```

   Deleting the topic removes its opening post; the drafts were never published,
   so there is nothing to unpublish first. (If you prefer the listing, search
   the *titles* — `CHEAP DESIGNER WATCHES` and `crypto seed vault` — since slug
   search does not work.)

2. Only then delete the `spam-screen-probe-280` user (id 20) in the Django/Wagtail
   user admin.

3. Confirm each of the six ids now 404s in the admin.

## Technical Details

Board: `show-tell`. Topic ids 37-42. User id 20.

Re-check public invisibility after deletion is unnecessary — they were never
visible. See `backend/docs/patterns/domain/forum.md` → "LLM spam backend" for
why a flagged post lands as a pending draft rather than being discarded.

## Acceptance Criteria

- [ ] Each of `/cms/snippets/wagtail_forum/topic/edit/<id>/` for ids **37, 38,
      39, 40, 41, 42** returns 404 (checked per id — a listing search is NOT
      acceptable evidence here, see the Findings trap)
- [ ] User id 20 (`spam-screen-probe-280`) is deleted, and was deleted *after*
      the topics
- [ ] A Topics listing search for `CHEAP DESIGNER WATCHES` and for
      `crypto seed vault` both return zero rows

## Work Log

### 2026-09-03 - Spun out of todo 280

- Filed rather than left in todo 280's archived Work Log, since the action needs
  a human with `/cms/` access and an archived file is not a worklist anyone
  re-reads.

## Notes

The original version of this file told the reader to find the topics by slug
search and made every acceptance criterion pass on a zero-row result — i.e. it
would have produced a confidently-ticked cleanup with nothing actually deleted.
Caught by `/code-review medium` on PR #621. Worth remembering that a todo whose
verification step can be satisfied by *not finding anything* is worse than no
todo at all.

p4 because there is no exposure and no functional impact — purely tidiness of
the moderation queue. Deliberately NOT `status: blocked`: per
`docs/LEARNINGS.md`, a blocked todo is invisible to every sweep skill, which is
the opposite of getting it done.
