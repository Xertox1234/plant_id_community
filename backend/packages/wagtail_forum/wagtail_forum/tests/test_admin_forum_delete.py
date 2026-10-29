"""Safe delete of forum rows in the admin (todo 667): a forum's topics are
moved or deleted first, a category's forums move to another category, and
every target is checked server-side."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from wagtail.models import Revision
from wagtail_forum.models import (
    Forum,
    Post,
    Reaction,
    Topic,
    TopicBookmark,
    TopicDeletedLog,
    TopicSubscription,
)
from wagtail_forum.services import forum_structure
from wagtail_forum.tests.factories import make_category, make_forum

User = get_user_model()

NS = "wagtail_forum_forums"

pytestmark = pytest.mark.django_db


def _url(name, *args):
    return reverse(f"{NS}:{name}", args=args)


@pytest.fixture
def admin_client(client):
    client.force_login(User.objects.create_superuser(username="root", email="r@x.io"))
    return client


def _topic(board, slug, author, replies=1):
    """A live topic with a published opening post and ``replies`` replies."""
    topic = Topic.objects.create(board=board, title=slug, slug=slug, author=author)
    Post.objects.create(
        topic=topic, author=author, is_opening_post=True
    ).save_revision().publish()
    for _ in range(replies):
        Post.objects.create(topic=topic, author=author).save_revision().publish()
    return topic


def _counts(forum):
    forum.refresh_from_db()
    return (forum.topic_count, forum.post_count)


# --- AC0: delete with *move* ---


def test_deleting_a_forum_with_move_puts_every_topic_in_the_target(admin_client):
    author = User.objects.create_user(username="ada")
    source = make_forum(name="Ferns", slug="ferns")
    target = make_forum(name="Pests", slug="pests")
    _topic(target, "already-here", author, replies=0)
    moved = [_topic(source, "a", author), _topic(source, "b", author, replies=2)]
    assert _counts(source) == (2, 5)
    assert _counts(target) == (1, 1)

    resp = admin_client.post(
        _url("delete", source.pk),
        {"topics_action": forum_structure.MOVE, "target": target.pk},
    )

    assert resp.status_code == 302, resp.content.decode()[:2000]
    assert not Forum.objects.filter(pk=source.pk).exists()
    assert set(
        Topic.objects.filter(pk__in=[t.pk for t in moved]).values_list(
            "board_id", flat=True
        )
    ) == {target.pk}
    assert _counts(target) == (3, 6)
    # Nothing was deleted on the way.
    assert Post.objects.filter(topic__in=moved).count() == 5
    assert not TopicDeletedLog.objects.exists()


def test_moving_topics_recounts_the_source_when_it_is_kept():
    """The service half: the source survives (a type change empties it the
    same way) and must read zero, not its old numbers."""
    author = User.objects.create_user(username="ada")
    source = make_forum(name="Ferns", slug="ferns")
    target = make_forum(name="Pests", slug="pests")
    _topic(source, "a", author)

    assert forum_structure.move_topics(source, target) == 1

    assert _counts(source) == (0, 0)
    assert _counts(target) == (1, 2)


def test_a_slug_the_target_already_uses_is_made_unique_not_refused():
    author = User.objects.create_user(username="ada")
    source = make_forum(name="Ferns", slug="ferns")
    target = make_forum(name="Pests", slug="pests")
    _topic(target, "watering", author, replies=0)
    clash = _topic(source, "watering", author, replies=0)
    # A draft saved before the move still names the old forum and slug.
    clash.save_revision()

    forum_structure.move_topics(source, target)

    clash.refresh_from_db()
    assert clash.board_id == target.pk
    assert clash.slug == f"watering-{clash.pk}"
    revision = Revision.objects.filter(
        base_content_type=ContentType.objects.get_for_model(Topic),
        object_id=str(clash.pk),
    ).get()
    assert revision.content["board"] == target.pk
    assert revision.content["slug"] == clash.slug
    # Publishing that draft keeps the topic where it now lives.
    revision.publish()
    clash.refresh_from_db()
    assert (clash.board_id, clash.slug) == (target.pk, f"watering-{clash.pk}")


def test_moving_bumps_updated_at_for_sync_clients():
    author = User.objects.create_user(username="ada")
    source = make_forum(name="Ferns", slug="ferns")
    target = make_forum(name="Pests", slug="pests")
    topic = _topic(source, "a", author, replies=0)
    topic.refresh_from_db()
    before = topic.updated_at

    forum_structure.move_topics(source, target)

    topic.refresh_from_db()
    assert topic.updated_at > before


# --- AC1: delete with *delete* ---


def test_deleting_a_forum_with_delete_removes_topics_posts_and_dependents(
    admin_client,
):
    author = User.objects.create_user(username="ada")
    reader = User.objects.create_user(username="bea")
    source = make_forum(name="Ferns", slug="ferns")
    keep = make_forum(name="Pests", slug="pests")
    kept_topic = _topic(keep, "kept", author)
    doomed = [_topic(source, "a", author), _topic(source, "b", author, replies=3)]
    doomed_ids = [t.pk for t in doomed]
    post = Post.objects.filter(topic=doomed[0]).first()
    Reaction.objects.create(post=post, user=reader, reaction_type=Reaction.LIKE)
    TopicBookmark.objects.create(user=reader, topic=doomed[0])
    TopicSubscription.objects.create(user=reader, topic=doomed[1])
    topic_type = ContentType.objects.get_for_model(Topic)
    post_ids = list(Post.objects.filter(topic__in=doomed).values_list("pk", flat=True))
    assert len(post_ids) == 6

    resp = admin_client.post(
        _url("delete", source.pk), {"topics_action": forum_structure.DELETE}
    )

    assert resp.status_code == 302, resp.content.decode()[:2000]
    assert not Forum.objects.filter(pk=source.pk).exists()
    assert not Topic.objects.filter(pk__in=doomed_ids).exists()
    # No orphan rows: posts, their revisions and reactions, the topics'
    # revisions, bookmarks and subscriptions all went with them.
    assert not Post.objects.filter(pk__in=post_ids).exists()
    assert not Post.objects.filter(topic_id__in=doomed_ids).exists()
    assert not Reaction.objects.filter(post_id__in=post_ids).exists()
    assert not TopicBookmark.objects.filter(topic_id__in=doomed_ids).exists()
    assert not TopicSubscription.objects.filter(topic_id__in=doomed_ids).exists()
    assert not Revision.objects.filter(
        base_content_type=topic_type, object_id__in=[str(i) for i in doomed_ids]
    ).exists()
    assert not Revision.objects.filter(
        base_content_type=ContentType.objects.get_for_model(Post),
        object_id__in=[str(i) for i in post_ids],
    ).exists()
    # Sync clients learn the topics are gone; the other forum is untouched.
    assert set(TopicDeletedLog.objects.values_list("topic_id", flat=True)) == set(
        doomed_ids
    )
    assert Topic.objects.filter(pk=kept_topic.pk).exists()
    assert _counts(keep) == (1, 2)


def test_a_forum_with_topics_needs_a_choice(admin_client):
    source = make_forum(name="Ferns", slug="ferns")
    _topic(source, "a", User.objects.create_user(username="ada"), replies=0)

    page = admin_client.get(_url("delete", source.pk))
    resp = admin_client.post(_url("delete", source.pk), {})

    assert page.status_code == 200
    assert "This forum holds 1 topic." in page.content.decode()
    assert resp.status_code == 200
    assert "topics_action" in resp.context["form"].errors
    assert Forum.objects.filter(pk=source.pk).exists()


def test_an_empty_forum_deletes_on_a_plain_confirm(admin_client):
    forum = make_forum(name="Ferns", slug="ferns")

    resp = admin_client.post(_url("delete", forum.pk), {})

    assert resp.status_code == 302
    assert not Forum.objects.filter(pk=forum.pk).exists()


# --- AC2: every target is validated server-side ---


def _link(category):
    """A link row; the admin cannot create one until todo 670."""
    return Forum.objects.create(
        forum_type=Forum.LINK, parent=category, name="Shop", slug="shop"
    )


@pytest.mark.parametrize("kind", ["self", "category", "link", "missing"])
def test_an_invalid_move_target_is_rejected(admin_client, kind):
    author = User.objects.create_user(username="ada")
    source = make_forum(name="Ferns", slug="ferns")
    topic = _topic(source, "a", author)
    target_id = {
        "self": lambda: source.pk,
        "category": lambda: source.parent_id,
        "link": lambda: _link(source.parent).pk,
        "missing": lambda: Forum.objects.order_by("-pk").first().pk + 1000,
    }[kind]()

    resp = admin_client.post(
        _url("delete", source.pk),
        {"topics_action": forum_structure.MOVE, "target": target_id},
    )

    assert resp.status_code == 200
    assert "target" in resp.context["form"].errors
    assert Forum.objects.filter(pk=source.pk).exists()
    topic.refresh_from_db()
    assert topic.board_id == source.pk
    assert _counts(source) == (1, 2)


@pytest.mark.parametrize("kind", ["self", "category", "link", "missing"])
def test_the_service_refuses_an_invalid_move_target(kind):
    """Defence in depth: the service re-checks what the form's queryset
    already filtered, so a caller that skips the form is refused too."""
    source = make_forum(name="Ferns", slug="ferns")
    _topic(source, "a", User.objects.create_user(username="ada"), replies=0)
    target = {
        "self": lambda: source,
        "category": lambda: source.parent,
        "link": lambda: _link(source.parent),
        "missing": lambda: Forum(pk=10_000_000, forum_type=Forum.FORUM),
    }[kind]()

    with pytest.raises(forum_structure.ValidationError):
        forum_structure.empty_forum(source, forum_structure.MOVE, target)

    assert Topic.objects.filter(board=source).count() == 1


@pytest.mark.parametrize("kind", ["self", "forum", "missing"])
def test_an_invalid_category_target_is_rejected(admin_client, kind):
    category = make_category()
    forum = make_forum(name="Ferns", slug="ferns", category=category)
    target_id = {
        "self": lambda: category.pk,
        "forum": lambda: forum.pk,
        "missing": lambda: forum.pk + 1000,
    }[kind]()

    resp = admin_client.post(
        _url("delete", category.pk), {"target_category": target_id}
    )

    assert resp.status_code == 200
    assert "target_category" in resp.context["form"].errors
    assert Forum.objects.filter(pk=category.pk).exists()
    forum.refresh_from_db()
    assert forum.parent_id == category.pk


# --- AC3: a category with forums needs a target category ---


def test_a_category_with_forums_cannot_be_deleted_without_a_target(admin_client):
    category = make_category()
    forum = make_forum(name="Ferns", slug="ferns", category=category)

    page = admin_client.get(_url("delete", category.pk))
    resp = admin_client.post(_url("delete", category.pk), {})

    assert "This category holds 1 forum." in page.content.decode()
    assert resp.status_code == 200
    assert "target_category" in resp.context["form"].errors
    assert Forum.objects.filter(pk=category.pk).exists()
    forum.refresh_from_db()
    assert forum.parent_id == category.pk


def test_deleting_a_category_moves_its_forums_to_the_end_of_the_target(
    admin_client,
):
    category = make_category()
    first = make_forum(name="Ferns", slug="ferns", category=category, position=0)
    second = make_forum(name="Moss", slug="moss", category=category, position=1)
    other = make_category(name="Outdoor", slug="outdoor")
    resident = make_forum(name="Trees", slug="trees", category=other, position=3)

    resp = admin_client.post(_url("delete", category.pk), {"target_category": other.pk})

    assert resp.status_code == 302, resp.content.decode()[:2000]
    assert not Forum.objects.filter(pk=category.pk).exists()
    assert list(
        Forum.objects.filter(parent=other)
        .order_by("position")
        .values_list("pk", "position")
    ) == [(resident.pk, 3), (first.pk, 4), (second.pk, 5)]


def test_an_empty_category_deletes_on_a_plain_confirm(admin_client):
    category = make_category()

    resp = admin_client.post(_url("delete", category.pk), {})

    assert resp.status_code == 302
    assert not Forum.objects.filter(pk=category.pk).exists()


def test_delete_needs_the_delete_permission(client):

    forum = make_forum(name="Ferns", slug="ferns")
    user = User.objects.create_user(username="editor", email="e@x.io")
    user.user_permissions.set(
        Permission.objects.filter(
            codename__in=["access_admin", "add_forum", "change_forum"]
        )
    )
    client.force_login(user)

    resp = client.post(
        _url("delete", forum.pk), {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
    )

    assert resp.status_code == 403
    assert Forum.objects.filter(pk=forum.pk).exists()


def test_a_topic_added_meanwhile_gives_a_form_error_not_a_500(
    admin_client, monkeypatch
):
    forum = make_forum(name="Ferns", slug="ferns")
    target = make_forum(name="Pests", slug="pests")
    topic = Topic.objects.create(board=forum, title="T", slug="t")
    # Stand-in for a topic created after the move: the move does nothing, so
    # the PROTECT FK refuses the delete.
    monkeypatch.setattr(forum_structure, "empty_forum", lambda *a, **k: 0)

    resp = admin_client.post(
        reverse("wagtail_forum_forums:delete", args=(forum.pk,)),
        {"topics_action": forum_structure.MOVE, "target": target.pk},
    )

    assert resp.status_code == 200
    assert "changed while you were on this page" in resp.content.decode()
    assert Forum.objects.filter(pk=forum.pk).exists()
    assert Topic.objects.get(pk=topic.pk).board_id == forum.pk


def test_deleting_a_hidden_category_keeps_its_forums_hidden(admin_client):
    hidden = make_category(name="Staff", slug="staff")
    hidden.is_hidden = True
    hidden.save()
    visible = make_category(name="Plants", slug="plants")
    forum = make_forum(name="Notes", slug="notes", category=hidden)

    resp = admin_client.post(
        reverse("wagtail_forum_forums:delete", args=(hidden.pk,)),
        {"target_category": visible.pk},
    )

    assert resp.status_code == 302
    forum.refresh_from_db()
    assert forum.parent_id == visible.pk
    assert forum.is_hidden is True


def test_deleting_topics_needs_the_topic_delete_permission(client):
    forum = make_forum(name="Ferns", slug="ferns")
    topic = Topic.objects.create(board=forum, title="T", slug="t")
    user = User.objects.create_user(username="structure", email="s@x.io")
    user.user_permissions.set(
        Permission.objects.filter(
            codename__in=["access_admin", "change_forum", "delete_forum"]
        )
    )
    client.force_login(user)

    resp = client.post(
        reverse("wagtail_forum_forums:delete", args=(forum.pk,)),
        {"topics_action": forum_structure.DELETE},
    )

    assert resp.status_code == 200
    assert "topics_action" in resp.context["form"].errors
    assert Topic.objects.filter(pk=topic.pk, board=forum).exists()
