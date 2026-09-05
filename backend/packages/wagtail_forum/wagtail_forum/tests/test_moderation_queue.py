"""Moderation queue report view (todo 345).

The queue is Wagtail's report framework over open/auto-hidden ``Report``
rows, gated on the Report model's own permissions (the same gate as the
Report snippet views every row links into) — so these tests pin the gate
against the host's bootstrapped "Forum Moderators" group, the membership
rule, the ordering, the resolved (never hardcoded) URLs and that they OPEN
for that group, the empty states, the export, and that the listing's query
count does not grow with the number of rows.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from wagtail.models import Page
from wagtail_forum.admin_views import ModerationQueueMenuItem
from wagtail_forum.models import (
    Conversation,
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Message,
    Post,
    Report,
    Topic,
    TrustLevel,
)
from wagtail_forum.wagtail_hooks import register_moderation_queue_menu_item

User = get_user_model()

pytestmark = pytest.mark.django_db


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _post(board, author, title, body_text):
    topic = Topic.objects.create(
        board=board, title=title, slug=title.lower(), author=author
    )
    return Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{body_text}</p>"}],
    )


def _staff(username, *codenames):
    """A staff user who can enter /cms/ plus the given wagtail_forum perms."""
    user = User.objects.create_user(username=username, is_staff=True)
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="wagtailadmin", codename="access_admin"
        )
    )
    for codename in codenames:
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="wagtail_forum", codename=codename
            )
        )
    return user


def _moderator():
    """A member of the host's bootstrapped "Forum Moderators" group — the
    real audience, not a hand-assembled permission set — so the gate and the
    click-through are proven against what a deploy actually grants."""
    user = User.objects.create_user(username="moderator")
    user.groups.add(Group.objects.get(name="Forum Moderators"))
    return user


def _queue_url():
    return reverse("wagtail_forum_reports:moderation_queue")


def _inspect_url(report):
    return reverse(Report.snippet_viewset.get_url_name("inspect"), args=[report.pk])


def test_menu_item_url_and_visibility_follow_the_report_permission():
    item = register_moderation_queue_menu_item()

    assert isinstance(item, ModerationQueueMenuItem)
    # Resolved, not hardcoded (audit 2026-07-17 M1): the same reverse() a host
    # with a different admin mount would get.
    assert item.url == _queue_url()

    factory = RequestFactory()
    shown = factory.get("/")
    shown.user = _moderator()
    view_only = factory.get("/")
    view_only.user = _staff("viewer", "view_report")
    hidden = factory.get("/")
    # change_post alone is NOT enough (review of this slice): the queue's
    # rows link into Report views that would bounce such a user.
    hidden.user = _staff("post_mod_only", "change_post")
    assert item.is_shown(shown) is True
    assert item.is_shown(view_only) is True
    assert item.is_shown(hidden) is False


def test_change_post_alone_does_not_open_the_queue(client):
    client.force_login(_staff("post_mod_only", "change_post"))

    resp = client.get(_queue_url())

    # Wagtail's require_admin_access turns the view's PermissionDenied into
    # its standard "no permission" redirect for a non-XHR request.
    assert resp.status_code == 302
    assert resp["Location"] == reverse("wagtailadmin_home")


def test_queue_lists_open_and_auto_hidden_oldest_first_and_links_to_inspect(client):
    board = _board()
    author = User.objects.create_user(username="author")
    r1, r2, r3, r4 = (
        User.objects.create_user(username=f"reporter{i}") for i in range(4)
    )
    ForumProfile.objects.filter(user=r1).delete()  # r1 has no profile row at all
    profile = ForumProfile.for_user(r2)
    profile.trust_level = TrustLevel.REGULAR
    profile.save(update_fields=["trust_level"])

    oldest = Report.objects.create(
        post=_post(board, author, "Oldest", "first body"),
        reporter=r1,
        reason=Report.SPAM,
    )
    hidden = Report.objects.create(
        post=_post(board, author, "Hidden", "second body"),
        reporter=r2,
        reason=Report.ABUSE,
        status=Report.AUTO_HIDDEN,
    )
    conversation = Conversation.between(author, r3)
    message = Message.objects.create(
        conversation=conversation, sender=author, body="dm text"
    )
    dm = Report.objects.create(message=message, reporter=r3, reason=Report.OTHER)
    Report.objects.create(
        post=_post(board, author, "Done", "resolved body"),
        reporter=r4,
        reason=Report.SPAM,
        status=Report.ACTIONED,
    )
    Report.objects.create(
        message=message, reporter=r4, reason=Report.SPAM, status=Report.DISMISSED
    )

    client.force_login(_moderator())
    resp = client.get(_queue_url())

    assert resp.status_code == 200
    rows = list(resp.context["object_list"])
    assert [r.pk for r in rows] == [oldest.pk, hidden.pk, dm.pk]
    html = resp.content.decode()
    for report in rows:
        assert _inspect_url(report) in html
        # ...and the link OPENS for this moderator (review of this slice):
        # the bootstrapped group must hold the Report permission the
        # snippet inspect view checks, or every row is a dead end.
        assert client.get(_inspect_url(report)).status_code == 200
    assert "Oldest: first body" in html
    assert "author: dm text" in html  # message_summary for the DM report
    assert "No reports are waiting" not in html
    # Reporter trust: a real level renders its label; a reporter with no
    # ForumProfile row still lists (LEFT JOIN), with a blank level.
    by_pk = {r.pk: r for r in rows}
    assert by_pk[oldest.pk].reporter_trust_level is None
    assert by_pk[hidden.pk].reporter_trust_level == TrustLevel.REGULAR
    assert "Regular" in html


def test_open_reports_on_target_counts_only_queue_statuses_for_the_same_target(client):
    board = _board()
    author = User.objects.create_user(username="author")
    post = _post(board, author, "Flagged", "body")
    other_post = _post(board, author, "Other", "body")
    reporters = [User.objects.create_user(username=f"r{i}") for i in range(4)]
    first = Report.objects.create(post=post, reporter=reporters[0], reason=Report.SPAM)
    Report.objects.create(
        post=post, reporter=reporters[1], reason=Report.SPAM, status=Report.AUTO_HIDDEN
    )
    Report.objects.create(
        post=post, reporter=reporters[2], reason=Report.SPAM, status=Report.DISMISSED
    )
    other = Report.objects.create(
        post=other_post, reporter=reporters[3], reason=Report.SPAM
    )

    client.force_login(_moderator())
    resp = client.get(_queue_url())

    counts = {r.pk: r.target_open_reports for r in resp.context["object_list"]}
    assert counts[first.pk] == 2  # OPEN + AUTO_HIDDEN, not the DISMISSED one
    assert counts[other.pk] == 1


def test_queue_filters_by_reason_and_status(client):
    board = _board()
    author = User.objects.create_user(username="author")
    r1, r2 = (User.objects.create_user(username=f"r{i}") for i in range(2))
    spam = Report.objects.create(
        post=_post(board, author, "A", "b"), reporter=r1, reason=Report.SPAM
    )
    abuse = Report.objects.create(
        post=_post(board, author, "B", "b"),
        reporter=r2,
        reason=Report.ABUSE,
        status=Report.AUTO_HIDDEN,
    )

    client.force_login(_moderator())
    by_reason = client.get(_queue_url(), {"reason": Report.ABUSE})
    by_status = client.get(_queue_url(), {"status": Report.OPEN})

    assert [r.pk for r in by_reason.context["object_list"]] == [abuse.pk]
    assert [r.pk for r in by_status.context["object_list"]] == [spam.pk]


def test_reports_filed_in_the_same_instant_keep_a_stable_order_across_sorts(client):
    """The queue is paginated, so ordering needs a deterministic tie-break
    (cross-cutting review): equal created_at rows fall back to pk in BOTH the
    default and the reversed sort, rather than the planner's whim."""
    board = _board()
    author = User.objects.create_user(username="author")
    reporters = [User.objects.create_user(username=f"r{i}") for i in range(3)]
    reports = [
        Report.objects.create(
            post=_post(board, author, f"T{i}", "b"),
            reporter=reporters[i],
            reason=Report.SPAM,
        )
        for i in range(3)
    ]
    Report.objects.filter(pk__in=[r.pk for r in reports]).update(
        created_at=reports[0].created_at
    )

    client.force_login(_moderator())
    default = client.get(_queue_url())
    reversed_ = client.get(_queue_url(), {"ordering": "-created_at"})

    expected = sorted(r.pk for r in reports)
    assert [r.pk for r in default.context["object_list"]] == expected
    assert [r.pk for r in reversed_.context["object_list"]] == expected


def test_target_excerpt_is_just_the_topic_title_when_the_body_has_no_text():
    board = _board()
    author = User.objects.create_user(username="author")
    reporter = User.objects.create_user(username="reporter")
    topic = Topic.objects.create(
        board=board, title="Photo only", slug="photo-only", author=author
    )
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p></p>"}],  # tags only → no text
    )
    report = Report.objects.create(post=post, reporter=reporter, reason=Report.SPAM)

    assert report.target_excerpt == "Photo only"


def test_empty_queue_renders_its_empty_state(client):
    client.force_login(_moderator())

    resp = client.get(_queue_url())

    assert resp.status_code == 200
    assert "No reports are waiting for moderation." in resp.content.decode()


def test_a_filter_that_matches_nothing_does_not_claim_the_queue_is_empty(client):
    board = _board()
    author = User.objects.create_user(username="author")
    reporter = User.objects.create_user(username="reporter")
    Report.objects.create(
        post=_post(board, author, "A", "b"), reporter=reporter, reason=Report.SPAM
    )

    client.force_login(_moderator())
    resp = client.get(_queue_url(), {"reason": Report.ABUSE})

    html = resp.content.decode()
    assert "No reports match your filters." in html
    assert "No reports are waiting for moderation." not in html


def test_queue_exports_csv_with_the_triage_columns(client):
    board = _board()
    author = User.objects.create_user(username="author")
    reporter = User.objects.create_user(username="reporter")
    profile = ForumProfile.for_user(reporter)
    profile.trust_level = TrustLevel.REGULAR
    profile.save(update_fields=["trust_level"])
    Report.objects.create(
        post=_post(board, author, "Exported", "csv body"),
        reporter=reporter,
        reason=Report.SPAM,
        detail="looks like spam",
    )

    client.force_login(_moderator())
    resp = client.get(_queue_url(), {"export": "csv"})

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    body = b"".join(resp.streaming_content).decode()
    assert "Reported content" in body and "Open reports on target" in body
    assert "Exported: csv body" in body and "looks like spam" in body
    # The trust level is decoded like the on-screen column, not the raw
    # annotation digit (review of this slice).
    assert "Regular" in body


def test_queue_query_count_does_not_grow_with_rows(client):
    board = _board()
    author = User.objects.create_user(username="author")
    moderator = _moderator()
    reporters = [User.objects.create_user(username=f"r{i}") for i in range(3)]
    Report.objects.create(
        post=_post(board, author, "One", "b"), reporter=reporters[0], reason=Report.SPAM
    )

    client.force_login(moderator)
    client.get(_queue_url())  # warm per-process caches (perms, hooks, templates)
    with CaptureQueriesContext(connection) as one:
        client.get(_queue_url())

    Report.objects.create(
        post=_post(board, author, "Two", "b"),
        reporter=reporters[1],
        reason=Report.ABUSE,
    )
    conversation = Conversation.between(author, reporters[2])
    message = Message.objects.create(
        conversation=conversation, sender=author, body="dm"
    )
    Report.objects.create(message=message, reporter=reporters[2], reason=Report.OTHER)
    with CaptureQueriesContext(connection) as three:
        client.get(_queue_url())

    assert len(three) == len(one)
