# Wagtail Forum — Plan 1A: Package Scaffold + Core Models + Admin + Search

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the installable `wagtail_forum` package with its core Wagtail-native data model (boards as Pages; topics/posts as feature-rich snippets; profiles; reactions), a Wagtail-admin management UI, and search indexing — a forum an admin can fully manage in the CMS, with no API yet.

**Architecture:** A standalone, editable-installed package under `backend/packages/wagtail_forum/`, importable as the top-level app `wagtail_forum`. `ForumIndex`/`ForumBoard` are Wagtail `Page`s; `Topic`/`Post` are non-page snippets composing `WorkflowMixin + DraftStateMixin + LockableMixin + RevisionMixin + index.Indexed`. The package imports nothing from the host's `apps.` namespace (enforced by a test).

**Tech Stack:** Django, Wagtail 7.4, PostgreSQL, pytest + `pytest-django`. This plan is part of **Spec 1** (`docs/superpowers/specs/2026-06-06-wagtail-native-forum-package-design.md`). Follow-on plans: **1B** (workflow moderation + trust + spam), **1C** (DRF API), **1D** (host integration + retire machina).

**Conventions (from the codebase):**

- Wagtail admin base URL is `/cms/` (NOT `/admin/`).
- Tests use `@pytest.mark.django_db` and/or Django `TestCase`; run with `python manage.py test wagtail_forum --keepdb` (Django runner) from `backend/`, or `pytest packages/wagtail_forum` from `backend/`.
- Run every command from `backend/` unless stated otherwise.
- This plan adds `wagtail_forum` to `INSTALLED_APPS` unconditionally; machina/`forum_integration` remain gated behind `ENABLE_FORUM` (default `False`) and are untouched until Plan 1D.

---

## Task 1: Package scaffold + editable install + test discovery

**Files:**

- Create: `backend/packages/wagtail_forum/pyproject.toml`
- Create: `backend/packages/wagtail_forum/README.md`
- Create: `backend/packages/wagtail_forum/wagtail_forum/__init__.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/apps.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/__init__.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_smoke.py`
- Modify: `backend/plant_community_backend/settings.py` (add `"wagtail_forum"` to `LOCAL_APPS`)
- Modify: `backend/pytest.ini` (add `packages` to `testpaths`)
- Modify: `backend/requirements.txt` (add editable install)

- [ ] **Step 1: Create the package metadata**

`backend/packages/wagtail_forum/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "wagtail-forum"
version = "0.1.0"
description = "A reusable, Wagtail-native community forum."
readme = "README.md"
requires-python = ">=3.11"
dependencies = ["Wagtail>=7.0"]

[project.optional-dependencies]
api = ["djangorestframework>=3.14"]

[tool.setuptools.packages.find]
include = ["wagtail_forum*"]
```

`backend/packages/wagtail_forum/README.md`:

```markdown
# wagtail-forum

A reusable, Wagtail-native community forum. Boards are Wagtail Pages; topics and
posts are feature-rich snippets (moderation workflow, revisions, locking, search).
Headless DRF API is optional (`pip install wagtail-forum[api]`).

The core imports nothing host-specific and uses `settings.AUTH_USER_MODEL`.
```

- [ ] **Step 2: Create the app config and package init**

`backend/packages/wagtail_forum/wagtail_forum/__init__.py`:

```python
# wagtail_forum is a reusable, Wagtail-native community forum package.
```

`backend/packages/wagtail_forum/wagtail_forum/apps.py`:

```python
from django.apps import AppConfig


class WagtailForumAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "wagtail_forum"
    label = "wagtail_forum"
    verbose_name = "Wagtail Forum"
```

`backend/packages/wagtail_forum/wagtail_forum/tests/__init__.py`: (empty file)

- [ ] **Step 3: Write the smoke test (failing)**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_smoke.py`:

```python
def test_package_imports():
    import wagtail_forum  # noqa: F401
    from wagtail_forum.apps import WagtailForumAppConfig

    assert WagtailForumAppConfig.label == "wagtail_forum"


def test_app_is_installed():
    from django.apps import apps

    assert apps.is_installed("wagtail_forum")
```

- [ ] **Step 4: Run the smoke test — verify it fails**

Run (from `backend/`): `pytest packages/wagtail_forum/wagtail_forum/tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wagtail_forum'` (not installed yet).

- [ ] **Step 5: Install the package (editable) and wire discovery**

Run (from `backend/`): `pip install -e ./packages/wagtail_forum`
Expected: `Successfully installed wagtail-forum-0.1.0`.

Add to `backend/requirements.txt` (new line at end):

```text
-e ./packages/wagtail_forum
```

In `backend/plant_community_backend/settings.py`, add `"wagtail_forum"` to the `LOCAL_APPS` list (the local-apps grouping around lines 190–201) so it loads unconditionally:

```python
LOCAL_APPS = [
    # ... existing local apps ...
    "wagtail_forum",
]
```

In `backend/pytest.ini`, extend `testpaths` so the package's tests are collected:

```ini
testpaths = apps packages
```

- [ ] **Step 6: Run the smoke test — verify it passes**

Run (from `backend/`): `pytest packages/wagtail_forum/wagtail_forum/tests/test_smoke.py -v`
Expected: PASS (both tests).

Also verify the bare import: `python -c "import wagtail_forum; print('ok')"` → prints `ok`.

- [ ] **Step 7: Commit**

```bash
git add backend/packages/wagtail_forum backend/plant_community_backend/settings.py backend/pytest.ini backend/requirements.txt
git commit -m "feat(wagtail_forum): scaffold installable package + app registration"
```

---

## Task 2: Board models (`ForumIndex`, `ForumBoard` as Pages)

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/models/__init__.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/models/boards.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_boards.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_boards.py`:

```python
import pytest
from wagtail.models import Page

from wagtail_forum.models import ForumBoard, ForumIndex


@pytest.mark.django_db
def test_board_nests_under_forum_index():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(
        instance=ForumBoard(title="General", slug="general", description="Chat")
    )

    assert board.get_parent().specific == index
    assert board.topic_count == 0
    assert board.post_count == 0
    assert list(index.get_children().type(ForumBoard)) == [board.page_ptr]
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_boards.py -v`
Expected: FAIL — `ModuleNotFoundError`/`ImportError` (no `models` package yet).

- [ ] **Step 3: Write the models**

`backend/packages/wagtail_forum/wagtail_forum/models/boards.py`:

```python
from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page


class ForumIndex(Page):
    """Root forum node. Lets a host site place the forum in its page tree."""

    intro = RichTextField(blank=True)

    subpage_types = ["wagtail_forum.ForumBoard"]
    content_panels = Page.content_panels + [FieldPanel("intro")]


class ForumBoard(Page):
    """A board/category — a low-volume structural node."""

    description = models.TextField(blank=True)
    # Denormalized counters (maintained as topics/posts change; see Task 7 / Plan 1B).
    topic_count = models.PositiveIntegerField(default=0, editable=False)
    post_count = models.PositiveIntegerField(default=0, editable=False)

    parent_page_types = ["wagtail_forum.ForumIndex"]
    subpage_types = []
    content_panels = Page.content_panels + [FieldPanel("description")]
```

`backend/packages/wagtail_forum/wagtail_forum/models/__init__.py`:

```python
from .boards import ForumBoard, ForumIndex

__all__ = ["ForumBoard", "ForumIndex"]
```

- [ ] **Step 4: Make and run migrations**

Run (from `backend/`):

```bash
python manage.py makemigrations wagtail_forum
```

Expected: creates `packages/wagtail_forum/wagtail_forum/migrations/0001_initial.py` defining `ForumIndex` and `ForumBoard`. (If the `migrations/` dir is missing, create `migrations/__init__.py` first, then re-run.)

- [ ] **Step 5: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_boards.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/models backend/packages/wagtail_forum/wagtail_forum/migrations backend/packages/wagtail_forum/wagtail_forum/tests/test_boards.py
git commit -m "feat(wagtail_forum): ForumIndex + ForumBoard page models"
```

---

## Task 3: `ForumProfile` (member + system fields)

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/models/profiles.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/models/__init__.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_profiles.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_profiles.py`:

```python
import pytest
from django.contrib.auth import get_user_model

from wagtail_forum.models import ForumProfile, TrustLevel

User = get_user_model()


@pytest.mark.django_db
def test_for_user_creates_profile_once():
    user = User.objects.create_user(username="ada", password="x")

    profile = ForumProfile.for_user(user)
    again = ForumProfile.for_user(user)

    assert profile.pk == again.pk
    assert profile.trust_level == TrustLevel.NEW
    assert profile.post_count == 0
    assert ForumProfile.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_str_prefers_display_name():
    user = User.objects.create_user(username="ada", password="x")
    profile = ForumProfile.for_user(user)
    profile.display_name = "Ada L."
    assert str(profile) == "Ada L."
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_profiles.py -v`
Expected: FAIL — `ImportError: cannot import name 'ForumProfile'`.

- [ ] **Step 3: Write the model**

`backend/packages/wagtail_forum/wagtail_forum/models/profiles.py`:

```python
from django.conf import settings
from django.db import models
from wagtail.images import get_image_model_string


class TrustLevel(models.IntegerChoices):
    NEW = 0, "New"
    BASIC = 1, "Basic"
    MEMBER = 2, "Member"
    REGULAR = 3, "Regular"
    LEADER = 4, "Leader"


class ForumProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_profile",
    )
    # Member-editable (via API in Plan 1C).
    display_name = models.CharField(max_length=80, blank=True)
    avatar = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    bio = models.TextField(blank=True)
    signature = models.CharField(max_length=255, blank=True)
    # System-computed (read-only to members).
    trust_level = models.PositiveSmallIntegerField(
        choices=TrustLevel.choices, default=TrustLevel.NEW
    )
    post_count = models.PositiveIntegerField(default=0)
    flags_received = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    @classmethod
    def for_user(cls, user):
        profile, _ = cls.objects.get_or_create(user=user)
        return profile

    def __str__(self):
        return self.display_name or self.user.get_username()
```

Update `backend/packages/wagtail_forum/wagtail_forum/models/__init__.py`:

```python
from .boards import ForumBoard, ForumIndex
from .profiles import ForumProfile, TrustLevel

__all__ = ["ForumBoard", "ForumIndex", "ForumProfile", "TrustLevel"]
```

- [ ] **Step 4: Make migrations**

Run: `python manage.py makemigrations wagtail_forum`
Expected: new migration `0002_*` adding `ForumProfile`.

- [ ] **Step 5: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_profiles.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/models backend/packages/wagtail_forum/wagtail_forum/migrations backend/packages/wagtail_forum/wagtail_forum/tests/test_profiles.py
git commit -m "feat(wagtail_forum): ForumProfile with member + system fields"
```

---

## Task 4: Forum-safe StreamField block set

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/blocks.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_blocks.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_blocks.py`:

```python
from wagtail_forum.blocks import ForumBodyBlock


def test_body_block_accepts_safe_blocks():
    block = ForumBodyBlock()
    value = block.to_python(
        [
            {"type": "heading", "value": "Hello"},
            {"type": "paragraph", "value": "<p>Hi there</p>"},
        ]
    )
    assert [child.block_type for child in value] == ["heading", "paragraph"]


def test_body_block_rejects_unknown_block_type():
    block = ForumBodyBlock()
    child_names = set(block.child_blocks.keys())
    assert "raw_html" not in child_names
    assert {"heading", "paragraph", "quote", "code", "image"} <= child_names
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_blocks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wagtail_forum.blocks'`.

- [ ] **Step 3: Write the block set**

`backend/packages/wagtail_forum/wagtail_forum/blocks.py`:

```python
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock


class CodeBlock(blocks.StructBlock):
    language = blocks.CharBlock(required=False)
    code = blocks.TextBlock()

    class Meta:
        icon = "code"


class ForumBodyBlock(blocks.StreamBlock):
    """The only blocks a forum post may contain. No raw HTML."""

    heading = blocks.CharBlock(form_classname="title")
    paragraph = blocks.RichTextBlock(
        features=["bold", "italic", "link", "ol", "ul", "code"]
    )
    quote = blocks.BlockQuoteBlock()
    code = CodeBlock()
    image = ImageChooserBlock()

    class Meta:
        required = False
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_blocks.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/blocks.py backend/packages/wagtail_forum/wagtail_forum/tests/test_blocks.py
git commit -m "feat(wagtail_forum): forum-safe StreamField block set"
```

---

## Task 5: `Topic` snippet (full mixins + counters + search)

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/models/topics.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/models/__init__.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_topics.py`

> **Note on `LockableMixin`:** it already provides editor-locking (`locked`, `locked_by`,
> `locked_at`). The forum's "no new replies" concept is the separate `is_closed`
> boolean. There is deliberately no `is_locked` field (it would collide).

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_topics.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page

from wagtail_forum.models import ForumBoard, ForumIndex, Topic

User = get_user_model()


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


@pytest.mark.django_db
def test_topic_publishes_via_revision():
    user = User.objects.create_user(username="ada", password="x")
    topic = Topic(board=_board(), title="Pothos help", slug="pothos-help", author=user)
    topic.save()

    revision = topic.save_revision()
    revision.publish()
    topic.refresh_from_db()

    assert topic.live is True
    assert topic.latest_revision is not None
    assert topic.reply_count == 0
    assert topic.is_closed is False


@pytest.mark.django_db
def test_topic_slug_unique_per_board():
    from django.db import IntegrityError

    board = _board()
    Topic.objects.create(board=board, title="A", slug="dup")
    with pytest.raises(IntegrityError):
        Topic.objects.create(board=board, title="B", slug="dup")
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_topics.py -v`
Expected: FAIL — `ImportError: cannot import name 'Topic'`.

- [ ] **Step 3: Write the model**

`backend/packages/wagtail_forum/wagtail_forum/models/topics.py`:

```python
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.models import (
    DraftStateMixin,
    LockableMixin,
    RevisionMixin,
    WorkflowMixin,
)
from wagtail.search import index


class Topic(
    WorkflowMixin,
    DraftStateMixin,
    LockableMixin,
    RevisionMixin,
    index.Indexed,
    models.Model,
):
    board = models.ForeignKey(
        "wagtail_forum.ForumBoard", on_delete=models.CASCADE, related_name="topics"
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="forum_topics",
    )
    is_pinned = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)  # no new replies

    # Denormalized for cheap mobile list rendering.
    reply_count = models.PositiveIntegerField(default=0, editable=False)
    view_count = models.PositiveIntegerField(default=0, editable=False)
    last_post_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_post_author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    _revisions = GenericRelation(
        "wagtailcore.Revision", related_query_name="forum_topic"
    )
    workflow_states = GenericRelation(
        "wagtailcore.WorkflowState",
        content_type_field="base_content_type",
        object_id_field="object_id",
        related_query_name="forum_topic",
        for_concrete_model=False,
    )

    search_fields = [
        index.SearchField("title"),
        index.AutocompleteField("title"),
    ]

    panels = [
        FieldPanel("board"),
        FieldPanel("title"),
        FieldPanel("slug"),
        FieldPanel("is_pinned"),
        FieldPanel("is_closed"),
    ]

    class Meta:
        ordering = ["-is_pinned", "-last_post_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["board", "slug"], name="uniq_topic_slug_per_board"
            )
        ]

    @property
    def revisions(self):
        return self._revisions

    def __str__(self):
        return self.title
```

Update `models/__init__.py`:

```python
from .boards import ForumBoard, ForumIndex
from .profiles import ForumProfile, TrustLevel
from .topics import Topic

__all__ = ["ForumBoard", "ForumIndex", "ForumProfile", "TrustLevel", "Topic"]
```

- [ ] **Step 4: Make migrations**

Run: `python manage.py makemigrations wagtail_forum`
Expected: new migration `0003_*` adding `Topic` (including mixin fields `live`, `latest_revision`, `locked`, etc.).

- [ ] **Step 5: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_topics.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/models backend/packages/wagtail_forum/wagtail_forum/migrations backend/packages/wagtail_forum/wagtail_forum/tests/test_topics.py
git commit -m "feat(wagtail_forum): Topic snippet with workflow/revision/lock/search"
```

---

## Task 6: `Post` snippet (StreamField body + opening-post flag)

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/models/posts.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/models/__init__.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_posts.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_posts.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page

from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()


def _topic(user):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    return Topic.objects.create(board=board, title="T", slug="t", author=user)


@pytest.mark.django_db
def test_opening_post_has_body_and_flag():
    user = User.objects.create_user(username="ada", password="x")
    topic = _topic(user)
    post = Post.objects.create(
        topic=topic,
        author=user,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>First!</p>"}],
    )

    post.refresh_from_db()
    assert post.is_opening_post is True
    assert post.reaction_counts == {}
    assert post.body[0].block_type == "paragraph"


@pytest.mark.django_db
def test_post_publishes_via_revision():
    user = User.objects.create_user(username="ada", password="x")
    post = Post.objects.create(topic=_topic(user), author=user)
    revision = post.save_revision()
    revision.publish()
    post.refresh_from_db()
    assert post.live is True
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_posts.py -v`
Expected: FAIL — `ImportError: cannot import name 'Post'`.

- [ ] **Step 3: Write the model**

`backend/packages/wagtail_forum/wagtail_forum/models/posts.py`:

```python
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import (
    DraftStateMixin,
    LockableMixin,
    RevisionMixin,
    WorkflowMixin,
)
from wagtail.search import index

from ..blocks import ForumBodyBlock


class Post(
    WorkflowMixin,
    DraftStateMixin,
    LockableMixin,
    RevisionMixin,
    index.Indexed,
    models.Model,
):
    topic = models.ForeignKey(
        "wagtail_forum.Topic", on_delete=models.CASCADE, related_name="posts"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="forum_posts",
    )
    body = StreamField(ForumBodyBlock(), blank=True)
    is_opening_post = models.BooleanField(default=False)
    edited = models.BooleanField(default=False)

    # Denormalized per-type reaction counts, e.g. {"like": 3, "thanks": 1}.
    reaction_counts = models.JSONField(default=dict, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    _revisions = GenericRelation(
        "wagtailcore.Revision", related_query_name="forum_post"
    )
    workflow_states = GenericRelation(
        "wagtailcore.WorkflowState",
        content_type_field="base_content_type",
        object_id_field="object_id",
        related_query_name="forum_post",
        for_concrete_model=False,
    )

    search_fields = [index.SearchField("body")]

    panels = [
        FieldPanel("topic"),
        FieldPanel("body"),
        FieldPanel("is_opening_post"),
    ]

    class Meta:
        ordering = ["created_at"]

    @property
    def revisions(self):
        return self._revisions

    def __str__(self):
        return f"Post #{self.pk} in {self.topic_id}"
```

Update `models/__init__.py`:

```python
from .boards import ForumBoard, ForumIndex
from .posts import Post
from .profiles import ForumProfile, TrustLevel
from .topics import Topic

__all__ = [
    "ForumBoard",
    "ForumIndex",
    "ForumProfile",
    "Post",
    "Topic",
    "TrustLevel",
]
```

- [ ] **Step 4: Make migrations**

Run: `python manage.py makemigrations wagtail_forum`
Expected: new migration `0004_*` adding `Post`.

- [ ] **Step 5: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_posts.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/models backend/packages/wagtail_forum/wagtail_forum/migrations backend/packages/wagtail_forum/wagtail_forum/tests/test_posts.py
git commit -m "feat(wagtail_forum): Post snippet with StreamField body + opening-post flag"
```

---

## Task 7: `Reaction` model + denormalized recount + topic counters

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/models/reactions.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/models/__init__.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_reactions.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_reactions.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from wagtail.models import Page

from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    Post,
    Reaction,
    Topic,
)

User = get_user_model()


def _post(author):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)
    return Post.objects.create(topic=topic, author=author, is_opening_post=True)


@pytest.mark.django_db
def test_recount_updates_post_counts():
    a = User.objects.create_user(username="a", password="x")
    b = User.objects.create_user(username="b", password="x")
    post = _post(a)

    Reaction.objects.create(post=post, user=a, reaction_type=Reaction.LIKE)
    Reaction.objects.create(post=post, user=b, reaction_type=Reaction.LIKE)
    Reaction.objects.create(post=post, user=b, reaction_type=Reaction.THANKS)
    Reaction.recount(post)

    post.refresh_from_db()
    assert post.reaction_counts == {"like": 2, "thanks": 1}


@pytest.mark.django_db
def test_one_reaction_per_user_per_type():
    a = User.objects.create_user(username="a", password="x")
    post = _post(a)
    Reaction.objects.create(post=post, user=a, reaction_type=Reaction.LIKE)
    with pytest.raises(IntegrityError):
        Reaction.objects.create(post=post, user=a, reaction_type=Reaction.LIKE)
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_reactions.py -v`
Expected: FAIL — `ImportError: cannot import name 'Reaction'`.

- [ ] **Step 3: Write the model**

`backend/packages/wagtail_forum/wagtail_forum/models/reactions.py`:

```python
from django.conf import settings
from django.db import models
from django.db.models import Count


class Reaction(models.Model):
    LIKE = "like"
    LOVE = "love"
    HELPFUL = "helpful"
    THANKS = "thanks"
    REACTION_CHOICES = [
        (LIKE, "Like"),
        (LOVE, "Love"),
        (HELPFUL, "Helpful"),
        (THANKS, "Thanks"),
    ]

    post = models.ForeignKey(
        "wagtail_forum.Post", on_delete=models.CASCADE, related_name="reactions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_reactions",
    )
    reaction_type = models.CharField(max_length=16, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user", "reaction_type"], name="uniq_forum_reaction"
            )
        ]

    @staticmethod
    def recount(post):
        """Recompute and persist a post's denormalized reaction_counts."""
        counts = {
            row["reaction_type"]: row["n"]
            for row in Reaction.objects.filter(post=post)
            .values("reaction_type")
            .annotate(n=Count("id"))
        }
        post.reaction_counts = counts
        post.save(update_fields=["reaction_counts"])
        return counts

    def __str__(self):
        return f"{self.reaction_type} on post {self.post_id}"
```

Update `models/__init__.py` to add `from .reactions import Reaction` and include `"Reaction"` in `__all__`.

- [ ] **Step 4: Make migrations**

Run: `python manage.py makemigrations wagtail_forum`
Expected: new migration `0005_*` adding `Reaction`.

- [ ] **Step 5: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_reactions.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/models backend/packages/wagtail_forum/wagtail_forum/migrations backend/packages/wagtail_forum/wagtail_forum/tests/test_reactions.py
git commit -m "feat(wagtail_forum): Reaction model + denormalized recount"
```

---

## Task 8: Wagtail admin (SnippetViewSets) for Topic / Post / Profile

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_admin.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_admin.py`:

```python
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_topic_snippet_list_is_reachable_in_admin(client):
    admin = User.objects.create_superuser(username="root", password="x", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/topic/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_post_snippet_list_is_reachable_in_admin(client):
    admin = User.objects.create_superuser(username="root", password="x", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/post/")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_admin.py -v`
Expected: FAIL — 404 (snippets not registered yet).

- [ ] **Step 3: Register the snippet viewsets**

`backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py`:

```python
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from .models import ForumProfile, Post, Topic


class TopicViewSet(SnippetViewSet):
    model = Topic
    icon = "form"
    menu_label = "Topics"
    list_display = ["title", "board", "author", "live", "reply_count"]
    search_fields = ["title"]


class PostViewSet(SnippetViewSet):
    model = Post
    icon = "comment"
    menu_label = "Posts"
    list_display = ["__str__", "topic", "author", "live"]


class ForumProfileViewSet(SnippetViewSet):
    model = ForumProfile
    icon = "user"
    menu_label = "Profiles"
    list_display = ["__str__", "trust_level", "post_count"]


class ForumViewSetGroup(SnippetViewSetGroup):
    items = (TopicViewSet, PostViewSet, ForumProfileViewSet)
    menu_icon = "group"
    menu_label = "Forum"
    menu_name = "forum"


register_snippet(ForumViewSetGroup)
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_admin.py -v`
Expected: PASS (both tests, 200).

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py backend/packages/wagtail_forum/wagtail_forum/tests/test_admin.py
git commit -m "feat(wagtail_forum): admin SnippetViewSets for topics/posts/profiles"
```

---

## Task 9: Search indexing smoke test

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_search.py`

> Topic/Post already declare `search_fields` (Tasks 5–6). This task proves the
> Wagtail search backend actually returns a topic, guarding the "unified search"
> claim. With the project's default database search backend, instances are
> indexed on save.

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_search.py`:

```python
import pytest
from wagtail.models import Page
from wagtail.search.backends import get_search_backend

from wagtail_forum.models import ForumBoard, ForumIndex, Topic


@pytest.mark.django_db
def test_topic_is_searchable_by_title():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    Topic.objects.create(board=board, title="Monstera propagation", slug="monstera")

    backend = get_search_backend()
    backend.refresh_index()
    results = backend.search("Monstera", Topic)

    assert any(t.slug == "monstera" for t in results)
```

- [ ] **Step 2: Run test — verify it fails or errors**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_search.py -v`
Expected: FAIL — empty results (or an error if `search_fields`/backend wiring is wrong). If it errors on `refresh_index()`, the backend doesn't support it; replace that line with a no-op and rely on save-time indexing.

- [ ] **Step 3: Ensure indexing works**

If Step 2 returned empty results, register an explicit index update after creation by adding to the test setup (proving the path) — but first try the default save-time indexing. If the project's `WAGTAILSEARCH_BACKENDS` is unset, Wagtail uses `wagtail.search.backends.database`, which indexes on save and supports `.search()`. No production code change should be needed; the `search_fields` on the models are the implementation. If results are still empty, add `index.SearchField("title", partial_match=True)` is NOT valid in 7.x — instead confirm `AutocompleteField` is present (it is) and use `backend.search("Monstera", Topic)` (full term), which this test already does.

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_search.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/tests/test_search.py
git commit -m "test(wagtail_forum): topics are returned by Wagtail search"
```

---

## Task 10: Reusability guard (no host-app imports)

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_reusability.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_reusability.py`:

```python
import pathlib
import re

import wagtail_forum

HOST_IMPORT = re.compile(r"^\s*(from|import)\s+apps(\.|\s|$)", re.MULTILINE)


def test_package_never_imports_host_apps_namespace():
    root = pathlib.Path(wagtail_forum.__file__).resolve().parent
    offenders = []
    for py in root.rglob("*.py"):
        if "tests" in py.parts or "migrations" in py.parts:
            continue
        if HOST_IMPORT.search(py.read_text(encoding="utf-8")):
            offenders.append(str(py.relative_to(root)))
    assert offenders == [], f"package imports host 'apps.*': {offenders}"
```

- [ ] **Step 2: Run test — verify behavior**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_reusability.py -v`
Expected: PASS immediately (no host imports were ever added). This test is a *guard* — it locks in the boundary so future tasks (esp. Plan 1D host wiring, which must live in the host app, not here) can't silently couple the package to plant code.

- [ ] **Step 3: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/tests/test_reusability.py
git commit -m "test(wagtail_forum): guard against host-app coupling"
```

---

## Task 11: Full suite + migration check

**Files:** none (verification only)

- [ ] **Step 1: Run the whole package suite**

Run (from `backend/`): `pytest packages/wagtail_forum -v`
Expected: all tests PASS.

- [ ] **Step 2: Verify no missing migrations**

Run: `python manage.py makemigrations wagtail_forum --check --dry-run`
Expected: `No changes detected`. If changes are detected, run `makemigrations wagtail_forum`, commit the file, and re-run.

- [ ] **Step 3: Verify the host project still boots**

Run: `python manage.py check`
Expected: `System check identified no issues`.

- [ ] **Step 4: Commit any stragglers**

```bash
git add -A backend/packages/wagtail_forum
git commit -m "chore(wagtail_forum): finalize Plan 1A (scaffold + core models)" || echo "nothing to commit"
```

---

## Plan self-review

- **Spec coverage (1A portion):** package scaffold ✅ (T1); Board=Page ✅ (T2); ForumProfile member+system fields ✅ (T3); forum-safe StreamField ✅ (T4); Topic/Post feature-rich snippets with the verified mixin stack + GenericRelations + search_fields ✅ (T5–T6); denormalized counters present as fields ✅ (T2/T5/T6) with reaction recount logic ✅ (T7); SnippetViewSet admin ✅ (T8); search indexing proven ✅ (T9); reusability/zero-coupling proven ✅ (T10); no-DB-mocks + real Postgres + strict suite ✅ (all tasks use `@pytest.mark.django_db`). **Deferred to later plans (intentionally):** workflow moderation + trust routing + spam (1B), topic/post counter *maintenance on publish* via signals (1B), the DRF API incl. `assertNumQueries` query-count tests on list endpoints (1C), host INSTALLED_APPS/url/moderator-group/FCM wiring + machina removal (1D).
- **Placeholder scan:** no TBD/TODO; every code step has complete code; commands have expected output.
- **Type/name consistency:** `ForumIndex`, `ForumBoard`, `Topic`, `Post`, `ForumProfile`, `TrustLevel`, `Reaction` names and `Reaction.recount(post)`/`ForumProfile.for_user(user)` signatures are consistent across tasks and `models/__init__.py` exports. App label `wagtail_forum` consistent throughout.
- **Known risk flagged in-task:** Task 9 depends on the active Wagtail search backend; the task body gives a fallback if `refresh_index()`/results misbehave.

---

## Roadmap — remaining Spec 1 plans (to be written next)

- **Plan 1B — Moderation workflow + trust + spam:** `SpamCheckTask`/`HeuristicSpamBackend`, trust-based auto-routing (`workflow.py`), trust promotion, post→topic counter maintenance signals (`signals.py` + `apps.ready()` wiring), `moderation_decided`/`reply_added`/`topic_created` signals. Tests: new-user→spam→approval→publish; trusted-user→instant publish; locked/closed topic rejects replies; counters update on publish.
- **Plan 1C — Mobile-first DRF API (`wagtail_forum/api/`, optional module):** serializers (compact list vs detail; StreamField→JSON), viewsets, **CursorPagination** subclass, idempotency-key dedupe on writes, `/sync` delta endpoint + tombstones, capability flags, reactions toggle, profile view/edit, `django-ratelimit`→429 throttling, ETag/Cache-Control. Tests: `assertNumQueries` on every list endpoint, cursor stability, idempotency, delta-sync, capability flags per trust level.
- **Plan 1D — Host integration + retire machina:** add forum API include to `backend/plant_community_backend/urls.py`, create the moderator `Group` + workflow via data migration, host signal handlers → FCM, then remove `MACHINA_APPS`/`HAYSTACK_CONNECTIONS`/`MACHINA_*` from settings, delete `apps.forum_integration`, drop `django-machina`/`django-mptt`/`django-haystack` from `requirements.txt`, and drop the machina tables (greenfield).
