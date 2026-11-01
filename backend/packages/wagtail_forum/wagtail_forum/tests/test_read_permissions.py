"""Forum read permissions on every read path (todo 676; replaces is_hidden).

A members-closed forum opened to one group: a member outside the group gets
404 (never 403) on the topic and the post, and the forum's content is left
out of their search, quotes, mentions, notifications and digest, while a
member of the group gets all of them. Guests follow the guest grants. Staff
and forum moderators bypass a No access grant (owner decision 2026-10-30).
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail_forum.digest import build_digest
from wagtail_forum.mentions import resolve_mentioned_users
from wagtail_forum.models import (
    ForumGrant,
    ForumModerator,
    ForumRole,
    Notification,
    NotificationVerb,
    Post,
    Topic,
)
from wagtail_forum.services.forum_permissions import set_grant
from wagtail_forum.tests.factories import make_forum

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]

WORD = "zygocactus"


def _topic(board, author, title, *, body=None, replies=0):
    topic = Topic.objects.create(
        board=board,
        title=title,
        slug=title.lower().replace(" ", "-"),
        author=author,
        live=True,
        reply_count=replies,
        last_post_at=timezone.now(),
    )
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=body or [{"type": "paragraph", "value": f"<p>{title} {WORD}</p>"}],
    )
    return topic, post


@pytest.fixture
def world():
    """``private`` is closed to guests and members and open to Insiders."""
    insiders = Group.objects.create(name="Insiders")
    insider = User.objects.create_user(username="insider")
    insider.groups.add(insiders)
    outsider = User.objects.create_user(username="outsider")
    author = User.objects.create_user(username="author")
    public = make_forum(name="Public", slug="public")
    private = make_forum(name="Private", slug="private")
    set_grant(private, ForumGrant.ANONYMOUS, ForumRole.NO_ACCESS)
    set_grant(private, ForumGrant.MEMBERS, ForumRole.NO_ACCESS)
    set_grant(private, ForumGrant.GROUP, ForumRole.STANDARD, group=insiders)
    topic, post = _topic(private, author, f"Private {WORD}", replies=5)
    return {
        "insider": insider,
        "outsider": outsider,
        "author": author,
        "public": public,
        "private": private,
        "topic": topic,
        "post": post,
    }


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(User.objects.get(pk=user.pk))
    return client


def test_topic_is_404_without_read_access_and_200_with_it(world):
    url = f"/forum/topics/{world['topic'].pk}/"

    assert _client(world["outsider"]).get(url).status_code == 404
    assert _client().get(url).status_code == 404
    assert _client(world["insider"]).get(url).status_code == 200


def test_topic_list_and_post_list_follow_the_grants(world):
    board = f"/forum/boards/{world['private'].slug}/topics/"
    posts = f"/forum/topics/{world['topic'].pk}/posts/"

    assert _client(world["outsider"]).get(board).status_code == 404
    assert _client(world["outsider"]).get(posts).status_code == 404
    assert _client(world["insider"]).get(board).status_code == 200
    assert _client(world["insider"]).get(posts).status_code == 200


def test_post_is_404_without_read_access_and_200_with_it(world):
    url = f"/forum/posts/{world['post'].pk}/"

    assert _client(world["outsider"]).get(url).status_code == 404
    assert _client(world["insider"]).get(url).status_code == 200


def test_search_hits_follow_the_grants(world):
    def hits(user):
        data = _client(user).get(f"/forum/search/?q={WORD}").data
        return [t["id"] for t in data["topics"]], [p["id"] for p in data["posts"]]

    assert hits(world["outsider"]) == ([], [])
    assert hits(None) == ([], [])
    topics, posts = hits(world["insider"])
    assert world["topic"].pk in topics
    assert world["post"].pk in posts


def test_a_quote_of_a_post_the_reader_cannot_read_is_unavailable(world):
    quoting_topic, _ = _topic(
        world["public"],
        world["author"],
        "Quoting",
        body=[
            {
                "type": "post_quote",
                "value": {"post": world["post"].pk, "text": "copied text"},
            }
        ],
    )
    url = f"/forum/topics/{quoting_topic.pk}/posts/"

    def quote(user):
        body = _client(user).get(url).data["results"][0]["body"]
        return next(b["value"] for b in body if b["type"] == "post_quote")

    assert quote(world["outsider"])["available"] is False
    assert quote(world["outsider"])["topic_id"] is None
    assert quote(world["insider"])["available"] is True
    assert quote(world["insider"])["topic_id"] == world["topic"].pk


def test_a_mention_notifies_only_members_who_can_read_the_forum(world):
    _, post = _topic(
        world["private"],
        world["author"],
        "Hello",
        body=[{"type": "paragraph", "value": "<p>@insider @outsider look</p>"}],
    )

    mentioned = resolve_mentioned_users(post)

    assert [u.username for u in mentioned] == ["insider"]


def test_notifications_follow_the_recipients_grants(world):
    for user in (world["insider"], world["outsider"]):
        Notification.objects.create(
            recipient=user,
            actor=world["author"],
            verb=NotificationVerb.REPLY,
            topic=world["topic"],
            post=world["post"],
        )

    def listed(user):
        return len(_client(user).get("/forum/notifications/").data["results"])

    assert listed(world["outsider"]) == 0
    assert listed(world["insider"]) == 1


def test_digest_entries_follow_the_recipients_grants(world):
    since = timezone.now() - timedelta(days=7)
    for user in (world["insider"], world["outsider"]):
        Notification.objects.create(
            recipient=user,
            actor=world["author"],
            verb=NotificationVerb.REPLY,
            topic=world["topic"],
            post=world["post"],
        )

    outsider = build_digest(world["outsider"], since)
    insider = build_digest(world["insider"], since)

    assert outsider.watched == [] and outsider.trending == []
    assert [t.title for t in insider.watched] == [world["topic"].title]


def test_guests_follow_the_guest_grants():
    author = User.objects.create_user(username="a")
    members_only = make_forum(name="Members", slug="members")
    set_grant(members_only, ForumGrant.ANONYMOUS, ForumRole.NO_ACCESS)
    open_forum = make_forum(name="Open", slug="open")
    closed_topic, _ = _topic(members_only, author, "Closed")
    open_topic, _ = _topic(open_forum, author, "Opened")
    member = User.objects.create_user(username="m")

    assert _client().get(f"/forum/topics/{closed_topic.pk}/").status_code == 404
    assert _client().get(f"/forum/topics/{open_topic.pk}/").status_code == 200
    assert _client(member).get(f"/forum/topics/{closed_topic.pk}/").status_code == 200
    slugs = [b["slug"] for b in _client().get("/forum/boards/").data["results"]]
    assert slugs == ["open"]


def test_staff_and_the_forums_moderators_bypass_no_access(world):
    staff = User.objects.create_user(username="staff", is_staff=True)
    moderator = User.objects.create_user(username="mod")
    ForumModerator.objects.create(forum=world["private"], user=moderator)
    url = f"/forum/topics/{world['topic'].pk}/"

    assert _client(staff).get(url).status_code == 200
    assert _client(moderator).get(url).status_code == 200


def _count(client, url):
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return len(ctx.captured_queries)


def test_index_and_topic_list_query_counts_are_fixed(world):
    """Grants are SQL inside the one forum query: the count does not grow
    with forums, grants or groups."""
    _topic(world["public"], world["author"], "First")  # a non-empty list
    client = _client(world["insider"])
    # Warm the per-process caches (content types, the profile row) first.
    _count(client, "/forum/categories/")
    _count(client, "/forum/boards/public/topics/")
    small_index = _count(client, "/forum/categories/")
    small_list = _count(client, "/forum/boards/public/topics/")

    for n in range(5):
        group = Group.objects.create(name=f"G{n}")
        world["insider"].groups.add(group)
        forum = make_forum(name=f"F{n}", slug=f"f{n}")
        set_grant(forum, ForumGrant.MEMBERS, ForumRole.NO_ACCESS)
        set_grant(forum, ForumGrant.GROUP, ForumRole.FULL, group=group)
        _topic(forum, world["author"], f"T{n}")
        _topic(world["public"], world["author"], f"P{n}")
    client = _client(world["insider"])
    _count(client, "/forum/categories/")
    _count(client, "/forum/boards/public/topics/")

    assert _count(client, "/forum/categories/") == small_index
    assert _count(client, "/forum/boards/public/topics/") == small_list


BEFORE_GRANTS = ("wagtail_forum", "0047_forum_permissions")


# transaction=True is unavoidable for MigrationExecutor (see
# test_forum_model_migration.py, which this mirrors).
@pytest.mark.django_db(transaction=True)
def test_is_hidden_forums_remain_invisible_after_the_data_migration():
    from django.db.migrations.executor import MigrationExecutor
    from wagtail_forum.services.forum_permissions import is_hidden_for_everyone

    author = User.objects.create_user(username="mig-676")
    executor = MigrationExecutor(connection)
    executor.migrate([BEFORE_GRANTS])
    try:
        old = executor.loader.project_state([BEFORE_GRANTS]).apps
        OldForum = old.get_model("wagtail_forum", "Forum")
        OldTopic = old.get_model("wagtail_forum", "Topic")
        category = OldForum.objects.create(
            forum_type="category", name="Cat", slug="cat"
        )
        hidden_cat = OldForum.objects.create(
            forum_type="category", name="Staff", slug="staff-cat", is_hidden=True
        )
        hidden = OldForum.objects.create(
            forum_type="forum", parent=category, name="Hid", slug="hid", is_hidden=True
        )
        under_hidden = OldForum.objects.create(
            forum_type="forum", parent=hidden_cat, name="Under", slug="under"
        )
        shown = OldForum.objects.create(
            forum_type="forum", parent=category, name="Shown", slug="shown"
        )
        topics = {
            forum.slug: OldTopic.objects.create(
                board_id=forum.pk, title="T", slug="t", author_id=author.pk, live=True
            ).pk
            for forum in (hidden, under_hidden, shown)
        }
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    from wagtail_forum.models import Forum

    assert is_hidden_for_everyone(Forum.objects.get(slug="hid"))
    assert is_hidden_for_everyone(
        Forum.objects.get(slug="staff-cat", forum_type="category")
    )
    assert not is_hidden_for_everyone(Forum.objects.get(slug="shown"))
    member = User.objects.create_user(username="member-676")
    for slug, expected in (("hid", 404), ("under", 404), ("shown", 200)):
        for client in (_client(), _client(member)):
            assert client.get(f"/forum/topics/{topics[slug]}/").status_code == expected
