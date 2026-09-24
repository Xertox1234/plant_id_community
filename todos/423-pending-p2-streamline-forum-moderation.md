---
status: pending
priority: p2
issue_id: "423"
tags: [forum, moderation, wagtail, backend, ux]
dependencies: []
---

# Examine and streamline forum moderation: staff are moderated, and approving a post takes a scavenger hunt

## Problem

The owner's first real pass through forum moderation, on 2026-09-24, was a
failure from start to finish. The owner described it as "a joke".

1. **The site admin's own posts were held for moderation.** `plantadmin` is
   staff. Topic 44 still sat as a draft until the owner approved it by hand.
2. **The owner couldn't find where to approve it.** They looked under
   **Snippets** and found only Blog Categories and Blog Series. The forum
   models are in a separate **Forum** sidebar group.
3. **Approving the topic published an empty thread.** The topic went live,
   but its opening post, which holds the body, stayed a draft in a different
   list (todo 422).
4. **Nothing is called "pending content".** The only item named "Forum
   moderation queue" (Reports menu) lists **user-filed reports** (`Report`
   rows, `admin_views.py` `ModerationQueueView`). Posts waiting for approval
   aren't in it. The pending count sits on the dashboard and links to the
   Topics list only.

It took four steps across three admin areas to publish one post, and it needed
knowledge of the Topic/Post model split.

## Findings

- **Trust depends only on post count.** `submit_for_moderation`
  (`wagtail_forum/workflow.py`) autopublishes only when
  `ForumProfile.for_user(author).trust_level >= TRUST_AUTOPUBLISH_LEVEL`
  (2, `conf.py`). `trust_level` comes from live post count through
  `TRUST_THRESHOLDS` `{1: 1, 2: 5, 3: 50, 4: 200}`
  (`signals.py`, `_refresh_profile`). `is_staff`, `is_superuser`, Wagtail
  moderator groups and the `change_post` permission are never checked on the
  create path. `plantadmin` shows `trust_level: 1` (Basic) in the API because
  they have one live post.
- The edit path has a moderator exception, `_edit_is_trusted(obj,
  acting_as_moderator)`, but it is only used to redact an account-deleted
  author's post.
- `_route_revision_by_trust` says the author's trust is used deliberately, not
  the caller's, so a privileged caller can't pass an untrusted author's content
  through. A staff bypass has to be based on the **author** being staff or a
  moderator, not the person making the request.
- A manually raised `trust_level` is kept. `_refresh_profile` keeps
  `max(current, earned)` once the stored level is above the earned one
  (`signals.py`), and `trust_level` can be edited in **Forum → Profiles**.
  This is the workaround until this todo is done.
- The dashboard summary counts active `WorkflowState` rows for Topic and Post
  (`_pending_moderation_count`) but links only to the Topic list.
- Topic and post are two separately moderated objects. See todo 422 for the
  publish-direction bug.

## Recommended Action

1. **Staff and moderators bypass moderation.** On create and edit, treat the
   author as trusted when they are staff or superuser, or hold the forum
   moderation permission. Decide which of these it should be. Then backfill:
   raise existing staff profiles, or compute it at request time instead of
   storing it.
2. **One pending-content queue.** A single admin view that lists pending
   topics and posts together, each with its body excerpt, author and trust
   level, and Approve / Reject buttons that act on the topic and its opening
   post as one unit. Point the dashboard count at it.
3. **Clearer names.** Rename the Reports-menu item to something like
   "Reported content", so "moderation queue" means pending content.
4. **Fold in todo 422**, or supersede it: approving a thread must never leave
   its opening post behind.
5. **Review the thresholds.** Five live posts before autopublish, with no
   moderator reachable by push or email when something is waiting, means new
   members' first posts can sit unseen. Check whether moderators are notified
   at all when content is pending.

## Acceptance Criteria

- [ ] A post by a staff or superuser account publishes immediately, on the
      create and edit paths, via the API and the mobile app. Pinned by tests.
      A test also shows an untrusted author's content is still held when the
      *request* comes from a staff account (author-based, not caller-based).
- [ ] One admin page lists every pending topic and post, and a single
      Approve publishes a topic together with its opening post.
- [ ] The dashboard's pending count links to that page.
- [ ] The Reports-menu item is named so it can't be mistaken for the pending
      queue.
- [ ] Decide whether moderators are notified when something is pending, and
      record the decision.
- [ ] A walkthrough from the owner's point of view: a trust-0 test account
      posts, a moderator approves in one place, and the thread shows up
      complete in the app.

## Work Log

### 2026-09-24 - Filed at the owner's request

- Filed after build 13's device check (todo 398) needed a video post and the
  owner's own post went through all four problems above: topic 44, post 289.
- Related: todo 422 (topic approval leaves the post pending) and todo 421
  (mobile video links).
