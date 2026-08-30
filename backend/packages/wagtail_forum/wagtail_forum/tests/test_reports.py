import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import override_settings
from wagtail.models import Page
from wagtail_forum.models import (
    Conversation,
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Message,
    Post,
    Report,
    Topic,
)

User = get_user_model()


def _post(author):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)
    return Post.objects.create(topic=topic, author=author, is_opening_post=True)


def _message(sender, recipient):
    conversation = Conversation.between(sender, recipient)
    return Message.objects.create(conversation=conversation, sender=sender, body="hi")


@pytest.mark.django_db
def test_file_creates_a_report():
    author = User.objects.create_user(username="author")
    reporter = User.objects.create_user(username="reporter")
    post = _post(author)

    report = Report.file(post, reporter, Report.SPAM, detail="looks like spam")

    assert report is not None
    assert report.post_id == post.pk
    assert report.reporter_id == reporter.pk
    assert report.status == Report.OPEN


@pytest.mark.django_db
def test_duplicate_report_from_same_user_is_idempotent_no_op():
    author = User.objects.create_user(username="author")
    reporter = User.objects.create_user(username="reporter")
    post = _post(author)

    first = Report.file(post, reporter, Report.SPAM)
    second = Report.file(
        post, reporter, Report.ABUSE
    )  # different reason, same user+post

    assert first is not None
    assert second is None
    assert Report.objects.filter(post=post, reporter=reporter).count() == 1


@pytest.mark.django_db
def test_file_increments_authors_flags_received():
    author = User.objects.create_user(username="author")
    reporter = User.objects.create_user(username="reporter")
    post = _post(author)
    profile = ForumProfile.for_user(author)
    assert profile.flags_received == 0

    Report.file(post, reporter, Report.SPAM)

    profile.refresh_from_db()
    assert profile.flags_received == 1


@pytest.mark.django_db
def test_file_skips_flags_received_when_author_is_none():
    author = User.objects.create_user(username="author")
    reporter = User.objects.create_user(username="reporter")
    post = _post(author)
    post.author = None
    post.save(update_fields=["author"])

    # Must not raise (there is no profile to credit).
    report = Report.file(post, reporter, Report.SPAM)

    assert report is not None


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_REPORT_AUTO_HIDE_THRESHOLD=2)
def test_reaching_threshold_auto_hides_the_post():
    author = User.objects.create_user(username="author")
    reporters = [User.objects.create_user(username=f"r{i}") for i in range(2)]
    post = _post(author)
    assert post.live is True

    for reporter in reporters:
        Report.file(post, reporter, Report.SPAM)

    post.refresh_from_db()
    assert post.live is False
    statuses = set(Report.objects.filter(post=post).values_list("status", flat=True))
    assert statuses == {Report.AUTO_HIDDEN}


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_REPORT_AUTO_HIDE_THRESHOLD=3)
def test_below_threshold_leaves_the_post_live_and_reports_open():
    author = User.objects.create_user(username="author")
    reporters = [User.objects.create_user(username=f"r{i}") for i in range(2)]
    post = _post(author)

    for reporter in reporters:
        Report.file(post, reporter, Report.SPAM)

    post.refresh_from_db()
    assert post.live is True
    statuses = set(Report.objects.filter(post=post).values_list("status", flat=True))
    assert statuses == {Report.OPEN}


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_REPORT_AUTO_HIDE_THRESHOLD=1)
def test_reporting_an_already_unpublished_post_does_not_retrigger_unhide_logic():
    author = User.objects.create_user(username="author")
    reporter = User.objects.create_user(username="reporter")
    post = _post(author)
    post.live = False
    post.save(update_fields=["live"])

    # Must not raise even though the post is already non-live.
    report = Report.file(post, reporter, Report.SPAM)

    assert report.status == Report.OPEN  # never evaluated for auto-hide


@pytest.mark.django_db
def test_a_report_must_target_exactly_one_of_post_or_message():
    reporter = User.objects.create_user(username="xor-reporter")
    with pytest.raises(IntegrityError):
        Report.objects.create(reporter=reporter, reason=Report.SPAM)


@pytest.mark.django_db
def test_file_for_message_creates_a_report():
    sender = User.objects.create_user(username="dm-sender")
    reporter = User.objects.create_user(username="dm-reporter")
    message = _message(sender, reporter)

    report = Report.file_for_message(message, reporter, Report.SPAM, detail="dm spam")

    assert report is not None
    assert report.message_id == message.pk
    assert report.post_id is None
    assert report.reporter_id == reporter.pk
    assert report.status == Report.OPEN


@pytest.mark.django_db
def test_duplicate_message_report_from_same_user_is_idempotent_no_op():
    sender = User.objects.create_user(username="dm-sender2")
    reporter = User.objects.create_user(username="dm-reporter2")
    message = _message(sender, reporter)

    first = Report.file_for_message(message, reporter, Report.SPAM)
    second = Report.file_for_message(message, reporter, Report.ABUSE)

    assert first is not None
    assert second is None
    assert Report.objects.filter(message=message, reporter=reporter).count() == 1


@pytest.mark.django_db
def test_file_for_message_increments_senders_flags_received():
    """A DM-only sender has NO ForumProfile row yet — Message creation fires
    no profile-seeding signal, unlike the post/topic publish signal. Do NOT
    pre-create the profile here (that would hide the exact bug this test
    exists to catch: a bare .filter().update() silently matching zero rows)."""
    sender = User.objects.create_user(username="dm-sender3")
    reporter = User.objects.create_user(username="dm-reporter3")
    message = _message(sender, reporter)
    assert not ForumProfile.objects.filter(user=sender).exists()

    Report.file_for_message(message, reporter, Report.SPAM)

    profile = ForumProfile.objects.get(user=sender)
    assert profile.flags_received == 1


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_REPORT_AUTO_HIDE_THRESHOLD=2)
def test_reaching_threshold_marks_message_reports_auto_hidden():
    """Unlike the Post path, there is no content-redaction side effect to
    verify — only the bookkeeping status flip (todo 319's Work Log)."""
    sender = User.objects.create_user(username="dm-sender4")
    reporters = [User.objects.create_user(username=f"dm-r{i}") for i in range(2)]
    message = _message(sender, reporters[0])

    for reporter in reporters:
        Report.file_for_message(message, reporter, Report.SPAM)

    statuses = set(
        Report.objects.filter(message=message).values_list("status", flat=True)
    )
    assert statuses == {Report.AUTO_HIDDEN}


@pytest.mark.django_db
def test_a_post_report_and_a_message_report_by_the_same_user_can_coexist():
    """The two conditioned unique constraints are independent — a NULL post
    on one row and a NULL message on the other must not collide."""
    author = User.objects.create_user(username="both-author")
    reporter = User.objects.create_user(username="both-reporter")
    post = _post(author)
    message = _message(author, reporter)

    Report.file(post, reporter, Report.SPAM)
    Report.file_for_message(message, reporter, Report.SPAM)

    assert Report.objects.filter(reporter=reporter).count() == 2
