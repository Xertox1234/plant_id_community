# Retire django-machina Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove django-machina, django-mptt, django-haystack, `apps.forum_integration`, and `apps.search` from the backend without breaking core account/dashboard code, repointing the `dashboard_stats` endpoint to the live `wagtail_forum` models.

**Architecture:** Decouple-first, then delete, then uninstall — in that order, with the full test suite green after every task. Machina stays pip-installed until the final task, so every intermediate commit is runnable and bisectable. All removed machina-coupled code is provably dead (verified caller-traces, see spec §2), so deletions are behavior-preserving; the one piece of new behavior is the `dashboard_stats` repoint, which is built test-first.

**Tech Stack:** Django 5 / DRF, Wagtail (the new `wagtail_forum` package), pytest (CI runner) over Django `TestCase` style tests, PostgreSQL + Redis.

**Spec:** `docs/superpowers/specs/2026-06-08-retire-django-machina-design.md`

**Branch:** `refactor/retire-machina` (already created and checked out; the spec is already committed on it).

**Environment note:** The system `git` requires `DEVELOPER_DIR=/Library/Developer/CommandLineTools` prefixed on this machine (Xcode license). All `git` commands below assume that env var is exported. The `markdownlint` pre-commit hook reformats `.md` files and aborts the first commit — if a commit aborts with "files were modified by this hook", `git add` the file again and re-run the commit. The `kimi-review` hook gates on `[CRITICAL]` findings only. The `flake8` pre-commit hook lints each **whole** changed `.py` file (not just changed lines); `services.py` and `views.py` are large and may carry pre-existing violations. If a commit is blocked by flake8 on lines you did **not** touch, prefer fixing them if trivial, else `SKIP=flake8 git commit …` (last resort) — never silence violations you introduced.

**Test command (used throughout):** `cd backend && source venv/bin/activate && python -m pytest apps packages -q` (full suite). Per-test: `python -m pytest <path>::<Class>::<method> -v`.

---

## File Structure

| File | Change | Responsibility after change |
|------|--------|------------------------------|
| `backend/apps/users/tests/test_dashboard_stats.py` | **Create** | Test `dashboard_stats` forum portion against `wagtail_forum` |
| `backend/apps/users/views.py` | Modify | `dashboard_stats` repointed; `forum_activity` + `forum_permissions` deleted |
| `backend/apps/users/urls.py` | Modify | Routes for `forum_activity` + `forum_permissions` removed |
| `backend/apps/users/services.py` | Modify | No machina imports/methods; trust + notification + demo (non-forum) logic only |
| `backend/apps/forum_integration/` | **Delete** | (gone) |
| `backend/apps/search/` | **Delete** | (gone) |
| `backend/pytest.ini` | Modify | Drop the two `forum_integration` `--ignore` lines |
| `backend/plant_community_backend/settings.py` | Modify | No machina/haystack footprint; `ENABLE_FORUM` + `wagtail.search` retained |
| `backend/plant_community_backend/urls.py` | Modify | Commented `apps.search` includes removed; confirmed no machina refs |
| `backend/requirements.txt` | Modify | `django-machina`, `django-mptt`, `django-haystack` removed |

---

## Task 1: Repoint `dashboard_stats` to `wagtail_forum` (TDD)

**Files:**

- Create: `backend/apps/users/tests/test_dashboard_stats.py`
- Modify: `backend/apps/users/views.py` (the `dashboard_stats` function, currently ~L638-788)

- [ ] **Step 1: Write the failing test**

Create `backend/apps/users/tests/test_dashboard_stats.py`:

```python
"""Tests for the dashboard_stats endpoint's forum portion (wagtail_forum)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()

DASHBOARD_URL = "/api/v1/auth/me/dashboard-stats/"


class DashboardStatsForumTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="ada", password="TestPass123!")
        # Build the wagtail_forum page tree: root -> ForumIndex -> ForumBoard
        root = Page.objects.get(id=1)
        index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
        self.board = index.add_child(instance=ForumBoard(title="General", slug="general"))

    def _topic(self, slug, *, live):
        return Topic.objects.create(
            board=self.board, title=slug.title(), slug=slug, author=self.user, live=live
        )

    def test_forum_stats_count_only_live_content_by_user(self):
        live_topic = self._topic("live", live=True)
        Post.objects.create(topic=live_topic, author=self.user, is_opening_post=True, live=True)
        Post.objects.create(topic=live_topic, author=self.user, is_opening_post=False, live=True)

        draft_topic = self._topic("draft", live=False)
        Post.objects.create(topic=draft_topic, author=self.user, is_opening_post=True, live=False)

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(DASHBOARD_URL)

        self.assertEqual(resp.status_code, 200)
        forum = resp.data["forum_stats"]
        self.assertEqual(forum["total_topics"], 1)   # live topic only
        self.assertEqual(forum["total_posts"], 2)    # 2 live posts; draft excluded
        self.assertEqual(forum["topics_this_month"], 1)
        self.assertEqual(forum["posts_this_month"], 2)

    def test_recent_activity_url_uses_live_web_forum_scheme(self):
        live_topic = self._topic("hello-world", live=True)
        Post.objects.create(topic=live_topic, author=self.user, is_opening_post=True, live=True)

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(DASHBOARD_URL)

        self.assertEqual(resp.status_code, 200)
        forum_items = [a for a in resp.data["recent_activity"] if a["type"].startswith("forum")]
        self.assertTrue(forum_items)
        expected = (
            f"/forum/{self.board.id}-{self.board.slug}"
            f"/{live_topic.id}-{live_topic.slug}"
        )
        self.assertTrue(all(item["url"] == expected for item in forum_items))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && source venv/bin/activate && python -m pytest apps/users/tests/test_dashboard_stats.py -v`
Expected: FAIL — `dashboard_stats` currently queries machina `Topic`/`Post`, so `total_topics`/`total_posts` come back `0` (and there are no forum `recent_activity` items), tripping the assertions.

- [ ] **Step 3: Repoint `dashboard_stats` in `backend/apps/users/views.py`**

Replace the machina import and the forum-stats / recent-forum-activity blocks. **Change the import line** inside `dashboard_stats`:

```python
    # was: from machina.apps.forum_conversation.models import Post, Topic
    from wagtail_forum.models import Post, Topic
```

Also reduce the `django.db.models` import inside this function from `from django.db.models import Case, Count, IntegerField, Q, When` to **`from django.db.models import Count, Q`** — `Case`, `IntegerField`, and `When` are pre-existing dead imports (never referenced in the function body) and the rewritten function uses only `Count` and `Q`; trimming them keeps the flake8 whole-file lint clean on commit.

Replace the **forum aggregation** block:

```python
    # OPTIMIZATION: Single aggregation query per model for forum stats
    forum_aggregation = Topic.objects.filter(
        author=request.user, live=True
    ).aggregate(
        total_topics=Count("id"),
        topics_this_month=Count("id", filter=Q(created_at__gte=thirty_days_ago)),
    )
    post_aggregation = Post.objects.filter(
        author=request.user, live=True
    ).aggregate(
        total_posts=Count("id"),
        posts_this_month=Count("id", filter=Q(created_at__gte=thirty_days_ago)),
    )

    forum_stats = {
        "total_topics": forum_aggregation["total_topics"],
        "total_posts": post_aggregation["total_posts"],
        "topics_this_month": forum_aggregation["topics_this_month"],
        "posts_this_month": post_aggregation["posts_this_month"],
    }
```

Add a URL helper just above the `recent_activity` assembly (mirrors `web/src/utils/forumUrls.ts`):

```python
    def _forum_topic_url(topic):
        board = topic.board
        return f"/forum/{board.id}-{board.slug}/{topic.id}-{topic.slug}"
```

Replace the **recent forum topics** block:

```python
    recent_topics = (
        Topic.objects.filter(author=request.user, live=True)
        .select_related("board")
        .only("id", "title", "slug", "created_at", "board__id", "board__slug", "board__title")
        .order_by("-created_at")[:2]
    )

    for topic in recent_topics:
        recent_activity.append(
            {
                "type": "forum_topic",
                "title": f"Created topic: {topic.title}",
                "description": f"in {topic.board.title}",
                "timestamp": topic.created_at,
                "url": _forum_topic_url(topic),
                "icon": "message-circle",
            }
        )
```

Replace the **recent forum posts** block (note: opening posts excluded via `is_opening_post=False`, replacing the old `first_post_id` exclusion):

```python
    recent_posts = (
        Post.objects.filter(author=request.user, live=True, is_opening_post=False)
        .select_related("topic", "topic__board")
        .only(
            "id", "created_at",
            "topic__id", "topic__title", "topic__slug",
            "topic__board__id", "topic__board__slug", "topic__board__title",
        )
        .order_by("-created_at")[:2]
    )

    for post in recent_posts:
        recent_activity.append(
            {
                "type": "forum_post",
                "title": f"Replied to: {post.topic.title}",
                "description": f"in {post.topic.board.title}",
                "timestamp": post.created_at,
                "url": _forum_topic_url(post.topic),
                "icon": "message-square",
            }
        )
```

Delete the now-unused `first_post_ids = Topic.objects.filter(...).values_list("first_post_id", ...)` lines. Leave `plant_stats`, `recent_identifications`, the `recent_activity.sort(...)`, and `total_activity_score` blocks unchanged (the score still reads `forum_stats["total_topics"]` / `["total_posts"]`).

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest apps/users/tests/test_dashboard_stats.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Run the users suite to confirm no regression**

Run: `python -m pytest apps/users -q`
Expected: all pass. (`dashboard_stats` had no prior test; nothing else references the changed blocks.)

- [ ] **Step 6: Commit**

```bash
git add backend/apps/users/views.py backend/apps/users/tests/test_dashboard_stats.py
git commit -m "refactor(users): repoint dashboard_stats forum stats to wagtail_forum (todo 220)"
```

---

## Task 2: Delete `forum_activity` and `forum_permissions` endpoints

**Files:**

- Modify: `backend/apps/users/views.py` (delete the two functions, currently ~L579-635 and ~L791-848)
- Modify: `backend/apps/users/urls.py` (delete routes L45 and L48)

- [ ] **Step 1: Delete the two view functions**

In `backend/apps/users/views.py`, delete the entire `forum_activity` function (its `@api_view(["GET"])` + `@permission_classes([...])` decorators through its `return Response(...)`) and the entire `forum_permissions` function likewise. `forum_activity` is the one importing `from apps.forum_integration.serializers import PostSerializer, TopicSerializer` and `from machina.apps.forum_conversation.models import Post, Topic`; `forum_permissions` is the one importing `from machina.apps.forum.models import Forum`. After deletion, `views.py` must contain **zero** `machina` references.

- [ ] **Step 2: Delete the routes in `backend/apps/users/urls.py`**

Remove these two lines (and the now-orphaned `# User forum activity and dashboard stats` comment is fine to keep or trim — keep `dashboard-stats`):

```python
    path("me/forum-activity/", views.forum_activity, name="forum_activity"),
    path("forum-permissions/", views.forum_permissions, name="forum_permissions"),
```

Keep `path("me/dashboard-stats/", views.dashboard_stats, name="dashboard_stats"),`.

- [ ] **Step 3: Verify no dangling references**

Run: `cd backend && grep -rn "forum_activity\|forum_permissions" apps/users`
Expected: no matches (function defs and routes both gone).

Run: `grep -rn "machina" apps/users/views.py`
Expected: no matches.

- [ ] **Step 4: Run the users suite**

Run: `python -m pytest apps/users -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/users/views.py backend/apps/users/urls.py
git commit -m "refactor(users): delete unused machina-coupled forum_activity + forum_permissions endpoints (todo 220)"
```

---

## Task 3: Sever machina from `apps/users/services.py`

**Files:**

- Modify: `backend/apps/users/services.py`

All of the following are provably dead (spec §2): zero callers, or the only caller (`forum_permissions`) was deleted in Task 2.

- [ ] **Step 1: Remove the module-level machina imports and lookups**

Delete these lines near the top of `services.py`:

```python
from machina.apps.forum.models import Forum
from machina.core.loading import get_class
```

and the block:

```python
# Import Django Machina models
ForumPermission = apps.get_model("forum_permission", "ForumPermission")
GroupForumPermission = apps.get_model("forum_permission", "GroupForumPermission")
UserForumPermission = apps.get_model("forum_permission", "UserForumPermission")
PermissionHandler = get_class("forum_permission.handler", "PermissionHandler")
```

Also remove `from django.apps import apps` (top of file) — verified its only uses are the three `apps.get_model(...)` lines just deleted, so it is now unused. (This is the `django.apps` registry import; leave the unrelated `from apps.core.utils...` project imports alone.)

- [ ] **Step 2: Delete the dead machina methods**

In `class TrustLevelService`, delete the `setup_forum_permissions` static method (uses `Forum`, `ForumPermission`, `GroupForumPermission`) and the `check_user_can_attach_files` static method (uses `PermissionHandler`). Delete the entire `class ForumPostService:` (its only method, `update_user_post_count`, imports `from machina.apps.forum_conversation.models import Post`).

- [ ] **Step 3: Remove the demo-forum machina code**

In `create_demo_data` (the method that builds the `created_items` dict), delete the block:

```python
            # Create demo forum posts (if forum is enabled)
            if self._is_forum_enabled():
                forum_posts = self._create_demo_forum_posts()
                created_items["forum_posts_count"] = len(forum_posts)
```

Keep `created_items["forum_posts_count"] = 0` in the initial dict (response shape preserved).

Delete the entire `_create_demo_forum_posts` method (imports machina `Forum`/`Post`/`Topic`).

In `cleanup_demo_data`, delete the block:

```python
            # Delete demo forum posts (if forum enabled)
            if self._is_forum_enabled():
                try:
                    from machina.apps.forum_conversation.models import Post, Topic

                    Topic.objects.filter(poster=self.user, is_demo_data=True).delete()
                    Post.objects.filter(poster=self.user, is_demo_data=True).delete()
                except Exception as e:
                    logger.warning(f"Could not delete demo forum posts: {e}")
```

Delete the now-unused `_is_forum_enabled` method:

```python
    def _is_forum_enabled(self):
        """Check if forum functionality is enabled."""
        return getattr(settings, "ENABLE_FORUM", False)
```

- [ ] **Step 4: Verify the file is machina-free and imports cleanly**

Run: `cd backend && grep -n "machina\|_is_forum_enabled\|ForumPostService\|setup_forum_permissions\|check_user_can_attach_files\|_create_demo_forum_posts" apps/users/services.py`
Expected: no matches.

Run: `python -c "import django; django.setup(); import apps.users.services" 2>&1 | tail -5` (with `DJANGO_SETTINGS_MODULE=plant_community_backend.settings` set, or use `python manage.py shell -c "import apps.users.services"`).
Expected: no ImportError. (Machina is still installed here, so this only proves the module no longer *references* machina symbols; the uninstalled-import proof is Task 7.)

- [ ] **Step 5: Run the full suite (account code is now machina-free)**

Run: `python -m pytest apps packages -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/apps/users/services.py
git commit -m "refactor(users): remove module-level machina imports + dead forum-permission/demo methods (todo 220)"
```

---

## Task 4: Delete `apps/forum_integration`

**Files:**

- Delete: `backend/apps/forum_integration/` (entire directory)
- Modify: `backend/pytest.ini`

- [ ] **Step 1: Delete the app directory**

```bash
cd backend && git rm -r apps/forum_integration
```

- [ ] **Step 2: Drop the `pytest.ini` ignore lines**

In `backend/pytest.ini`, delete these two lines (currently L20-21):

```ini
    --ignore=apps/forum_integration/tests.py
    --ignore=apps/forum_integration/tests
```

- [ ] **Step 3: Verify no dangling imports of forum_integration outside the (already-disabled) machina-gated settings block**

Run: `grep -rn "forum_integration" apps plant_community_backend --include=*.py`
Expected: only matches inside `plant_community_backend/settings.py`'s `if ENABLE_FORUM:` blocks (removed in Task 6) — i.e. `LOCAL_APPS.insert(2, "apps.forum_integration")` and the context-processor / template-dir lines. No matches in any `apps/*` runtime code.

- [ ] **Step 4: Run the full suite + system check**

Run: `python -m pytest apps packages -q`
Expected: all pass. (Pytest count unchanged — those tests were already ignored.)

Run: `python manage.py check`
Expected: `System check identified no issues`.

- [ ] **Step 5: Commit**

```bash
git add backend/pytest.ini
git commit -m "refactor: delete apps.forum_integration + its pytest ignore lines (todo 220)"
```

---

## Task 5: Delete `apps/search`

**Files:**

- Delete: `backend/apps/search/` (entire directory)
- Modify: `backend/plant_community_backend/urls.py` (commented includes)

- [ ] **Step 1: Delete the app directory**

```bash
cd backend && git rm -r apps/search
```

- [ ] **Step 2: Remove the commented urlconf includes**

In `backend/plant_community_backend/urls.py`, delete these commented lines (currently ~L126 and ~L146):

```python
                    # path('search/', include('apps.search.urls')),  # Temporarily disabled (depends on Machina)
```

```python
                # path('search/', include('apps.search.urls')),  # Temporarily disabled (depends on Machina)
```

(The commented `LOCAL_APPS` line `# 'apps.search', ...` in `settings.py` L195 is removed in Task 6.)

- [ ] **Step 3: Verify**

Run: `grep -rn "apps.search\|apps/search" apps plant_community_backend --include=*.py`
Expected: at most the single commented `# 'apps.search',` line in `settings.py` (removed next task). No runtime references. (`settings.py` OpenAPI tag literally named `"search"` is unrelated — leave it.)

- [ ] **Step 4: Run the full suite + system check + migration check**

Run: `python -m pytest apps packages -q`
Expected: all pass.

Run: `python manage.py check && python manage.py makemigrations --check --dry-run`
Expected: check passes; `makemigrations --check` reports **no changes** (confirms no orphaned migration state from the two deleted apps slipped in).

- [ ] **Step 5: Commit**

```bash
git add backend/plant_community_backend/urls.py
git commit -m "refactor: delete disabled apps.search (machina/haystack-dependent) (todo 220)"
```

---

## Task 6: Strip the machina footprint from `settings.py`

**Files:**

- Modify: `backend/plant_community_backend/settings.py`

- [ ] **Step 1: Remove the apps wiring**

Delete the `MACHINA_APPS` definition block:

```python
# Django Machina Apps (optional)
MACHINA_APPS = []
if ENABLE_FORUM:
    MACHINA_APPS = [
        "machina",
        "machina.apps.forum",
        "machina.apps.forum_conversation",
        "machina.apps.forum_conversation.forum_attachments",
        "machina.apps.forum_conversation.forum_polls",
        "machina.apps.forum_feeds",
        "machina.apps.forum_moderation",
        "machina.apps.forum_search",
        "machina.apps.forum_tracking",
        "machina.apps.forum_member",
        "machina.apps.forum_permission",
        "haystack",
    ]
```

In `LOCAL_APPS`, delete the commented line `# 'apps.search',  # Temporarily disabled (depends on Machina)`.

Delete the forum_integration insert:

```python
if ENABLE_FORUM:
    # Machina forum integration shim
    LOCAL_APPS.insert(2, "apps.forum_integration")
```

Delete the MACHINA_APPS append (leave the plain `INSTALLED_APPS = DJANGO_APPS + WAGTAIL_APPS + THIRD_PARTY_APPS + LOCAL_APPS` line):

```python
if ENABLE_FORUM:
    # MACHINA_APPS will be removed once the new headless forum is production-ready
    INSTALLED_APPS += MACHINA_APPS
```

- [ ] **Step 2: Remove middleware, context processors, template dir**

Delete the commented machina middleware block:

```python
# Include forum permission middleware only when forum is enabled
# Temporarily disabled (depends on Machina)
# if ENABLE_FORUM:
#     MIDDLEWARE.append('machina.apps.forum_permission.middleware.ForumPermissionMiddleware')
```

Delete the context-processor block:

```python
if ENABLE_FORUM:
    _base_context_processors += [
        "machina.core.context_processors.metadata",
        "apps.forum_integration.context_processors.forum_globals",
    ]
```

Delete the template-dir block:

```python
if ENABLE_FORUM:
    _template_dirs.append(BASE_DIR / "apps" / "forum_integration" / "templates")
```

- [ ] **Step 3: Remove the `machina_attachments` cache entries**

Delete the `"machina_attachments": { ... }` entry from **both** the Redis `CACHES` dict and the locmem-fallback `CACHES` dict (the `django_redis` one with `KEY_PREFIX: "machina_attachments"`, and the `FileBasedCache` one with `LOCATION: BASE_DIR / "machina_attachments_cache"`).

- [ ] **Step 4: Remove the machina + haystack config blocks**

Delete:

```python
# Django Machina settings
MACHINA_DEFAULT_AUTHENTICATED_USER_FORUM_PERMISSIONS = [
    "can_see_forum",
    "can_read_forum",
    "can_start_new_topics",
    "can_reply_to_topics",
    "can_edit_own_posts",
    "can_post_without_approval",
    "can_create_polls",
    "can_vote_in_polls",
    "can_download_file",
]

MACHINA_PROFILE_AVATARS_PATH = "machina/avatars"
MACHINA_USER_DISPLAY = lambda u: u.get_full_name() if u.get_full_name() else u.username
```

and:

```python
# Search configuration
HAYSTACK_CONNECTIONS = {
    "default": {
        "ENGINE": "haystack.backends.simple_backend.SimpleEngine",
    },
}
```

**Retain** `ENABLE_FORUM = config(...)` (L169) and `"wagtail.search"` in `WAGTAIL_APPS` (L137) — neither is machina. `ENABLE_FORUM` is now defined-but-unused in settings; that is intentional per the spec (kept as a feature flag).

- [ ] **Step 5: Verify settings is machina-free**

Run: `cd backend && grep -n "machina\|haystack\|MACHINA\|HAYSTACK\|forum_integration" plant_community_backend/settings.py`
Expected: no matches.

Run: `python manage.py check`
Expected: `System check identified no issues` (machina is still pip-installed, so import resolution is unaffected; this proves settings no longer wires it).

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest apps packages -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/plant_community_backend/settings.py
git commit -m "refactor(settings): remove django-machina + haystack footprint (todo 220)"
```

---

## Task 7: Uninstall the packages and verify the end state

**Files:**

- Modify: `backend/requirements.txt`

- [ ] **Step 1: Remove the requirements**

In `backend/requirements.txt`, delete these three lines:

```text
django-haystack==3.3.0
django-machina==1.3.1
django-mptt==0.18.0
```

- [ ] **Step 2: Uninstall from the venv**

Run: `cd backend && source venv/bin/activate && pip uninstall -y django-machina django-mptt django-haystack`
Expected: all three uninstalled. (If `pip check` flags an unrelated package that depended on mptt/haystack, stop and report — none is expected.)

- [ ] **Step 3: The critical proof — account code imports with machina GONE**

Run: `python manage.py check`
Expected: `System check identified no issues` — proves no remaining module imports machina at import time (this is the original "whole backend down" blocker; it must pass with machina uninstalled).

Run: `python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','plant_community_backend.settings'); django.setup(); import apps.users.services, apps.users.views; print('OK')"`
Expected: `OK`.

- [ ] **Step 4: Confirm `urls.py` has no machina/forum_integration refs**

Run: `grep -rn "machina\|forum_integration" plant_community_backend/urls.py`
Expected: no matches (legacy include already removed in Plan 1D-T1; the commented search includes removed in Task 5).

- [ ] **Step 5: Run every acceptance gate**

Run: `grep -rn "machina\|forum_integration" apps plant_community_backend --include="*.py"`
Expected: no matches (acceptance criterion #1).

Run: `python manage.py makemigrations --check --dry-run`
Expected: no changes.

Run: `python manage.py spectacular --file /tmp/schema.yml --validate`
Expected: schema generates and validates; `dashboard_stats` still present (`grep dashboard-stats /tmp/schema.yml`), `forum-activity`/`forum-permissions` absent.

Run: `python -m pytest apps packages -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt
git commit -m "build: drop django-machina, django-mptt, django-haystack (todo 220)"
```

---

## Final verification checklist (maps to spec §10 / todo 220)

- [ ] `grep -rn "machina\|forum_integration" backend/apps backend/plant_community_backend --include="*.py"` → clean.
- [ ] `apps/users/services.py` imports cleanly with machina uninstalled; `dashboard_stats` returns 200 and reflects `wagtail_forum` content.
- [ ] `django-machina`, `django-mptt`, `django-haystack` removed from `requirements.txt` and uninstalled from the venv.
- [ ] `apps/forum_integration/` and `apps/search/` deleted.
- [ ] `python manage.py check` clean; `makemigrations --check` clean; `spectacular --validate` clean; full `pytest apps packages` green.

## Notes for the executor

- **Do not push to `main`.** Work stays on `refactor/retire-machina`; open a PR at the end (the repo has branch protection).
- Machina must remain pip-installed through Tasks 1-6. Only Task 7 uninstalls it — that ordering is what keeps every intermediate commit runnable.
- Out of scope (do **not** do here): re-wiring `User.trust_level`/`posts_count_verified` to new-forum activity (the new forum owns its own `ForumProfile.trust_level`); React/Flutter client changes (nothing consumes the removed endpoints today).
