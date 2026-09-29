"""Pending forum content: one admin page, one Approve per thread (todo 423).

The owner's first moderation pass took four steps across three admin areas:
the pending count linked to a list, "Forum moderation queue" listed only
user-filed reports, and approving the topic left its opening post behind.
These pin the replacement: a single page that lists every pending topic and
post, an Approve that publishes a new topic together with its opening post,
the dashboard count that links to that page and counts exactly its rows, and
a Reports-menu name that can't be mistaken for it.

Content is driven through the real ``submit_for_moderation`` (spam the
heuristic holds), not hand-built workflow states.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test import RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from wagtail.models import Page
from wagtail_forum.admin_views import (
    ModerationQueueMenuItem,
    PendingContentMenuItem,
    pending_posts,
)
from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic
from wagtail_forum.wagtail_hooks import (
    _pending_moderation_count,
    register_moderation_queue_menu_item,
    register_pending_content_menu_item,
)
from wagtail_forum.workflow import (
    ensure_default_workflow,
    submit_edit_for_moderation,
    submit_for_moderation,
)

User = get_user_model()
pytestmark = pytest.mark.django_db

SPAM = "http://a.com http://b.com http://c.com http://d.com http://e.com"


def _board():
    ensure_default_workflow()
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _member(username):
    """Trust NEW (0): the trust-0 test account of the owner's walkthrough."""
    user = User.objects.create_user(username=username)
    ForumProfile.for_user(user)
    return user


def _body(text):
    return [{"type": "paragraph", "value": f"<p>{text}</p>"}]


def _pending_topic(author, board, title="Held topic", *, post_author=None):
    topic = Topic.objects.create(
        board=board,
        title=title,
        slug=title.lower().replace(" ", "-"),
        author=author,
        live=False,
    )
    post = Post(
        topic=topic,
        author=post_author or author,
        is_opening_post=True,
        body=_body(f"{title} body {SPAM}"),
    )
    post.save()
    assert submit_for_moderation(post, post_author or author) == "pending"
    topic.refresh_from_db()
    assert topic.live is False
    return topic, post


def _live_topic(author, board, title="Live topic"):
    topic = Topic.objects.create(
        board=board,
        title=title,
        slug=title.lower().replace(" ", "-"),
        author=author,
        live=False,
    )
    post = Post(topic=topic, author=author, is_opening_post=True, body=_body("ok"))
    post.save()
    assert submit_for_moderation(post, author) == "published"
    topic.refresh_from_db()
    return topic, post


def _pending_reply(author, topic, text="held reply"):
    reply = Post(topic=topic, author=author, body=_body(f"{text} {SPAM}"))
    reply.save()
    assert submit_for_moderation(reply, author) == "pending"
    return reply


def _pending_edit(author, post, text="held edit"):
    from wagtail_forum.blocks import ForumBodyBlock

    post.body = ForumBodyBlock().to_python(_body(f"{text} {SPAM}"))
    assert submit_edit_for_moderation(post, author) == "pending"
    post.refresh_from_db()
    assert post.live is True
    return post


def _moderator(username="moderator"):
    """A member of the host's bootstrapped "Forum Moderators" group, the real
    audience, so the gate is proven against what a deploy grants."""
    user = User.objects.create_user(username=username)
    user.groups.add(Group.objects.get(name="Forum Moderators"))
    return user


def _staff(username, *codenames):
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


def _page_url():
    return reverse("wagtail_forum_pending:index")


def _approve_url(post):
    return reverse("wagtail_forum_pending:approve", args=[post.pk])


def _approve(client, post, revision=None):
    """POST Approve as the page's form does: with the revision the row shows."""
    if revision is None:
        post.refresh_from_db()
        revision = post.latest_revision_id or ""
    return client.post(_approve_url(post), {"revision": revision})


# --- One page lists every pending topic and post ----------------------------


def test_page_lists_new_topics_replies_and_held_edits_and_nothing_decided(client):
    board = _board()
    author = _member("newbie")
    held_topic, held_opening = _pending_topic(author, board, "Held topic")
    live_topic, live_opening = _live_topic(author, board, "Live topic")
    reply = _pending_reply(author, live_topic, "held reply")
    edited = _pending_edit(author, live_opening, "held edit")
    # Decided content is not pending: a clean live reply, and a post a
    # moderator took down.
    clean = Post(topic=live_topic, author=author, body=_body("clean reply"))
    clean.save()
    assert submit_for_moderation(clean, author) == "published"
    taken_down = Post(topic=live_topic, author=author, body=_body("taken down"))
    taken_down.save()
    submit_for_moderation(taken_down, author)
    taken_down.refresh_from_db()
    taken_down.unpublish()

    assert set(pending_posts().values_list("pk", flat=True)) == {
        held_opening.pk,
        reply.pk,
        edited.pk,
    }

    client.force_login(_moderator())
    resp = client.get(_page_url())

    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Pending forum content" in html
    # Each row shows what is waiting: the body excerpt, the kind, the author
    # and their trust.
    assert "Held topic body" in html
    assert "held reply" in html
    assert "New topic" in html
    assert "Reply" in html
    assert "Edit" in html
    assert "newbie" in html
    # The held EDIT's excerpt is the submitted revision, not the live body.
    assert "held edit" in html
    assert "clean reply" not in html
    assert "taken down" not in html
    assert html.count(">Approve<") == 3
    # The test client skips CSRF checks, so pin that each Approve form
    # really carries the token a browser needs.
    import re

    approve_forms = re.findall(
        r'action="[^"]*/approve/">\s*<input type="hidden" '
        r'name="csrfmiddlewaretoken" value="[^"]+"',
        html,
    )
    assert len(approve_forms) == 3


@override_settings(
    WAGTAILFORUM_SPAM_BACKEND="wagtail_forum.tests.api.test_topic_create.RaisingSpamBackend"
)
def test_page_lists_a_draft_whose_spam_backend_crashed():
    # The old dashboard count missed this one (the crash rolls the workflow
    # state back). It is still a never-published draft, so it is pending.
    board = _board()
    author = _member("newbie")
    topic = Topic.objects.create(
        board=board, title="Crash", slug="crash", author=author, live=False
    )
    post = Post(topic=topic, author=author, is_opening_post=True, body=_body("x"))
    post.save()
    assert submit_for_moderation(post, author) == "pending"
    assert post.current_workflow_state is None

    assert list(pending_posts()) == [post]


# --- A single Approve publishes the topic together with its opening post ------


def test_one_approve_publishes_the_topic_and_its_opening_post(client):
    board = _board()
    author = _member("newbie")
    topic, post = _pending_topic(author, board)
    moderator = _moderator()
    client.force_login(moderator)

    resp = _approve(client, post)

    assert resp.status_code == 302
    assert resp["Location"] == _page_url()
    topic.refresh_from_db()
    post.refresh_from_db()
    assert topic.live is True
    assert post.live is True
    # The spam hold is cancelled, so the row and the dashboard count go.
    assert post.current_workflow_state is None
    assert not pending_posts().exists()
    assert _pending_moderation_count() == 0
    # Both publishes are attributed to the moderator who approved them.
    from wagtail.log_actions import registry

    for obj in (post, topic):
        entry = registry.get_logs_for_instance(obj).filter(action="wagtail.publish")
        assert entry.get().user == moderator


def test_approve_publishes_the_thread_even_when_the_halves_have_different_authors(
    client,
):
    # The receiver's same-author guard stops an AUTHOR forcing someone
    # else's topic live. A moderator approving the thread is not that.
    board = _board()
    owner = _member("owner")
    other = _member("other")
    topic, post = _pending_topic(owner, board, post_author=other)
    client.force_login(_moderator())

    _approve(client, post)

    topic.refresh_from_db()
    post.refresh_from_db()
    assert topic.live is True
    assert post.live is True


def test_approve_of_a_held_edit_publishes_the_submitted_body(client):
    board = _board()
    author = _member("newbie")
    _topic, post = _live_topic(author, board)
    _pending_edit(author, post, "held edit")
    client.force_login(_moderator())

    _approve(client, post)

    post.refresh_from_db()
    assert "held edit" in post.body.raw_data[0]["value"]
    assert post.has_unpublished_changes is False
    assert not pending_posts().exists()


def test_approve_of_a_reply_publishes_only_that_reply(client):
    board = _board()
    author = _member("newbie")
    topic, _ = _live_topic(author, board)
    reply = _pending_reply(author, topic)
    other = _pending_reply(author, topic, "another")
    client.force_login(_moderator())

    _approve(client, reply)

    reply.refresh_from_db()
    other.refresh_from_db()
    assert reply.live is True
    assert other.live is False


def test_approve_of_content_no_longer_pending_is_404_and_publishes_nothing(client):
    board = _board()
    author = _member("newbie")
    _topic, live = _live_topic(author, board)
    live.unpublish()  # a moderator's take-down: decided, not pending
    client.force_login(_moderator())

    resp = _approve(client, live)

    assert resp.status_code == 404
    live.refresh_from_db()
    assert live.live is False


def test_approve_refuses_a_revision_the_moderator_did_not_see(client):
    # The author edits a held post again after the page loaded: the new text
    # is held too, and the moderator's Approve is for the text they saw.
    board = _board()
    author = _member("newbie")
    _topic, post = _live_topic(author, board)
    _pending_edit(author, post, "first held edit")
    seen = post.latest_revision_id
    _pending_edit(author, post, "second held edit")
    assert post.latest_revision_id != seen
    client.force_login(_moderator())

    resp = _approve(client, post, revision=seen)

    assert resp.status_code == 302
    assert resp["Location"] == _page_url()
    post.refresh_from_db()
    assert "held edit" not in post.body.raw_data[0]["value"]
    assert list(pending_posts()) == [post]
    shown = client.get(_page_url()).content.decode()
    assert "changed after this page loaded" in shown
    assert "second held edit" in shown


def test_approve_without_the_revision_publishes_nothing(client):
    board = _board()
    _topic, post = _pending_topic(_member("newbie"), board)
    client.force_login(_moderator())

    resp = client.post(_approve_url(post))

    assert resp.status_code == 302
    post.refresh_from_db()
    assert post.live is False
    assert list(pending_posts()) == [post]


def test_a_second_approve_of_the_same_row_publishes_nothing_more(client):
    # A double-click, or a second moderator on a page loaded before the first
    # approved: the second request finds the post no longer pending.
    from wagtail.log_actions import registry

    board = _board()
    topic, post = _pending_topic(_member("newbie"), board)
    client.force_login(_moderator())
    post.refresh_from_db()
    seen = post.latest_revision_id

    first = _approve(client, post, revision=seen)
    second = _approve(client, post, revision=seen)

    assert first.status_code == 302
    assert second.status_code == 404
    for obj in (post, topic):
        assert (
            registry.get_logs_for_instance(obj).filter(action="wagtail.publish").count()
            == 1
        )


def _take_down_by_moderator(post):
    from wagtail.actions.unpublish import UnpublishAction

    UnpublishAction(post, user=_moderator("takedown-mod")).execute(
        skip_permission_checks=True
    )


def _take_down_by_reports(post):
    from wagtail_forum.conf import get_setting
    from wagtail_forum.models import Report

    for i in range(get_setting("REPORT_AUTO_HIDE_THRESHOLD")):
        Report.file(post, _member(f"reporter{i}"), Report.SPAM)


@pytest.mark.parametrize("take_down", [_take_down_by_moderator, _take_down_by_reports])
def test_a_held_edit_taken_down_afterwards_is_not_pending_and_approve_404s(
    client, take_down
):
    # A held edit leaves an active NEEDS_CHANGES state and UnpublishAction
    # does not cancel it. The post must still leave the queue, or one
    # Approve would publish content someone removed.
    board = _board()
    author = _member("newbie")
    _topic, post = _live_topic(author, board)
    _pending_edit(author, post, "held edit")
    assert post.current_workflow_state is not None
    assert list(pending_posts()) == [post]

    take_down(post)
    post.refresh_from_db()
    assert post.live is False
    assert post.current_workflow_state is not None  # the state survives

    assert not pending_posts().exists()
    assert _pending_moderation_count() == 0
    client.force_login(_moderator())
    assert "held edit" not in client.get(_page_url()).content.decode()

    resp = _approve(client, post)

    assert resp.status_code == 404
    post.refresh_from_db()
    assert post.live is False
    assert "held edit" not in post.body.raw_data[0]["value"]


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_a_held_edit_the_author_then_deletes_is_not_pending():
    from rest_framework.test import APIClient

    board = _board()
    author = _member("newbie")
    topic, _opening = _live_topic(author, board)
    reply = Post(topic=topic, author=author, body=_body("ok reply"))
    reply.save()
    assert submit_for_moderation(reply, author) == "published"
    _pending_edit(author, reply, "held edit")
    assert list(pending_posts()) == [reply]

    api = APIClient()
    api.force_authenticate(author)
    assert api.delete(f"/forum/posts/{reply.id}/").status_code == 204

    reply.refresh_from_db()
    assert reply.live is False
    assert reply.current_workflow_state is not None
    assert not pending_posts().exists()


def test_approve_is_post_only(client):
    board = _board()
    _topic, post = _pending_topic(_member("newbie"), board)
    client.force_login(_moderator())

    resp = client.get(_approve_url(post))

    assert resp.status_code == 405
    post.refresh_from_db()
    assert post.live is False


def test_reject_links_to_the_delete_confirmation_for_new_content_only(client):
    board = _board()
    author = _member("newbie")
    topic, opening = _pending_topic(author, board)
    live_topic, live_opening = _live_topic(author, board)
    reply = _pending_reply(author, live_topic)
    _pending_edit(author, live_opening)
    client.force_login(_moderator())

    html = client.get(_page_url()).content.decode()

    topic_delete = reverse(
        Topic.snippet_viewset.get_url_name("delete"), args=[topic.pk]
    )
    reply_delete = reverse(Post.snippet_viewset.get_url_name("delete"), args=[reply.pk])
    edit_delete = reverse(
        Post.snippet_viewset.get_url_name("delete"), args=[live_opening.pk]
    )
    # Rejecting a new topic removes the thread; the confirmation returns here.
    assert f'href="{topic_delete}?next=' in html
    assert f'href="{reply_delete}?next=' in html
    # A held edit has no Reject: deleting would take the live post down.
    assert f'href="{edit_delete}?' not in html
    assert html.count(">Reject<") == 2


def test_reject_never_targets_a_live_topic(client):
    # A topic can go live while its opening post is still a draft: here an
    # admin publishes the topic, and the same-author guard keeps the other
    # author's opening post a draft. That row is still pending, but deleting
    # the topic would remove a live thread, so it offers no Reject at all.
    board = _board()
    topic, opening = _pending_topic(
        _member("owner"), board, post_author=_member("other")
    )
    admin = User.objects.create_superuser(username="root", email="r@x.io")
    topic.save_revision(user=admin).publish(user=admin)
    topic.refresh_from_db()
    opening.refresh_from_db()
    assert topic.live is True
    assert opening.live is False
    assert list(pending_posts()) == [opening]
    client.force_login(_moderator())

    html = client.get(_page_url()).content.decode()

    topic_delete = reverse(
        Topic.snippet_viewset.get_url_name("delete"), args=[topic.pk]
    )
    post_delete = reverse(
        Post.snippet_viewset.get_url_name("delete"), args=[opening.pk]
    )
    assert html.count(">Approve<") == 1
    assert f'href="{topic_delete}?' not in html
    assert f'href="{post_delete}?' not in html
    assert ">Reject<" not in html


# --- Who can open it -------------------------------------------------------


def test_page_and_approve_need_the_publish_post_permission(client):
    board = _board()
    _topic, post = _pending_topic(_member("newbie"), board)
    # change_post alone can edit a post but not publish one.
    client.force_login(_staff("editor", "change_post", "view_post"))

    page = client.get(_page_url())
    approve = _approve(client, post)

    assert page.status_code == 302
    assert page["Location"] == reverse("wagtailadmin_home")
    assert approve.status_code in (302, 403)
    post.refresh_from_db()
    assert post.live is False


def test_menu_item_is_shown_to_moderators_and_superusers_only():
    item = register_pending_content_menu_item()
    assert isinstance(item, PendingContentMenuItem)
    assert item.url == _page_url()

    factory = RequestFactory()

    def shown(user):
        request = factory.get("/")
        request.user = user
        return item.is_shown(request)

    assert shown(_moderator()) is True
    assert shown(User.objects.create_superuser(username="root", email="r@x.io"))
    assert shown(_staff("editor", "change_post")) is False


def test_page_query_count_does_not_grow_with_rows(client):
    board = _board()
    author = _member("newbie")
    topic, _ = _live_topic(author, board)
    _pending_reply(author, topic, "one")
    client.force_login(_moderator())
    client.get(_page_url())  # warm per-process caches

    with CaptureQueriesContext(connection) as one:
        client.get(_page_url())
    for i in range(3):
        _pending_reply(author, topic, f"more {i}")
    _pending_topic(_member("other"), board, "Second topic")
    with CaptureQueriesContext(connection) as five:
        client.get(_page_url())

    assert len(five) == len(one)


# --- The dashboard count links to that page ----------------------------------


def test_dashboard_count_links_to_the_pending_page_and_counts_its_rows(client):
    board = _board()
    author = _member("newbie")
    _pending_topic(author, board)
    live_topic, _ = _live_topic(author, board)
    _pending_reply(author, live_topic)
    client.force_login(User.objects.create_superuser(username="root", email="r@x"))

    resp = client.get(reverse("wagtailadmin_home"))

    assert resp.status_code == 200
    html = resp.content.decode()
    assert "2 Forum posts awaiting moderation" in html
    assert f'href="{_page_url()}"' in html
    assert _pending_moderation_count() == pending_posts().count() == 2


# --- The Reports menu names ---------------------------------------------------


def test_reports_menu_item_is_named_for_reported_content():
    item = register_moderation_queue_menu_item()

    assert isinstance(item, ModerationQueueMenuItem)
    assert item.label == "Reported forum content"
    assert "moderation queue" not in item.label.lower()
    # Pending content is its own, separately named item.
    assert register_pending_content_menu_item().label == "Pending forum content"


def test_reported_content_page_title_matches_its_menu_item(client):
    client.force_login(User.objects.create_superuser(username="root", email="r@x"))

    resp = client.get(reverse("wagtail_forum_reports:moderation_queue"))

    assert resp.status_code == 200
    assert "Reported forum content" in resp.content.decode()
    assert "Forum moderation queue" not in resp.content.decode()


# --- The owner's walkthrough, as far as the repo reaches ----------------------


def test_walkthrough_trust0_posts_moderator_approves_thread_is_complete_in_api(
    client,
):
    """A trust-0 account posts through the API the app uses, a moderator
    approves once on the pending page, and the topic-detail and post-list
    endpoints the app reads return the thread with its body. The on-device
    check itself is the owner's (todo 423's last criterion)."""
    from rest_framework.test import APIClient

    board = _board()
    author = _member("trust0")
    api = APIClient()
    api.force_authenticate(author)
    created = api.post(
        f"/api/v1/forum/boards/{board.slug}/topics/",
        {"title": "Video post", "slug": "video-post", "body": _body(f"look {SPAM}")},
        format="json",
    )
    assert created.status_code == 201, created.content
    assert created.data["status"] == "pending"
    topic = Topic.objects.get(pk=created.data["id"])
    opening = topic.posts.get(is_opening_post=True)

    client.force_login(_moderator())
    listing = client.get(_page_url()).content.decode()
    assert "Video post" in listing
    _approve(client, opening)

    reader = APIClient()
    detail = reader.get(f"/api/v1/forum/topics/{topic.pk}/")
    posts = reader.get(f"/api/v1/forum/topics/{topic.pk}/posts/")
    assert detail.status_code == 200
    assert posts.status_code == 200
    bodies = [p["body"][0]["value"] for p in posts.data["results"]]
    assert len(bodies) == 1 and "look" in bodies[0]
