# Wagtail Forum — Plan 1D: Host Integration + Retire django-machina

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the `wagtail_forum` package into the plant app — mount its API, create the moderation workflow + moderator group, and forward forum events to FCM push — then remove django-machina and the old `apps.forum_integration` entirely (greenfield, no data migration).

**Architecture:** A thin host app `apps.forum_host` owns everything plant-specific: a data migration that bootstraps the workflow + moderator `Group`, and signal handlers that turn the package's `reply_added`/`topic_created`/`moderation_decided` signals into FCM notifications. The reusable package stays untouched and host-agnostic. Machina's settings/urls/requirements/app are deleted last, after the new forum is proven mounted.

**Tech Stack:** Django, Wagtail workflows, DRF, existing Firebase/FCM infra.

**Depends on:** Plans 1A–1C. **Run every command from `backend/`.**

> **Exact-location references** (from codebase audit; verify before editing as line numbers may have shifted):
>
> - `backend/plant_community_backend/settings.py`: `ENABLE_FORUM` ~L169; `MACHINA_APPS` ~L172–187; conditional `LOCAL_APPS` insert ~L199–201; `MACHINA_*` config ~L750–771; `HAYSTACK_CONNECTIONS` ~L767–771.
> - `backend/plant_community_backend/urls.py`: forum include (v1) ~L126–128; legacy ~L154–156.
> - `backend/requirements.txt`: `django-machina==1.3.1` ~L55, `django-mptt==0.18.0` ~L57, `django-haystack==3.3.0` ~L52.

---

## Task 1: Create the `apps.forum_host` integration app + mount the API

**Files:**

- Create: `backend/apps/forum_host/__init__.py`
- Create: `backend/apps/forum_host/apps.py`
- Create: `backend/apps/forum_host/migrations/__init__.py`
- Modify: `backend/plant_community_backend/settings.py` (add `apps.forum_host` to `LOCAL_APPS`)
- Modify: `backend/plant_community_backend/urls.py` (mount `wagtail_forum.api.urls`)
- Create: `backend/apps/forum_host/tests/__init__.py`
- Create: `backend/apps/forum_host/tests/test_api_mounted.py`

- [ ] **Step 1: Write the failing test**

`backend/apps/forum_host/tests/test_api_mounted.py`:

```python
import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_forum_boards_endpoint_is_mounted():
    resp = APIClient().get("/api/v1/forum/boards/")
    assert resp.status_code == 200
    assert "results" in resp.data
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest apps/forum_host/tests/test_api_mounted.py -v`
Expected: FAIL — 404 (not mounted).

- [ ] **Step 3: Create the host app and mount the API**

`backend/apps/forum_host/__init__.py`: (empty file)

`backend/apps/forum_host/apps.py`:

```python
from django.apps import AppConfig


class ForumHostAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.forum_host"
    label = "forum_host"
    verbose_name = "Forum Host Integration"

    def ready(self):
        from . import signals  # noqa: F401  (wired in Task 3)
```

> Defer the `ready()` import of `signals` until Task 3 creates it. For this task,
> use a `ready()` with `pass` (no import), then add the import in Task 3.

`backend/apps/forum_host/apps.py` (Task 1 version):

```python
from django.apps import AppConfig


class ForumHostAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.forum_host"
    label = "forum_host"
    verbose_name = "Forum Host Integration"
```

`backend/apps/forum_host/migrations/__init__.py`: (empty file)
`backend/apps/forum_host/tests/__init__.py`: (empty file)

In `backend/plant_community_backend/settings.py`, add `"apps.forum_host"` to the `LOCAL_APPS` list (unconditionally, near `"wagtail_forum"`).

In `backend/plant_community_backend/urls.py`, mount the forum API at the v1 prefix. Add (in the v1 `api_v1_patterns` / wherever `path("forum/", ...)` lived):

```python
path("forum/", include("wagtail_forum.api.urls")),
```

so the full path is `/api/v1/forum/...`. (If you removed the old `ENABLE_FORUM`-gated `apps.forum_integration` include already, this replaces it; otherwise it is removed in Task 4.)

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest apps/forum_host/tests/test_api_mounted.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/forum_host backend/plant_community_backend/settings.py backend/plant_community_backend/urls.py
git commit -m "feat(forum_host): integration app + mount wagtail_forum API at /api/v1/forum/"
```

---

## Task 2: Data migration — moderation workflow + moderator group

**Files:**

- Create: `backend/apps/forum_host/migrations/0001_forum_bootstrap.py`
- Create: `backend/apps/forum_host/tests/test_bootstrap.py`

- [ ] **Step 1: Write the failing test**

`backend/apps/forum_host/tests/test_bootstrap.py`:

```python
import pytest
from django.contrib.auth.models import Group
from wagtail.models import Workflow

from wagtail_forum.models import Post
from wagtail_forum.workflow import DEFAULT_WORKFLOW_NAME


@pytest.mark.django_db
def test_bootstrap_created_workflow_and_group():
    # Migrations have run; the bootstrap data migration should have created both.
    assert Workflow.objects.filter(name=DEFAULT_WORKFLOW_NAME).exists()
    assert Group.objects.filter(name="Forum Moderators").exists()


@pytest.mark.django_db
def test_post_resolves_the_default_workflow():
    # A workflow is assigned to the Post content type.
    from wagtail_forum.models import ForumBoard, ForumIndex, Topic
    from wagtail.models import Page

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t")
    post = Post.objects.create(topic=topic, is_opening_post=True)

    assert post.get_workflow() is not None
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest apps/forum_host/tests/test_bootstrap.py -v`
Expected: FAIL — workflow/group don't exist.

- [ ] **Step 3: Write the data migration**

`backend/apps/forum_host/migrations/0001_forum_bootstrap.py`:

```python
from django.db import migrations


def bootstrap(apps, schema_editor):
    # Import the real (non-historical) helpers — safe here because this migration
    # depends on wagtail_forum's schema migrations being applied.
    from django.contrib.auth.models import Group, Permission
    from wagtail_forum.workflow import ensure_default_workflow

    ensure_default_workflow()

    group, _ = Group.objects.get_or_create(name="Forum Moderators")
    wanted = Permission.objects.filter(
        content_type__app_label="wagtail_forum",
        content_type__model__in=["topic", "post"],
        codename__in=[
            "change_topic", "delete_topic", "change_post", "delete_post",
            "publish_topic", "publish_post",
        ],
    )
    group.permissions.add(*wanted)


def unbootstrap(apps, schema_editor):
    from django.contrib.auth.models import Group

    Group.objects.filter(name="Forum Moderators").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("forum_host", "__first__"),
        # Ensure wagtail_forum tables + the workflow models exist first.
        ("wagtail_forum", "__latest__"),
        ("wagtailcore", "__latest__"),
    ]

    operations = [migrations.RunPython(bootstrap, unbootstrap)]
```

> If `("wagtail_forum", "__latest__")` is rejected by Django's dependency
> resolver, replace it with the concrete latest migration name from
> `packages/wagtail_forum/wagtail_forum/migrations/` (e.g. `("wagtail_forum",
> "0006_…")`). The `publish_topic`/`publish_post` permissions exist because the
> models use `DraftStateMixin`; if a codename is absent in your Wagtail version,
> drop it from the list — the test only asserts the group exists.

- [ ] **Step 4: Run migrations + test**

Run:

```bash
python manage.py migrate forum_host
pytest apps/forum_host/tests/test_bootstrap.py -v
```

Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add backend/apps/forum_host/migrations/0001_forum_bootstrap.py backend/apps/forum_host/tests/test_bootstrap.py
git commit -m "feat(forum_host): bootstrap moderation workflow + Forum Moderators group"
```

---

## Task 3: Forward forum signals to FCM push

**Files:**

- Create: `backend/apps/forum_host/notifications.py`
- Create: `backend/apps/forum_host/signals.py`
- Modify: `backend/apps/forum_host/apps.py` (re-add `ready()` import)
- Create: `backend/apps/forum_host/tests/test_signals.py`

- [ ] **Step 1: Write the failing test**

`backend/apps/forum_host/tests/test_signals.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page

from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()


@pytest.mark.django_db
def test_publishing_a_reply_dispatches_a_host_notification(monkeypatch):
    events = []
    from apps.forum_host import notifications

    monkeypatch.setattr(notifications, "dispatch", lambda event, **kw: events.append(event))

    author = User.objects.create_user(username="ada", password="x")
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)

    opening = Post.objects.create(topic=topic, author=author, is_opening_post=True)
    opening.save_revision().publish()
    reply = Post.objects.create(topic=topic, author=author, is_opening_post=False)
    reply.save_revision().publish()

    assert "topic_created" in events
    assert "reply_added" in events
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest apps/forum_host/tests/test_signals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.forum_host.notifications'`.

- [ ] **Step 3: Write notifications + receivers + wire `ready()`**

`backend/apps/forum_host/notifications.py`:

```python
import logging

logger = logging.getLogger("forum_host.notifications")


def dispatch(event, **kwargs):
    """Send a forum event to FCM.

    Replace the log call with the project's FCM sender (e.g. enqueue a Celery
    task that calls the Firebase Admin SDK). Kept as a single seam so the
    delivery mechanism is swappable and unit-testable.
    """
    topic = kwargs.get("topic")
    logger.info("forum.%s topic=%s", event, getattr(topic, "id", None))
```

`backend/apps/forum_host/signals.py`:

```python
from django.dispatch import receiver

from wagtail_forum.signals import moderation_decided, reply_added, topic_created

from . import notifications


@receiver(topic_created)
def _on_topic_created(sender, topic, post, **kwargs):
    notifications.dispatch("topic_created", topic=topic, post=post)


@receiver(reply_added)
def _on_reply_added(sender, topic, post, **kwargs):
    notifications.dispatch("reply_added", topic=topic, post=post)


@receiver(moderation_decided)
def _on_moderation_decided(sender, **kwargs):
    notifications.dispatch("moderation_decided", **kwargs)
```

Update `backend/apps/forum_host/apps.py` `ready()`:

```python
    def ready(self):
        from . import signals  # noqa: F401
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest apps/forum_host/tests/test_signals.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/forum_host/notifications.py backend/apps/forum_host/signals.py backend/apps/forum_host/apps.py backend/apps/forum_host/tests/test_signals.py
git commit -m "feat(forum_host): forward forum signals to FCM dispatch seam"
```

---

## Task 4: Retire django-machina + `apps.forum_integration`

**Files:**

- Modify: `backend/plant_community_backend/settings.py` (remove machina + forum_integration)
- Modify: `backend/plant_community_backend/urls.py` (remove forum_integration includes)
- Modify: `backend/requirements.txt` (remove machina/mptt/haystack)
- Delete: `backend/apps/forum_integration/` (whole directory)

- [ ] **Step 1: Drop machina/forum_integration tables if they exist**

Greenfield: there is no data. If the active DB ever migrated these apps, revert them to zero BEFORE removing the code (otherwise the tables are orphaned but harmless):

```bash
python manage.py migrate forum_integration zero || echo "forum_integration not migrated; skipping"
python manage.py migrate forum_conversation zero || echo "machina not migrated; skipping"
```

(Order matters only if FKs exist; both are no-ops on a fresh DB where `ENABLE_FORUM` was `False`.)

- [ ] **Step 2: Remove from settings**

In `backend/plant_community_backend/settings.py`, delete:

- the entire `MACHINA_APPS = [...]` block (~L172–187),
- the conditional that inserts `apps.forum_integration` into `LOCAL_APPS` and appends `MACHINA_APPS` to `INSTALLED_APPS` (~L199–206) — keep `INSTALLED_APPS = DJANGO_APPS + WAGTAIL_APPS + THIRD_PARTY_APPS + LOCAL_APPS`,
- the `MACHINA_*` configuration block (~L750–766),
- the `HAYSTACK_CONNECTIONS` block (~L767–771).

Leave `ENABLE_FORUM` defined if other code reads it; otherwise remove it too. Grep to confirm: `grep -rn "ENABLE_FORUM\|MACHINA\|machina\|HAYSTACK\|haystack" backend/plant_community_backend/settings.py` → no remaining references.

- [ ] **Step 3: Remove from urls**

In `backend/plant_community_backend/urls.py`, delete the `apps.forum_integration` includes (~L126–128 and the legacy ~L154–156). The new include from Task 1 (`wagtail_forum.api.urls`) is the only forum route. Confirm: `grep -n "forum_integration" backend/plant_community_backend/urls.py` → nothing.

- [ ] **Step 4: Remove from requirements + uninstall**

In `backend/requirements.txt`, delete the lines: `django-machina==1.3.1`, `django-mptt==0.18.0`, `django-haystack==3.3.0`. (Keep `-e ./packages/wagtail_forum` from Plan 1A.)

```bash
pip uninstall -y django-machina django-mptt django-haystack || true
```

- [ ] **Step 5: Delete the old app**

```bash
git rm -r backend/apps/forum_integration
```

- [ ] **Step 6: Verify the project boots and nothing references the old app**

Run:

```bash
grep -rn "forum_integration\|machina" backend/apps backend/plant_community_backend --include=*.py || echo "clean"
python manage.py check
```

Expected: `clean` (or only references inside docs/comments you choose to leave), then `System check identified no issues`.

- [ ] **Step 7: Commit**

```bash
git add -A backend
git commit -m "refactor(forum): retire django-machina + apps.forum_integration"
```

---

## Task 5: Full backend verification

**Files:** none (verification)

- [ ] **Step 1: Run the forum package + host suites**

Run:

```bash
pytest packages/wagtail_forum apps/forum_host -v
```

Expected: all PASS.

- [ ] **Step 2: Run the broader backend test suite for regressions**

Run: `python manage.py test --keepdb` (or `pytest`)
Expected: no failures attributable to the machina removal. If an unrelated app imported from `apps.forum_integration`, fix that import (grep already flagged it in Task 4 Step 6).

- [ ] **Step 3: Migration + check**

Run:

```bash
python manage.py makemigrations --check --dry-run
python manage.py check
```

Expected: `No changes detected` and `System check identified no issues`.

- [ ] **Step 4: Final commit**

```bash
git add -A backend
git commit -m "chore(forum): finalize Spec 1 backend (Plan 1D host integration)" || echo "nothing to commit"
```

---

## Plan self-review

- **Spec coverage (1D / host-integration section):** mount API at `/api/v1/forum/` ✅ (T1); moderation workflow created ✅ (T2); global moderator group ✅ (T2, "Forum Moderators"); FCM push via host signal handlers ✅ (T3); retire machina (settings/urls/requirements/app/tables) ✅ (T4); greenfield, no data migration ✅ (T4 Step 1 is a no-op on a fresh DB).
- **Placeholder scan:** the FCM `dispatch` is a real, runnable, tested seam (logs + documented swap point), not a TODO. No other placeholders.
- **Type/name consistency:** `DEFAULT_WORKFLOW_NAME`, `ensure_default_workflow`, package signals `topic_created`/`reply_added`/`moderation_decided` reused with matching names from Plans 1B; `Forum Moderators` group name consistent across T2 migration and test.
- **Risk flagged in-task:** the data-migration dependency spec (`"__latest__"`) and the `publish_*` permission codenames are verified at red-test time (T2 note).

---

## Spec 1 complete

With Plans 1A–1D done, Spec 1 is delivered: a reusable, Wagtail-native forum package with workflow moderation, trust routing, pluggable spam, reactions, profiles, search, and a mobile-first DRF API — wired into the plant app, with django-machina fully retired. **Spec 2** (updating the React web + Flutter mobile clients to this API) is the next, separate brainstorming → spec → plan cycle.
