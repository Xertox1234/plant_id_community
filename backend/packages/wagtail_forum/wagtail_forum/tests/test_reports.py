import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
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
