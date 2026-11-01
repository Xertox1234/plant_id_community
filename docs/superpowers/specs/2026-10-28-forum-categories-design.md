# Forum categories, forum types and forum admin — design

**Date:** 2026-10-28
**Status:** research complete, no code written. Slices filed as todos 665–681.
**Scope:** web only (no Flutter work). Backend in `backend/packages/wagtail_forum/`.

## 1. Owner decisions (2026-10-28)

1. Follow phpBB's model: **Category** (holds forums, never topics), **Forum**
   (holds topics), **Link** (a row that redirects to a URL).
2. "If phpBB has it then I want it" — every phpBB forum-management extra is in
   scope, delivered as separately testable slices.
3. Admin lives **inside the Wagtail admin** (`/cms/`), under a dedicated
   *Forum* menu.
4. Forums are **forum-specific data, not Wagtail pages** — no CMS page tree,
   no page explorer.
5. **Subforums are out of scope** (deferred by the owner as a separate, large
   undertaking). Depth is exactly two: category → forum.
6. Web only for now.

## 2. Research summary

### phpBB 3.3 (source: `phpbb/phpbb` 3.3.x — `includes/acp/acp_forums.php`, `includes/functions_display.php`, `includes/constants.php`, `language/en/acp/forums.php`, `install/schemas/schema_data.sql`)

- Three types in one `forums` table: `FORUM_CAT=0`, `FORUM_POST=1`, `FORUM_LINK=2`.
  A link forum cannot be a parent. Categories are not postable.
- Board index: each root category is a header row; its forums are rows under it.
  A category with no visible children is skipped. Root-level forums with no
  category get a dummy header.
- Per-forum settings the ACP groups as *General* (type, parent, copy permissions
  from, name, description, image, password, style, link URL + "track link
  redirects") and *Forum settings* (locked status, display on index, topics per
  page, search indexing, active topics, post review, quick reply, icons, rules
  text or rules link) and *Prune settings* (auto-prune frequency, days since
  last post, days since viewed, prune polls/announcements/stickies).
- Ordering: move-up/move-down arrows only, within one level. **No drag and drop.**
- Delete: choose *delete topics* or *move topics to [forum]*. Server-side, phpBB
  does not validate the target's type or that it isn't the forum itself — we must.
- Type changes: POST→CAT/LINK forces a "delete or move topics" choice; counters reset.
- Permissions: per forum, per group/user, `f_*` flags (Yes/No/Never), packaged as
  roles (Full / Standard / Standard+Polls / Limited / Read Only / No Access / On
  Moderation Queue). **Not inherited** — a new forum is invisible until
  permissions are copied onto it (a well-known footgun). Per-forum moderators via
  `m_*` roles drive the "Moderators:" line.
- Read state: per-forum mark time (`forums_track`), "mark forums read" on the
  index and inside a forum. Collapsible categories are an official *extension*,
  not core.
- Pain points to avoid: nested-set (`left_id`/`right_id`) corruption; invisible
  new forums; one-step-at-a-time reordering; drifting denormalized counters
  needing "Resync"; forum passwords (the ACP itself says prefer permissions).

### Discourse (source: `discourse/discourse` — `app/models/category.rb`, `config/site_settings.yml`, admin `edit-category` templates, `reorder-categories.gjs`; meta.discourse.org 13821, 83171, 87678)

- One node type: every category holds topics; subcategories via
  `parent_category_id`, depth 2 by default (max 3, hidden setting). Tags carry
  finer classification.
- Worth borrowing: colour + icon/emoji per category, per-category **topic
  template**, read-only banner, default sort, per-category Watching / Tracking /
  Muted notification levels, featured-topic layouts.
- Delete is refused unless the category is empty. Reorder is a modal of
  arrows + position numbers; drag and drop was removed as buggy.
- Permissions: See / Reply / Create per group; a child may be narrower than its
  parent, never broader.

## 3. Current state (code anchors)

- `ForumIndex(Page)` → `ForumBoard(Page)` only; `ForumBoard.subpage_types = []`
  (`models/boards.py:63,98-99`).
- `Topic.board` FK, `on_delete=CASCADE` (`models/topics.py:23-25`) — deleting a
  board in Wagtail today deletes every topic on it.
- Board visibility: `_visible_boards()` = `ForumBoard.objects.live().public()`
  (`api/views.py:134-141`); a Wagtail view restriction hides a board from the
  whole API.
- Board lookup by slug only, 409 on ambiguity (`api/views.py:180-194`).
- Topic URL: `/forum/{board.id}-{board.slug}/{topic.id}-{topic.slug}`
  (`models/topics.py:220-222`); slug/board change redirects in
  `apps/forum_host/redirects.py` (incl. board renames via `page_slug_changed`).
- Non-test files referencing `ForumBoard`: `apps/forum_host/management/commands/seed_default_forum.py`,
  `seed_demo_content.py`, `apps/forum_host/redirects.py`, `apps/forum_host/sitemaps.py`,
  `apps/users/views.py`, `wagtail_forum/api/serializers.py`, `api/views.py`,
  `models/__init__.py`, `models/boards.py`, `models/topics.py`, `signals.py`.
  94 test files reference `ForumBoard`.
- **Flutter consumes** `GET /forum/boards/` and `/forum/boards/{slug}/topics/`
  (`plant_community_mobile/lib/features/forum/services/forum_api.dart:412,429`).
  Web-only means these responses must keep their current shape.
- Web index: `web/src/pages/forum/CategoryListPage.tsx` renders a flat
  "Boards" grid of `CategoryCard`s.
- Read state: per-topic reads (`models/topic_reads.py`) plus
  `ForumProfile.read_watermark_at` (`models/profiles.py:138`); no endpoint
  writes the watermark (no "mark all read" yet). No per-forum read state.
- Watching: topic-level only (`models/subscriptions.py` `TopicSubscription`).
- Moderation permission: Wagtail model permissions on Post/Topic
  (`admin_views.py:305` `user_can_moderate_pending`) — global, not per forum.

## 4. Target model

One table, `Forum` (plain Django model, `ClusterableModel` if inline panels are
needed), replacing `ForumBoard`:

| Field | Notes |
|---|---|
| `id` | **Copied from the ForumBoard page id** so existing topic URLs survive |
| `forum_type` | `category` / `forum` / `link` |
| `parent` | FK to self, null. Only a `category` may be a parent; categories have no parent. |
| `position` | integer sibling order |
| `name`, `slug` | slug **unique forum-wide among forums and links** — a partial `UniqueConstraint(fields=["slug"], condition=~Q(forum_type="category"))`, because `/forum/boards/{slug}/` only ever resolves forums. Category slugs are unique among categories only. This removes the 409 ambiguity and means the migration's default "General" category can never collide with an existing board slug. |
| `description` | plain text (existing contract) |
| `topic_count`, `post_count` | the existing denormalized counters move over. `ForumBoard` has **no** last-post cache — last-post data lives on `Topic` (`last_post_at`, `last_post_author`), so a row's newest post is computed from its topics at read time. |
| `is_hidden` | interim visibility flag, replaced by permissions (slices 675–677) |
| later slices | status/locked, rules, icon/colour/image, topics per page, default sort, link URL + clicks, topic template, prune settings, password, theme |

Decisions:

- **Can a forum sit at root with no category?** No. Every forum has a category
  parent; the slice-1 migration creates one default category ("General") and
  parents every existing board under it. Simplest rendering, no dummy header.
- Adjacency list (`parent` + `position`), **not** nested sets or treebeard —
  depth is two, so every move is a one-row update.
- Category rows aggregate their forums' counts and newest last post **at read
  time**, filtered by what the viewer may see (phpBB's approach).
- **One table, not `Category` + `Forum` tables.** With depth fixed at two, two
  tables would drop the self-FK and the parent-type validation; one table was
  chosen because it keeps the deferred subforums a validation change rather
  than a schema migration, and phpBB's type changes (forum ↔ category ↔ link)
  stay a field update instead of a row move between tables.
- Category rows with **zero visible forums are omitted** from the index (phpBB
  does the same), so a category whose only forum is hidden never renders as an
  empty header.
- `Topic.board` **keeps its name and `related_name="topics"`** — the FK only
  repoints from `ForumBoard` to `Forum` and switches to `PROTECT` (slice 1), so
  no path can cascade-delete topics. Renaming it to `forum` would roughly
  double the test churn. The `uniq_topic_slug_per_board` constraint and the
  `(board, -last_post_at)` index are regenerated by the FK change.
- `ForumIndex` stays as the single page placing the forum on the site (intro,
  event hero); `subpage_types = []`. Its `get_context` fallback
  (`models/boards.py`, audit H17) uses `get_children()` and must switch to the
  `Forum` model.
- **Migration order for the old pages:** in a `RunPython` that runs **before**
  the `RemoveModel(ForumBoard)` operation, delete each board through the
  historical `ForumBoard` model (that removes its `wagtailcore_page` base row
  too), then recompute `ForumIndex.numchild`, because historical-model deletes
  bypass treebeard. Otherwise orphan base rows with a dead content type break
  the page explorer. `manage.py fixtree --noinput` must report nothing
  afterwards.
- `/forum/boards/` (the Flutter contract) lists **only `forum_type="forum"`
  rows** — never categories or links. Flutter would otherwise open a link and
  fetch `/topics/` on it.
- **Web naming:** `web/src` already calls boards "categories" (`fetchCategories`,
  the `Category` type, `CategoryListPage`, `CategoryCard`). Slice 1 must give
  real categories a distinct name in the web model (e.g. `ForumSection`) or
  rename the existing board types to `Forum`, and say which.

Out of scope (deferred): subforums, the "Subforums:" line, `display_subforum_list`,
`display_on_index` legend toggles, multi-level breadcrumbs.

## 5. Admin (inside Wagtail, not the page explorer)

A *Forum* menu in the Wagtail sidebar (registered like the existing moderation
queue in `wagtail_hooks.py`):

- **Structure tree** (main screen): categories with their forums, drag and drop
  to reorder categories, reorder forums within a category, and move a forum to
  another category. A pinned copy of SortableJS (Wagtail's bundled copy is not a
  public API). One move endpoint, validated server-side.
- **Create / edit** forms via Wagtail `ModelViewSet`, tabs grouped like phpBB's
  ACP (General, Display, Rules, Pruning, Permissions).
- **Delete** with "move topics to… / delete topics"; **change type** as its own
  action with phpBB's rules (simplified for two levels).

## 6. Slice map

| Todo | Slice | Depends on |
|---|---|---|
| 665 | Forum model + migration off pages + category headers on the web index | — |
| 666 | Forum admin: Wagtail menu, create/edit forms | 665 |
| 667 | Safe delete (move/delete topics) + change type | 666 |
| 668 | Drag-and-drop structure tree | 666 |
| 669 | Display settings: locked, rules, icon/colour/image, topics per page, default sort | 666 |
| 670 | Link forums + click tracking | 666 |
| 671 | Read state: per-forum unread, mark forum read, mark all read | 665 |
| 672 | Watch / Track / Mute per forum | 665 |
| 673 | Collapsible categories (per user) | 665 |
| 674 | Per-forum moderators + "Moderators:" line | 666 |
| 675 | Permissions A: roles + per-group grants + copy permissions (admin) | 666 |
| 676 | Permissions B: read enforcement everywhere (replaces `is_hidden`) | 675 |
| 677 | Permissions C: write enforcement (post/reply/poll/attach) + web UI | 676 |
| 678 | Topic template per forum | 666 |
| 679 | Auto-pruning | 666 |
| 680 | Forum passwords | 676 |
| 681 | Per-forum theme override | 669 |
