"""Erasing a deleted account's Django, forum and email data (Plan B, task 3).

``erase_django_data`` runs the ``forum``, ``email`` and ``django`` steps of a
``DeletedAccount`` in order, each recorded in ``steps_done`` once it commits,
so a crashed run resumes where it stopped.
"""

import io
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from apps.users import deletion
from apps.users.constants import (
    DELETED_ACCOUNT_REASON_SELF,
    DELETED_TOPIC_TITLE,
    FORUM_HELD_POST_DAYS,
)
from apps.users.deletion import email_hash, erase_django_data, erase_post
from apps.users.models import DeletedAccount
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db.models import CharField, F, TextField
from django.db.models.functions import Cast
from django.test import override_settings
from django.utils import timezone
from PIL import Image as PILImage
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail_forum.models import (
    Conversation,
    Message,
    Notification,
    Post,
    Reaction,
    Report,
    Topic,
)
from wagtail_forum.tests.factories import make_forum

User = get_user_model()

pytestmark = pytest.mark.django_db

# Distinctive, so an ``icontains`` search cannot false-positive on a short word.
USERNAME = "erasetarget7f3a"
EMAIL = "Gone.Q9x2@Example.test"


# --- the "no identifying rows" walk ----------------------------------------


def _rows_naming(needle):
    """Every ``(model label, field, pk)`` whose text holds ``needle``.

    Walks every installed model's CharField and TextField (EmailField,
    SlugField and URLField are CharFields) and every JSON column
    (JSONField, StreamField) cast to text. Base managers, so no custom
    manager hides a row.
    """
    hits = []
    for model in apps.get_models():
        opts = model._meta
        if opts.proxy or not opts.managed:
            continue
        for field in opts.concrete_fields:
            if isinstance(field, (CharField, TextField)):
                rows = model._base_manager.filter(
                    **{f"{field.attname}__icontains": needle}
                )
            elif field.get_internal_type() == "JSONField":
                rows = model._base_manager.annotate(
                    _as_text=Cast(F(field.attname), TextField())
                ).filter(_as_text__icontains=needle)
            else:
                continue
            for pk in rows.values_list("pk", flat=True):
                hits.append((opts.label, field.name, pk))
    return hits


def _is_post_search_entry(pk, post_pks):
    """Whether IndexEntry ``pk`` is the search-index copy of one of
    ``post_pks``: the same text as that post's body, not a separate copy."""
    from wagtail.search.models import IndexEntry

    entry = IndexEntry.objects.get(pk=pk)
    return entry.content_type.model_class() is Post and int(entry.object_id) in post_pks


def _unexpected(hits, *, kept_post_pks=()):
    """Hits outside the brief's allowed exceptions: the pending
    ``DeletedAccount.email``, ``EmailSuppression`` (a hash only, so it can
    never hold the needle) and OTHER users' post bodies (quotes), including
    the search index's copy of those bodies."""
    unexpected = []
    for label, field, pk in hits:
        if (label, field) == ("users.DeletedAccount", "email"):
            continue
        if (label, field) == ("wagtail_forum.Post", "body") and pk in kept_post_pks:
            continue
        if label == "wagtailsearch.IndexEntry" and _is_post_search_entry(
            pk, kept_post_pks
        ):
            continue
        unexpected.append((label, field, pk))
    return unexpected


# --- fixtures ---------------------------------------------------------------


@pytest.fixture
def roots(tmp_path):
    media = tmp_path / "media"
    private = tmp_path / "private"
    media.mkdir()
    private.mkdir()
    with override_settings(MEDIA_ROOT=str(media), SCAN_PHOTO_LOCAL_ROOT=str(private)):
        yield media, private


def _png_bytes():
    buf = io.BytesIO()
    PILImage.new("RGB", (64, 64), (20, 140, 40)).save(buf, "PNG")
    return buf.getvalue()


def _jpeg_bytes():
    buf = io.BytesIO()
    PILImage.new("RGB", (64, 64), (40, 120, 40)).save(buf, "JPEG")
    return buf.getvalue()


def _image(uploader, title="leaf"):
    return get_image_model().objects.create(
        title=title, file=get_test_image_file(), uploaded_by_user=uploader
    )


def _record(user):
    return DeletedAccount.objects.create(
        user_id=user.pk,
        email=user.email,
        email_hash=email_hash(user.email),
        reason=DELETED_ACCOUNT_REASON_SELF,
    )


@pytest.fixture
def target(db):
    return User.objects.create_user(username=USERNAME, email=EMAIL, password="x" * 16)


@pytest.fixture
def other(db):
    return User.objects.create_user(
        username="bystander", email="bystander@example.org", password="x" * 16
    )


@pytest.fixture
def board(db):
    return make_forum(name="General", slug="general")


def _topic(board, author, title="Fern trouble", slug="fern-trouble"):
    return Topic.objects.create(board=board, title=title, slug=slug, author=author)


def _post(topic, author, body, *, opening=False):
    return Post.objects.create(
        topic=topic, author=author, is_opening_post=opening, live=True, body=body
    )


def _blog_post(author):
    from apps.blog.models import BlogIndexPage, BlogPostPage
    from wagtail.models import Locale, Page, Site

    locale, _ = Locale.objects.get_or_create(language_code="en")
    site = Site.objects.filter(is_default_site=True).first()
    if site is not None:
        root = site.root_page
    else:
        root = Page.objects.filter(depth=1).first() or Page.add_root(
            title="Root", locale=locale
        )
        Site.objects.create(hostname="localhost", root_page=root, is_default_site=True)
    index = BlogIndexPage(title="Blog", slug="erasure-blog")
    root.add_child(instance=index)
    page = BlogPostPage(
        title="Repotting",
        slug="repotting",
        author=author,
        publish_date=timezone.now().date(),
        introduction="intro",
    )
    index.add_child(instance=page)
    return page


# --- tests ------------------------------------------------------------------


def test_erasure_leaves_no_identifying_rows(
    roots, target, other, board, django_capture_on_commit_callbacks
):
    from apps.blog.models import BlogNewsletter, BlogPostView
    from apps.core.models import EmailNotification, PushDevice
    from apps.garden_calendar.models import GardenBed, Plant
    from apps.plant_identification.scan_models import ScanJob, ScanJobImage
    from apps.users.models import (
        OnboardingAnalytics,
        OnboardingProgress,
        PushSubscription,
        UserPlantCollection,
    )
    from auditlog import get_logentry_model
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
    from rest_framework_simplejwt.tokens import RefreshToken
    from wagtail_forum.models import ForumProfile

    media, private = roots
    LogEntry = get_logentry_model()

    # Avatar.
    target.avatar.save("a.png", ContentFile(_png_bytes()), save=True)
    avatar_path = media / target.avatar.name

    # Garden bed and plant (both audited; the bed's object_repr names the user).
    bed = GardenBed.objects.create(owner=target, name="Back bed", bed_type="raised")
    Plant.objects.create(
        owner=target,
        garden_bed=bed,
        common_name="Tomato",
        health_status="healthy",
        growth_stage="seedling",
        planted_date=date(2026, 5, 1),
    )

    # An audited collection outside the garden app: its LogEntry
    # object_repr is "<username>'s Favourites".
    UserPlantCollection.objects.create(user=target, name="Favourites")

    # Scan job with a photo.
    job = ScanJob.objects.create(
        user=target, mode="diagnose", local_date=date(2026, 11, 2)
    )
    photo = ScanJobImage.objects.create(
        job=job, role="leaf", image=ContentFile(_jpeg_bytes(), name="x.jpg")
    )
    photo_path = private / photo.image.name

    # Forum: a topic and a post with an image, a reply by someone else that
    # quotes the user by name, a DM, a report the user filed, a reaction and
    # a notification the user caused.
    topic = _topic(board, target)
    image = _image(target)
    image_path = media / image.file.name
    own_post = _post(
        topic, target, [("image", {"image": image, "alt_text": "a fern"})], opening=True
    )
    reply = _post(topic, other, [("quote", f"{USERNAME} said ferns like shade")])
    other_topic = _topic(board, other, title="Cacti", slug="cacti")
    other_post = _post(other_topic, other, [("quote", "spines")], opening=True)
    Reaction.objects.create(post=other_post, user=target, reaction_type=Reaction.LIKE)
    Reaction.recount(other_post)
    assert other_post.reaction_counts == {"like": 1}
    Report.objects.create(post=other_post, reporter=target, reason=Report.SPAM)
    conversation = Conversation.between(target, other)
    Message.objects.create(conversation=conversation, sender=target, body="hi there")
    Notification.objects.create(
        recipient=other, actor=target, verb="reply", topic=topic, post=own_post
    )
    profile, _ = ForumProfile.objects.get_or_create(user=target)
    profile.fcm_token = "fcm-token-abc"
    profile.save()

    # Email and logs.
    BlogNewsletter.objects.create(email=EMAIL.upper())
    EmailNotification.objects.create(
        email_type="welcome", recipient_email=EMAIL, user=target, subject="Welcome"
    )
    EmailNotification.objects.create(
        email_type="digest", recipient_email=EMAIL.lower(), user=None, subject="Digest"
    )
    BlogPostView.objects.create(
        post=_blog_post(other), user=target, ip_address="203.0.113.7", user_agent="UA"
    )
    RefreshToken.for_user(target)

    # Devices and analytics.
    PushDevice.objects.create(user=target, token="device-token-1", platform="ios")
    PushSubscription.objects.create(
        user=target,
        endpoint="https://fcm.googleapis.com/fcm/send/erasure",
        p256dh_key="BPk-key",
        auth_key="auth-value",  # pragma: allowlist secret
    )
    progress = OnboardingProgress.objects.create(user=target)
    OnboardingAnalytics.objects.create(
        user=target,
        onboarding_progress=progress,
        action_type="step_started",
        step_name="welcome",
        ip_address="198.51.100.4",
    )

    # An audit row the user is the ACTOR of, on someone else's object.
    LogEntry.objects.create(
        content_type=ContentType.objects.get_for_model(User),
        object_pk=str(other.pk),
        object_id=other.pk,
        object_repr="bystander",
        action=LogEntry.Action.UPDATE,
        changes={"bio": ["", "edited"]},
        actor=target,
        actor_email=EMAIL,
    )
    # Sanity: the fixture really does name the user in the audit log.
    assert LogEntry.objects.filter(object_pk=str(target.pk)).exists()
    assert _rows_naming(USERNAME) and _rows_naming(EMAIL)

    record = _record(target)
    with django_capture_on_commit_callbacks(execute=True):
        erase_django_data(record)

    assert not User.objects.filter(pk=record.user_id).exists()
    assert not avatar_path.exists()
    assert not photo_path.exists()
    assert not image_path.exists()
    assert not get_image_model().objects.filter(pk=image.pk).exists()
    other_post.refresh_from_db()
    assert other_post.reaction_counts == {}
    assert Message.objects.filter(conversation=conversation).count() == 1

    # Rows that carry no username or email text, so the walk below cannot
    # see them: they must be gone by count.
    uid = record.user_id
    assert PushDevice.objects.filter(user_id=uid).count() == 0
    assert PushDevice.objects.filter(token="device-token-1").count() == 0
    assert PushSubscription.objects.filter(user_id=uid).count() == 0
    assert ScanJob.objects.filter(user_id=uid).count() == 0
    assert ScanJobImage.objects.filter(job_id=job.pk).count() == 0
    assert GardenBed.objects.filter(pk=bed.pk).count() == 0
    assert Plant.objects.filter(owner_id=uid).count() == 0
    assert OutstandingToken.objects.filter(user_id=uid).count() == 0
    assert BlogPostView.objects.filter(user_id=uid).count() == 0
    assert BlogPostView.objects.filter(ip_address="203.0.113.7").count() == 0
    assert OnboardingAnalytics.objects.filter(ip_address="198.51.100.4").count() == 0
    assert ForumProfile.objects.filter(user_id=uid).count() == 0

    kept = {reply.pk}
    assert _unexpected(_rows_naming(USERNAME), kept_post_pks=kept) == []
    assert _unexpected(_rows_naming(EMAIL), kept_post_pks=kept) == []
    assert _unexpected(_rows_naming(EMAIL.lower()), kept_post_pks=kept) == []


def test_post_with_open_report_is_held(
    roots, target, other, board, django_capture_on_commit_callbacks
):
    topic = _topic(board, other)
    _post(topic, other, [("quote", "opening")], opening=True)
    image = _image(target)
    image_path = Path(image.file.path)
    body = [("image", {"image": image, "alt_text": "x"}), ("quote", "rude words")]
    held = _post(topic, target, body)
    Report.objects.create(post=held, reporter=other, reason=Report.ABUSE)
    before = timezone.now()

    record = _record(target)
    with django_capture_on_commit_callbacks(execute=True):
        erase_django_data(record)

    held.refresh_from_db()
    assert held.author_id is None
    assert held.erase_after is not None
    assert (
        before + timedelta(days=FORUM_HELD_POST_DAYS)
        <= held.erase_after
        <= timezone.now() + timedelta(days=FORUM_HELD_POST_DAYS)
    )
    assert [block.block_type for block in held.body] == ["image", "quote"]
    assert get_image_model().objects.filter(pk=image.pk).exists()
    assert image_path.exists()
    assert not User.objects.filter(pk=record.user_id).exists()


def test_an_auto_hidden_report_also_holds_the_post(target, other, board):
    topic = _topic(board, other)
    held = _post(topic, target, [("quote", "rude words")])
    Report.objects.create(
        post=held, reporter=other, reason=Report.ABUSE, status=Report.AUTO_HIDDEN
    )

    erase_django_data(_record(target))

    held.refresh_from_db()
    assert held.erase_after is not None
    assert len(held.body) == 1


def test_a_resolved_report_does_not_hold_the_post(target, other, board):
    topic = _topic(board, other)
    post = _post(topic, target, [("quote", "fine words")])
    Report.objects.create(
        post=post, reporter=other, reason=Report.SPAM, status=Report.DISMISSED
    )

    erase_django_data(_record(target))

    post.refresh_from_db()
    assert post.erase_after is None
    assert len(post.body) == 0


def test_erase_post_deletes_its_images(
    roots, target, other, board, django_capture_on_commit_callbacks
):
    topic = _topic(board, other)
    own = _image(target, "own")
    shared = _image(target, "shared")
    own_path = Path(own.file.path)
    released = _post(
        topic,
        None,
        [
            ("image", {"image": own, "alt_text": ""}),
            ("image", {"image": shared, "alt_text": ""}),
        ],
    )
    _post(topic, other, [("image", {"image": shared, "alt_text": ""})])

    with django_capture_on_commit_callbacks(execute=True):
        erase_post(released)

    assert not get_image_model().objects.filter(pk=own.pk).exists()
    assert not own_path.exists()
    assert get_image_model().objects.filter(pk=shared.pk).exists()


def test_erase_post_removes_body_and_revisions(target, other, board):
    topic = _topic(board, other)
    post = _post(topic, target, [("quote", "first")])
    post.save_revision(user=target)
    post.body = [("quote", "second")]
    post.save_revision(user=target)
    assert post.revisions.count() == 2
    post.erase_after = timezone.now()
    post.save()

    erase_post(post)

    post.refresh_from_db()
    assert len(post.body) == 0
    assert post.author_id is None
    assert post.erase_after is None
    assert post.revisions.count() == 0
    assert post.latest_revision_id is None


def test_topic_title_becomes_deleted_and_replies_remain(target, other, board):
    topic = _topic(board, target)
    topic.save_revision(user=target)
    _post(topic, target, [("quote", "my question")], opening=True)
    reply = _post(topic, other, [("quote", "an answer")])

    erase_django_data(_record(target))

    topic.refresh_from_db()
    assert topic.title == DELETED_TOPIC_TITLE
    assert topic.author_id is None
    assert topic.revisions.count() == 0
    reply.refresh_from_db()
    assert [block.value for block in reply.body] == ["an answer"]
    assert reply.author_id == other.pk


def test_steps_are_idempotent(target, board):
    topic = _topic(board, target)
    _post(topic, target, [("quote", "hello")], opening=True)
    record = _record(target)

    erase_django_data(record)
    erase_django_data(record)

    record.refresh_from_db()
    assert record.steps_done == ["forum", "email", "django"]


def test_a_gone_user_marks_the_remaining_steps_done(target):
    record = _record(target)
    record.steps_done = ["forum"]
    record.save()
    target.delete()

    erase_django_data(record)

    record.refresh_from_db()
    assert record.steps_done == ["forum", "email", "django"]


def test_erasure_writes_no_new_audit_rows(target, django_capture_on_commit_callbacks):
    from apps.garden_calendar.models import GardenBed
    from auditlog import get_logentry_model

    GardenBed.objects.create(owner=target, name="Bed", bed_type="raised")
    record = _record(target)
    with django_capture_on_commit_callbacks(execute=True):
        erase_django_data(record)

    assert (
        get_logentry_model().objects.filter(object_pk=str(record.user_id)).count() == 0
    )
    assert (
        not get_logentry_model()
        .objects.filter(action=get_logentry_model().Action.DELETE)
        .exists()
    )


def test_an_upload_used_elsewhere_survives_without_its_uploader(
    roots, target, other, board, django_capture_on_commit_callbacks
):
    topic = _topic(board, other)
    shared = _image(target, "shared upload")
    shared_path = Path(shared.file.path)
    _post(topic, target, [("image", {"image": shared, "alt_text": ""})])
    _post(topic, other, [("image", {"image": shared, "alt_text": ""})])
    # Uploaded but referenced by nothing at all: still goes.
    orphan = _image(target, "orphan upload")

    with django_capture_on_commit_callbacks(execute=True):
        erase_django_data(_record(target))

    shared.refresh_from_db()
    assert shared.uploaded_by_user_id is None
    assert shared_path.exists()
    assert not get_image_model().objects.filter(pk=orphan.pk).exists()


def test_an_upload_a_blog_page_uses_survives(roots, target, other, board):
    from wagtail.models import ReferenceIndex

    image = _image(target, "blog hero")
    page = _blog_post(other)
    page.featured_image = image
    page.save()
    assert ReferenceIndex.get_references_to(image).exists()

    erase_django_data(_record(target))

    image.refresh_from_db()
    assert image.uploaded_by_user_id is None


def test_a_failed_step_resumes_without_redoing_earlier_steps(target, other, board):
    topic = _topic(board, other)
    held = _post(topic, target, [("quote", "rude words")])
    Report.objects.create(post=held, reporter=other, reason=Report.ABUSE)
    record = _record(target)
    real_email = deletion._erase_email
    calls = {"email": 0}

    def flaky_email(user):
        calls["email"] += 1
        if calls["email"] == 1:
            raise RuntimeError("mail store down")
        real_email(user)

    with (
        patch.object(deletion, "_erase_email", side_effect=flaky_email),
        patch.object(deletion, "_erase_forum", wraps=deletion._erase_forum) as forum,
    ):
        with pytest.raises(RuntimeError):
            erase_django_data(record)
        record.refresh_from_db()
        assert record.steps_done == ["forum"]
        assert User.objects.filter(pk=target.pk).exists()
        held.refresh_from_db()
        first_hold = held.erase_after
        assert first_hold is not None

        erase_django_data(record)

    record.refresh_from_db()
    assert record.steps_done == ["forum", "email", "django"]
    assert forum.call_count == 1
    assert calls["email"] == 2
    held.refresh_from_db()
    assert held.erase_after == first_hold
    assert not User.objects.filter(pk=target.pk).exists()


def test_a_stale_record_copy_does_not_redo_or_overwrite_steps(target, board):
    topic = _topic(board, target)
    _post(topic, target, [("quote", "hello")], opening=True)
    first = _record(target)
    stale = DeletedAccount.objects.get(pk=first.pk)  # read before any step ran

    erase_django_data(first)
    with patch.object(deletion, "_erase_forum") as forum:
        erase_django_data(stale)

    forum.assert_not_called()
    first.refresh_from_db()
    assert first.steps_done == ["forum", "email", "django"]
    assert stale.steps_done == ["forum", "email", "django"]
