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
- Topics **37-41** (slugs `spam-screen-probe-280`, `…-2` … `…-5`) in board
  `show-tell`, all rejected by the LLM screen and left as pending drafts.
- Topic **42** (slug `spam-screen-probe-280-cold`), the post-fix cold-start
  probe, same state.

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

1. In `/cms/`, delete topics 37-42 (search slug prefix `spam-screen-probe-280`).
   Deleting the topic removes its opening post; the drafts were never published,
   so there is nothing to unpublish first.
2. Delete the `spam-screen-probe-280` user (id 20). It owns nothing else — it
   was created solely for the probe and its `forum_posts_count` is 0.
3. Confirm the moderation queue no longer lists them.

## Technical Details

Board: `show-tell`. Topic ids 37-42. User id 20.

Re-check public invisibility after deletion is unnecessary — they were never
visible. See `backend/docs/patterns/domain/forum.md` → "LLM spam backend" for
why a flagged post lands as a pending draft rather than being discarded.

## Acceptance Criteria

- [ ] Topics 37-42 no longer exist (Wagtail admin search for
      `spam-screen-probe-280` returns nothing)
- [ ] User id 20 (`spam-screen-probe-280`) is deleted
- [ ] The forum moderation queue shows no `spam-screen-probe-280` entries

## Work Log

### 2026-09-03 - Spun out of todo 280

- Filed rather than left in todo 280's archived Work Log, since the action needs
  a human with `/cms/` access and an archived file is not a worklist anyone
  re-reads.

## Notes

p4 because there is no exposure and no functional impact — purely tidiness of
the moderation queue. Deliberately NOT `status: blocked`: per
`docs/LEARNINGS.md`, a blocked todo is invisible to every sweep skill, which is
the opposite of getting it done.
