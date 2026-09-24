---
status: pending
priority: p3
issue_id: "422"
tags: [forum, moderation, wagtail, backend]
dependencies: []
---

# Approving a topic in the admin leaves its opening post pending, and the live topic is empty

## Problem

A new topic from an author below `TRUST_AUTOPUBLISH_LEVEL` needs moderation for
both the Topic and its opening Post. A moderator who publishes only the
**topic** in the Wagtail admin puts an empty topic live. Readers see a title
with no body until someone finds the Post separately and publishes that too.

Reproduced on production on 2026-09-24. The owner's account (`plantadmin`,
trust level 1) posted topic 44, "video post". The owner published the topic
from the admin. The API then returned the topic as live with
`opening_post_id: null`, `/forum/topics/44/posts/` returned `results: []`,
and the app showed an empty thread. Publishing post 289 separately under
**Forum → Posts** fixed it.

## Findings

- The automatic path is fine. `submit_for_moderation`
  (`wagtail_forum/workflow.py:129-138`) publishes the topic when its author's
  opening post goes live. The link only runs from post to topic, though.
  Nothing makes publishing a topic carry its opening post along.
- The dashboard's "awaiting forum moderation" count links to the **Topics**
  list (`wagtail_hooks.py`, `moderation_url`). That steers a moderator to the
  half that doesn't publish the content.
- The Forum menu is its own sidebar group (`ForumViewSetGroup`), not under
  Snippets. The owner looked under Snippets first and found no forum items.
  This is minor, but it adds to the "where do I approve this" confusion.
- **Hypothesis, not verified:** publishing the topic first fires
  `topic_created` with `post=None` (`signals.py`, `update_counters_on_publish`).
  The comment there expects `None` only for topics created in the admin. Any
  host receiver that deep-links or quotes the opening post would get `None`
  for a user-created topic.

## Recommended Action

When a moderator publishes a Topic whose opening post is still a draft by the
same author, publish that post as well. Keep the same author-match guard as
`workflow.py:129-138`. Also consider sending the dashboard link to the Posts
list, or to a list that shows both topics and posts.

## Acceptance Criteria

- [ ] Test: a topic with a draft opening post by a trust-1 author. Publishing
      the topic through the admin (snippet publish) makes the opening post
      live too. The test fails before the fix.
- [ ] Test: publishing a topic never publishes an opening post by a
      *different* author (the IDOR guard).
- [ ] `topic_created` receives the opening post, not `None`, when a
      user-created topic is approved from the admin.
- [ ] A moderator can find pending forum content from the dashboard without
      knowing the model split.

## Work Log

### 2026-09-24 - Filed during build 13's device check

- Reproduced on production: topic 44, post 289.
