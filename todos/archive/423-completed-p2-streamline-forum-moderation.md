---
status: completed
priority: p2
issue_id: "423"
tags: [forum, moderation, wagtail, backend, ux]
dependencies: []
triage: needs-design
triaged: 2026-09-28
blocked_on: "Owner picks the bypass criterion, stored vs computed trust, and the moderator-notification policy"
owner_decision: "Bypass: superusers plus a forum-moderator group/permission, checked at request time (no trust_level backfill); no moderator notification for pending content (2026-09-28)"
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

- [x] A post by a staff or superuser account publishes immediately, on the
      create and edit paths, via the API and the mobile app. Pinned by tests.
      A test also shows an untrusted author's content is still held when the
      *request* comes from a staff account (author-based, not caller-based).
- [x] One admin page lists every pending topic and post, and a single
      Approve publishes a topic together with its opening post.
- [x] The dashboard's pending count links to that page.
- [x] The Reports-menu item is named so it can't be mistaken for the pending
      queue.
- [x] Decide whether moderators are notified when something is pending, and
      record the decision.
- [ ] A walkthrough from the owner's point of view: a trust-0 test account → todo 493 (re-pointed 2026-09-28)
      posts, a moderator approves in one place, and the thread shows up
      complete in the app.

## Work Log

### 2026-09-24 - Filed at the owner's request

- Filed after build 13's device check (todo 398) needed a video post and the
  owner's own post went through all four problems above: topic 44, post 289.
- Related: todo 422 (topic approval leaves the post pending) and todo 421
  (mobile video links).

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- Bypass (owner decision): `workflow.author_bypasses_moderation` trusts an
  active superuser or an author holding `WAGTAILFORUM_MODERATION_BYPASS_PERMISSION`
  (default `wagtail_forum.publish_post`, which the bootstrapped "Forum
  Moderators" group holds), checked on the AUTHOR at request time, no
  `trust_level` backfill. Used on create, edit and DM screening. A staff
  account bypasses when it is in the moderator group; plain `is_staff` alone
  does not, per the owner decision. Tests: `tests/api/test_moderation_bypass.py`.
- One page: **Reports → Pending forum content** (`PendingContentView`,
  `<admin>/forum/pending/`) lists every pending new topic, reply and held
  edit with excerpt, kind, author and trust. Approve publishes the latest
  revision and, for a new topic, the topic with it (even across authors);
  Reject on new content opens the snippet delete confirmation. Todo 422's
  signal link stays; the approve path does not rely on it alone.
- The dashboard count now counts exactly that page's rows (it also catches a
  draft whose spam backend crashed, which it missed before) and links to it.
  The Reports item "Forum moderation queue" is renamed "Reported forum content".
- Decision recorded: moderators are NOT notified (no push, no email) when
  content is pending (owner decision 2026-09-28); the dashboard count and the
  pending page are the signal. Written in the `admin_views.py` docstring and
  the package README. The
  autopublish threshold (5 live posts) is unchanged.
- Left for the owner: the on-device walkthrough (trust-0 account posts in the
  app, a moderator approves on the pending page, the thread shows up complete
  in the app). Its API half is `test_walkthrough_trust0_posts_moderator_approves_thread_is_complete_in_api`.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py 1 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_moderation_bypass.py --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/423-ac0.txt`, last lines:

  ```text
    /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_3590897f-ede-1/backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 15 passed, 3 warnings in 17.52s ========================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py 1 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_pending_content.py packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py -k "not dashboard and not reports_menu and not reported_content" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/423-ac1.txt`, last lines:

  ```text
    /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_3590897f-ede-1/backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ================ 25 passed, 4 deselected, 3 warnings in 19.93s =================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py 1 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_pending_content.py packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py packages/wagtail_forum/wagtail_forum/tests/test_admin.py packages/wagtail_forum/wagtail_forum/tests/test_workflow_routing.py -k "dashboard or summary_item or spam_backend_crashes" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/423-ac2.txt`, last lines:

  ```text
    /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_3590897f-ede-1/backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ================ 4 passed, 57 deselected, 3 warnings in 16.95s =================
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py 1 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_pending_content.py packages/wagtail_forum/wagtail_forum/tests/test_moderation_queue.py -k "reports_menu or reported_content or menu_item" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/423-ac3.txt`, last lines:

  ```text
    /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_3590897f-ede-1/backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ================ 4 passed, 23 deselected, 3 warnings in 16.58s =================
  ```

- AC 5: `grep -n -i "not notified\|NOT notified\|not pushed or emailed\|no moderator notification" backend/packages/wagtail_forum/wagtail_forum/admin_views.py backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py backend/packages/wagtail_forum/README.md todos/423-pending-p2-streamline-forum-moderation.md` — evidence `.sweep-evidence/g1/423-ac4.txt`, last lines:

  ```text
  todos/423-pending-p2-streamline-forum-moderation.md:10:owner_decision: "Bypass: superusers plus a forum-moderator group/permission, checked at request time (no trust_level backfill); no moderator notification for pending content (2026-09-28)"
  todos/423-pending-p2-streamline-forum-moderation.md:128:- Decision recorded: moderators are NOT notified (no push, no email) when
  backend/packages/wagtail_forum/wagtail_forum/admin_views.py:36:Moderators are NOT notified when content is waiting (owner decision
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
