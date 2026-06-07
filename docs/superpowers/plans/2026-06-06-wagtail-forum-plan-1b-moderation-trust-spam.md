# Wagtail Forum — Plan 1B: Moderation Workflow + Trust Routing + Spam + Counters

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make forum moderation a native Wagtail Workflow driven by an automated, pluggable spam check and per-user trust level, and maintain the denormalized counters via publish signals — so new-user posts are screened/queued while trusted-user posts publish instantly.

**Architecture:** A single automated `SpamCheckTask` (a `wagtail.models.Task` subclass) forms the moderation workflow assigned to `Topic`/`Post` via `WorkflowContentType`. `submit_for_moderation(obj, user)` routes by trust: trusted users publish immediately; others run the workflow, where clean content auto-approves→publishes and flagged content is rejected (left as a draft in the moderator queue). A `published` signal handler keeps topic/board/profile counters current.

**Tech Stack:** Django, Wagtail 7.4 workflows (`Task`, `Workflow`, `WorkflowContentType`, `WAGTAIL_FINISH_WORKFLOW_ACTION`), PostgreSQL, pytest.

**Depends on:** Plan 1A (models, package). **Verified:** custom `Task` subclassing, `Workflow.start`, and finish-action auto-publish confirmed against Wagtail stable docs.

**Design note (refines the spec):** the spec's two-stage chain (`SpamCheckTask` → human `GroupApprovalTask`) is implemented in v1 as a single automated `SpamCheckTask`; rejected content waits in the moderator queue for manual publish (native Wagtail), which is the human-approval step. A dedicated `GroupApprovalTask` node is a future refinement.

**Run every command from `backend/`.**

---

## Task 1: Settings resolution (`conf.py`) + spam backend interface + heuristic

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/conf.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/spam/__init__.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/spam/base.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/spam/heuristic.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_spam.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_spam.py`:

```python
from types import SimpleNamespace

from wagtail_forum.conf import get_setting
from wagtail_forum.spam import get_spam_backend
from wagtail_forum.spam.heuristic import HeuristicSpamBackend


class _FakeBody:
    """Mimic a StreamValue: iterating yields blocks with a .value."""

    def __init__(self, text):
        self._blocks = [SimpleNamespace(value=text)]

    def __iter__(self):
        return iter(self._blocks)


def test_default_backend_is_heuristic():
    assert isinstance(get_spam_backend(), HeuristicSpamBackend)


def test_clean_text_passes():
    obj = SimpleNamespace(title="Hello", body=_FakeBody("a normal post"))
    assert get_spam_backend().check(obj).is_clean is True


def test_too_many_links_flagged():
    spammy = "http://a.com http://b.com http://c.com http://d.com http://e.com"
    obj = SimpleNamespace(title="", body=_FakeBody(spammy))
    result = HeuristicSpamBackend().check(obj)
    assert result.is_clean is False
    assert "link" in result.reason.lower()


def test_default_autopublish_level_is_member():
    assert get_setting("TRUST_AUTOPUBLISH_LEVEL") == 2
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_spam.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wagtail_forum.conf'`.

- [ ] **Step 3: Write conf + spam backend**

`backend/packages/wagtail_forum/wagtail_forum/conf.py`:

```python
from django.conf import settings
from django.utils.module_loading import import_string

DEFAULTS = {
    "SPAM_BACKEND": "wagtail_forum.spam.heuristic.HeuristicSpamBackend",
    "TRUST_AUTOPUBLISH_LEVEL": 2,  # TrustLevel.MEMBER
    "SPAM_MAX_LINKS": 3,
    "SPAM_BANNED_WORDS": [],
    "TRUST_THRESHOLDS": {1: 1, 2: 5, 3: 50, 4: 200},  # trust_level -> min post_count
}


def get_setting(name):
    return getattr(settings, f"WAGTAILFORUM_{name}", DEFAULTS[name])
```

`backend/packages/wagtail_forum/wagtail_forum/spam/__init__.py`:

```python
from django.utils.module_loading import import_string

from ..conf import get_setting


def get_spam_backend():
    return import_string(get_setting("SPAM_BACKEND"))()
```

`backend/packages/wagtail_forum/wagtail_forum/spam/base.py`:

```python
from dataclasses import dataclass


@dataclass
class SpamResult:
    is_clean: bool
    reason: str = ""


class SpamBackend:
    """Override check() to return a SpamResult for a Topic or Post."""

    def check(self, obj) -> SpamResult:
        raise NotImplementedError

    def extract_text(self, obj) -> str:
        parts = []
        title = getattr(obj, "title", "") or ""
        if title:
            parts.append(title)
        body = getattr(obj, "body", None)
        if body is not None:
            for block in body:
                parts.append(str(getattr(block, "value", "")))
        return " ".join(parts)
```

`backend/packages/wagtail_forum/wagtail_forum/spam/heuristic.py`:

```python
import re

from ..conf import get_setting
from .base import SpamBackend, SpamResult

URL_RE = re.compile(r"https?://", re.IGNORECASE)


class HeuristicSpamBackend(SpamBackend):
    def check(self, obj) -> SpamResult:
        text = self.extract_text(obj)
        if len(URL_RE.findall(text)) > get_setting("SPAM_MAX_LINKS"):
            return SpamResult(False, "Too many links")
        lowered = text.lower()
        for word in get_setting("SPAM_BANNED_WORDS"):
            if word.lower() in lowered:
                return SpamResult(False, f"Banned term: {word}")
        return SpamResult(True)
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_spam.py -v`
Expected: PASS (all four).

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/conf.py backend/packages/wagtail_forum/wagtail_forum/spam backend/packages/wagtail_forum/wagtail_forum/tests/test_spam.py
git commit -m "feat(wagtail_forum): pluggable spam backend + settings resolution"
```

---

## Task 2: `SpamCheckTask` (automated moderation Task)

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/models/moderation.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/models/__init__.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_moderation_task.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_moderation_task.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page, Workflow, WorkflowContentType, WorkflowTask
from django.contrib.contenttypes.models import ContentType

from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic
from wagtail_forum.models.moderation import SpamCheckTask

User = get_user_model()


def _post(author, body_text):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)
    return Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{body_text}</p>"}],
    )


def _assign_workflow():
    workflow = Workflow.objects.create(name="Forum moderation")
    task = SpamCheckTask.objects.create(name="Spam check")
    WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)
    WorkflowContentType.objects.create(
        content_type=ContentType.objects.get_for_model(Post), workflow=workflow
    )
    return workflow


@pytest.mark.django_db
def test_clean_post_is_published_by_workflow():
    user = User.objects.create_user(username="ada", password="x")
    post = _post(user, "a totally normal first post")
    workflow = _assign_workflow()

    post.save_revision()
    workflow.start(post, user)
    post.refresh_from_db()

    assert post.live is True


@pytest.mark.django_db
def test_spammy_post_is_not_published():
    user = User.objects.create_user(username="eve", password="x")
    spam = "http://a.com http://b.com http://c.com http://d.com http://e.com"
    post = _post(user, spam)
    workflow = _assign_workflow()

    post.save_revision()
    workflow.start(post, user)
    post.refresh_from_db()

    assert post.live is False
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_moderation_task.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wagtail_forum.models.moderation'`.

- [ ] **Step 3: Write the Task**

`backend/packages/wagtail_forum/wagtail_forum/models/moderation.py`:

```python
from wagtail.models import Task

from ..spam import get_spam_backend


class SpamCheckTask(Task):
    """An automated moderation task: approves clean content, rejects flagged.

    Approval lets the (single-task) workflow finish, which publishes the latest
    revision via WAGTAIL_FINISH_WORKFLOW_ACTION. Rejection leaves the object as a
    draft for a human to review and publish from the admin.
    """

    def start(self, workflow_state, user=None):
        task_state = super().start(workflow_state, user=user)
        result = get_spam_backend().check(workflow_state.content_object)
        if result.is_clean:
            task_state.approve(user=user)
        else:
            task_state.reject(user=user, comment=result.reason)
        return task_state
```

Update `backend/packages/wagtail_forum/wagtail_forum/models/__init__.py` to add `from .moderation import SpamCheckTask` and include `"SpamCheckTask"` in `__all__`.

- [ ] **Step 4: Make migrations**

Run: `python manage.py makemigrations wagtail_forum`
Expected: a migration adding `SpamCheckTask` (a `Task` subclass → a small concrete model).

- [ ] **Step 5: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_moderation_task.py -v`
Expected: PASS. (If `task_state.approve()`/`reject()` signatures differ in 7.4, adjust kwargs — verify against `wagtail.models.TaskState.approve` at red-test time.)

- [ ] **Step 6: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/models backend/packages/wagtail_forum/wagtail_forum/migrations backend/packages/wagtail_forum/wagtail_forum/tests/test_moderation_task.py
git commit -m "feat(wagtail_forum): automated SpamCheckTask moderation task"
```

---

## Task 3: Default-workflow helper + trust-based routing (`workflow.py`)

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/workflow.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_workflow_routing.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_workflow_routing.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page

from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic, TrustLevel
from wagtail_forum.workflow import ensure_default_workflow, submit_for_moderation

User = get_user_model()


def _post(author, text="hello world"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)
    return Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{text}</p>"}],
    )


@pytest.mark.django_db
def test_trusted_user_publishes_instantly():
    user = User.objects.create_user(username="reg", password="x")
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.MEMBER
    profile.save()
    ensure_default_workflow()

    post = _post(user)
    post.save()
    status = submit_for_moderation(post, user)

    post.refresh_from_db()
    assert status == "published"
    assert post.live is True


@pytest.mark.django_db
def test_new_user_clean_post_publishes_after_spam_check():
    user = User.objects.create_user(username="new", password="x")
    ForumProfile.for_user(user)  # trust NEW
    ensure_default_workflow()

    post = _post(user, "a friendly normal hello")
    post.save()
    status = submit_for_moderation(post, user)

    post.refresh_from_db()
    assert post.live is True
    assert status == "published"


@pytest.mark.django_db
def test_new_user_spam_stays_pending():
    user = User.objects.create_user(username="spammer", password="x")
    ForumProfile.for_user(user)
    ensure_default_workflow()

    spam = "http://a.com http://b.com http://c.com http://d.com http://e.com"
    post = _post(user, spam)
    post.save()
    status = submit_for_moderation(post, user)

    post.refresh_from_db()
    assert post.live is False
    assert status == "pending"
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_workflow_routing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wagtail_forum.workflow'`.

- [ ] **Step 3: Write the routing module**

`backend/packages/wagtail_forum/wagtail_forum/workflow.py`:

```python
from django.contrib.contenttypes.models import ContentType
from wagtail.models import Workflow, WorkflowContentType, WorkflowTask

from .conf import get_setting
from .models import ForumProfile, Post, Topic
from .models.moderation import SpamCheckTask

DEFAULT_WORKFLOW_NAME = "Forum moderation"


def ensure_default_workflow():
    """Idempotently create the moderation workflow and assign it to Topic/Post."""
    workflow, _ = Workflow.objects.get_or_create(name=DEFAULT_WORKFLOW_NAME)
    task, _ = SpamCheckTask.objects.get_or_create(name="Spam check")
    WorkflowTask.objects.get_or_create(
        workflow=workflow, task=task, defaults={"sort_order": 0}
    )
    for model in (Topic, Post):
        WorkflowContentType.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(model),
            defaults={"workflow": workflow},
        )
    return workflow


def submit_for_moderation(obj, user):
    """Route by trust. Returns 'published' or 'pending'.

    Trusted users (trust >= TRUST_AUTOPUBLISH_LEVEL) publish immediately.
    Others run the workflow: clean content auto-publishes; flagged content is
    rejected and stays a draft (status 'pending') for manual moderation.
    """
    profile = ForumProfile.for_user(user)
    revision = obj.save_revision(user=user)
    if profile.trust_level >= get_setting("TRUST_AUTOPUBLISH_LEVEL"):
        revision.publish(user=user)
        return "published"

    workflow = obj.get_workflow()
    if workflow is None:
        revision.publish(user=user)
        return "published"

    workflow.start(obj, user)
    obj.refresh_from_db()
    return "published" if obj.live else "pending"
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_workflow_routing.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/workflow.py backend/packages/wagtail_forum/wagtail_forum/tests/test_workflow_routing.py
git commit -m "feat(wagtail_forum): default workflow helper + trust-based routing"
```

---

## Task 4: Counter maintenance + custom signals (`signals.py`)

**Files:**

- Create: `backend/packages/wagtail_forum/wagtail_forum/signals.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/apps.py` (wire `ready()`)
- Create: `backend/packages/wagtail_forum/wagtail_forum/tests/test_counters.py`

- [ ] **Step 1: Write the failing test**

`backend/packages/wagtail_forum/wagtail_forum/tests/test_counters.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page

from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic

User = get_user_model()


def _topic(author):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    return Topic.objects.create(board=board, title="T", slug="t", author=author)


def _publish(topic, author, opening=False):
    post = Post.objects.create(topic=topic, author=author, is_opening_post=opening)
    post.save_revision().publish()
    return post


@pytest.mark.django_db
def test_reply_updates_topic_and_board_and_profile_counters():
    user = User.objects.create_user(username="ada", password="x")
    topic = _topic(user)
    _publish(topic, user, opening=True)
    _publish(topic, user)  # one reply

    topic.refresh_from_db()
    topic.board.refresh_from_db()
    profile = ForumProfile.for_user(user)

    assert topic.reply_count == 1
    assert topic.last_post_author_id == user.id
    assert topic.last_post_at is not None
    assert topic.board.post_count == 2
    assert topic.board.topic_count == 1
    assert profile.post_count == 2
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_counters.py -v`
Expected: FAIL — counters stay 0 (no signal wired).

- [ ] **Step 3: Write the signals module + wire `ready()`**

`backend/packages/wagtail_forum/wagtail_forum/signals.py`:

```python
from django.dispatch import Signal, receiver
from django.utils import timezone
from wagtail.signals import published

# Public signals for hosts (e.g. push notifications). kwargs: post, topic.
topic_created = Signal()
reply_added = Signal()
moderation_decided = Signal()


@receiver(published)
def update_counters_on_publish(sender, instance, **kwargs):
    from .models import ForumProfile, Post, Topic

    if not isinstance(instance, Post):
        return
    post = instance
    topic = post.topic

    if post.is_opening_post:
        topic_created.send(sender=Post, post=post, topic=topic)
    else:
        reply_added.send(sender=Post, post=post, topic=topic)

    topic.reply_count = topic.posts.filter(is_opening_post=False, live=True).count()
    topic.last_post_at = timezone.now()
    topic.last_post_author = post.author
    topic.save(
        update_fields=["reply_count", "last_post_at", "last_post_author", "updated_at"]
    )

    board = topic.board
    board.post_count = Post.objects.filter(topic__board=board, live=True).count()
    board.topic_count = Topic.objects.filter(board=board, live=True).count()
    board.save(update_fields=["post_count", "topic_count"])

    if post.author_id:
        profile = ForumProfile.for_user(post.author)
        profile.post_count = Post.objects.filter(
            author=post.author, live=True
        ).count()
        _maybe_promote(profile)
        profile.save(update_fields=["post_count", "trust_level"])


def _maybe_promote(profile):
    from .conf import get_setting

    thresholds = get_setting("TRUST_THRESHOLDS")
    new_level = profile.trust_level
    for level, min_posts in sorted(thresholds.items()):
        if profile.post_count >= min_posts:
            new_level = max(new_level, level)
    profile.trust_level = new_level
```

Update `backend/packages/wagtail_forum/wagtail_forum/apps.py` — add a `ready()`:

```python
from django.apps import AppConfig


class WagtailForumAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "wagtail_forum"
    label = "wagtail_forum"
    verbose_name = "Wagtail Forum"

    def ready(self):
        from . import signals  # noqa: F401  (registers receivers)
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `pytest packages/wagtail_forum/wagtail_forum/tests/test_counters.py -v`
Expected: PASS.

- [ ] **Step 5: Run the whole package suite**

Run: `pytest packages/wagtail_forum -v`
Expected: all PASS. Then `python manage.py makemigrations wagtail_forum --check --dry-run` → `No changes detected`.

- [ ] **Step 6: Commit**

```bash
git add backend/packages/wagtail_forum/wagtail_forum/signals.py backend/packages/wagtail_forum/wagtail_forum/apps.py backend/packages/wagtail_forum/wagtail_forum/tests/test_counters.py
git commit -m "feat(wagtail_forum): publish-signal counters + trust promotion + host signals"
```

---

## Plan self-review

- **Spec coverage (1B):** moderation = Wagtail Workflow ✅ (T2–T3); automated spam Task ✅ (T2); pluggable/configurable spam backend ✅ (T1); trust-based auto-routing ✅ (T3); trust promotion ✅ (T4); denormalized counter maintenance ✅ (T4); host-facing signals `topic_created`/`reply_added`/`moderation_decided` ✅ (T4). Deferred: locking-rejects-reply enforcement and `is_closed` guard live in the API layer (Plan 1C); per-board moderator scoping is out of v1 (global group, Plan 1D).
- **Placeholder scan:** none; every code step is complete.
- **Type/name consistency:** `SpamCheckTask`, `ensure_default_workflow()`, `submit_for_moderation(obj, user)→"published"|"pending"`, `get_spam_backend()`, `SpamResult(is_clean, reason)`, `get_setting(NAME)` consistent across tasks and with Plan 1A model names.
- **Risk flagged in-task:** `TaskState.approve/reject` kwargs (T2) and the `WorkflowContentType` field name (T2/T3) are verified at red-test time by TDD.

---

## Note for Plan 1C

`submit_for_moderation` is the single entry point the API create-endpoints call. The API must reject replies when `topic.is_closed` or `topic.locked` (LockableMixin) before calling it.
