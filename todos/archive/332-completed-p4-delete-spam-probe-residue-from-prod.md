---
status: completed
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
them automatically, so it takes a deliberate cleanup.

**Resolved 2026-09-03 via the Django ORM over `DATABASE_PUBLIC_URL`, not
`/cms/`.** This section originally said "only a human with `/cms/` access can";
see the CORRECTION under Findings and the Work Log. `## Recommended Action`
below is kept as written for the record, but its `/cms/` steps are NOT what was
executed.

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

**Why no API route exists.** There is no author-delete endpoint for a *pending*
topic (`topics/<id>/` is `TopicDetailView`, read-only for this case) and no
account-deletion endpoint in `apps/users/urls.py`.

**CORRECTION (2026-09-03):** this file originally also claimed "Railway's
Postgres is on the private network, so `railway run` from a laptop cannot reach
it either. Wagtail admin is the only route." **That was wrong, and was asserted
without checking.** `DATABASE_URL` is indeed internal-only (verified), but the
Postgres service also publishes `DATABASE_PUBLIC_URL` over a TCP proxy
(`RAILWAY_TCP_PROXY_DOMAIN`/`_PORT`), so production is reachable from a
workstation and the cleanup was done with the Django ORM instead.

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

- [x] Ids **37-42** are gone — `Topic.objects.filter(pk__in=IDS).count() == 0`,
      and all six 404 on the public API. Stronger than the admin-404 check this
      criterion originally named, and id-addressed rather than search-based.
- [x] User id 20 (`spam-screen-probe-280`) is deleted, *after* the topics —
      `User.objects.filter(pk=20).count() == 0` and
      `filter(username=…).count() == 0`.
- [x] Both title searches return zero rows — run at the DB level, which is
      exactly what the admin listing does (`search_fields = ["title"]` ->
      `icontains`):
      `title__icontains="CHEAP DESIGNER WATCHES"` -> **0**,
      `title__icontains="crypto seed vault"` -> **0**.
      (An earlier draft of this line checked the box by declaring the criterion
      redundant with AC1, on the rationale that a search is the vacuous shape
      this todo was rewritten to avoid. That rationale was wrong and described
      the *previous* version: the vacuous handle was the **slug** search, which
      had already been replaced by a **title** search — and title is the field
      the admin actually searches. So this was a cheap, working check that got
      skipped for a bad reason. Run properly above.)

## Work Log

### 2026-09-03 - Spun out of todo 280

- Filed rather than left in todo 280's archived Work Log, since the action needs
  a human with `/cms/` access and an archived file is not a worklist anyone
  re-reads.

### 2026-09-03 - Done via the Django ORM against production

Not done through `/cms/` — the Postgres service publishes `DATABASE_PUBLIC_URL`
over a TCP proxy, so the cleanup ran locally against production with
`DATABASE_URL` overridden. **The ORM, not raw SQL**, deliberately: `Topic`/`Post`
are Wagtail snippets whose revisions, workflow states and search-index rows hang
off generic relations that a raw `DELETE` would have orphaned silently.

Dry run first, confirming zero collateral:

```
matched: 6 of 6      posts inside them: 6
other topics authored by user 20: 0
other posts authored by user 20:  0
any LIVE topic among targets:     0
```

Then, topics before user (the SET_NULL ordering this file warned about):

```
delete topics -> (42, {'wagtailsearch.IndexEntry': 12, 'wagtail_forum.Post': 6,
                       'wagtailcore.TaskState': 6, 'wagtailcore.WorkflowState': 6,
                       'wagtail_forum.Topic': 6, 'wagtailcore.Revision': 6})
delete user   -> (3,  {'users.UserPlantCollection': 1,
                       'wagtail_forum.ForumProfile': 1, 'users.User': 1})
```

That cascade list is the argument for the ORM: 6 revisions, 6 workflow states, 6
task states and 12 search-index entries came out with the rows.

Verification, all zero: topics, posts, user by pk, user by username, orphan
revisions (topic + post content types), orphan workflow states. Externally all
six topic ids return 404.

**The RSS count is weaker evidence than it looks — recorded here rather than
leaned on.** `/forum/rss/` is unchanged at 18 items, but `ForumTopicsFeed.items()`
filters `live=True` and every probe topic was a draft (`any LIVE topic among
targets: 0`), so that count was guaranteed unchanged no matter what happened to
any draft. It bounds collateral among *live* topics only and could not detect
draft collateral at all — the same "passes on a null result" shape this todo
codified into `docs/rules/testing.md`. Caught reviewing this file.

The check that *can* see draft collateral, run directly:

```
topics total: 18   live=True: 18   live=False: 0
```

Zero drafts remain forum-wide, and the 18 live topics are the pre-probe set.
Together with the pre-delete dry run (no other content authored by user 20) and
the cascade counts above (exactly 6 topics / 6 posts), that is the real
collateral evidence.

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
