"""Per-forum moderators (todo 674; owner decision 2026-10-30).

A ``ForumModerator`` (a user, or a group the user is in) moderates one forum
through the existing admin screens: they may act on a topic in their forum
and are refused in another, and the pending and reports queues show them
their forums' rows only. A move needs both forums to be theirs.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from rest_framework.test import APIClient
from wagtail_forum.models import (
    Conversation,
    ForumModerator,
    ForumProfile,
    Message,
    Post,
    Report,
    Topic,
)
from wagtail_forum.tests.factories import make_forum
from wagtail_forum.wagtail_hooks import (
    PostAdminForm,
    ReportAdminForm,
    TopicAdminForm,
    topic_policy,
)
from wagtail_forum.workflow import ensure_default_workflow, submit_for_moderation

User = get_user_model()
pytestmark = pytest.mark.django_db
XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
SPAM = "http://a.com http://b.com http://c.com http://d.com http://e.com http://f.com"


def _admin_user(username):
    """Enters the admin, holds no forum model permission at all."""
    user = User.objects.create_user(username=username)
    user.user_permissions.set(Permission.objects.filter(codename="access_admin"))
    return User.objects.get(pk=user.pk)


def _topic(board, title):
    author = User.objects.create_user(username=f"a-{title}")
    topic = Topic.objects.create(
        board=board, title=title, slug=title, author=author, live=True
    )
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": f"<p>{title}</p>"}],
    )
    return topic, post


def _pending_topic(board, title):
    author = User.objects.create_user(username=f"p-{title}")
    ForumProfile.for_user(author)
    topic = Topic.objects.create(
        board=board, title=title, slug=title, author=author, live=False
    )
    post = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{title} {SPAM}</p>"}],
    )
    post.save()
    assert submit_for_moderation(post, author) == "pending"
    return topic, post


@pytest.fixture
def forums():
    ensure_default_workflow()
    mine = make_forum(name="Ferns", slug="ferns")
    other = make_forum(name="Cacti", slug="cacti")
    return mine, other


@pytest.fixture
def moderator(forums):
    user = _admin_user("fern-mod")
    ForumModerator.objects.create(forum=forums[0], user=user)
    return user


def _edit_url(topic):
    return reverse(Topic.snippet_viewset.get_url_name("edit"), args=[topic.pk])


def test_a_forum_moderator_can_act_on_a_topic_in_their_forum_only(
    client, forums, moderator
):
    mine, other = forums
    in_mine, _ = _topic(mine, "fronds")
    in_other, _ = _topic(other, "spines")
    client.force_login(moderator)

    assert client.get(_edit_url(in_mine)).status_code == 200
    assert client.get(_edit_url(in_other), **XHR).status_code == 403
    for action in ("change", "publish", "unpublish"):
        assert topic_policy.user_has_permission_for_instance(moderator, action, in_mine)
        assert not topic_policy.user_has_permission_for_instance(
            moderator, action, in_other
        )
    # Moderating is not owning: no delete.
    assert not topic_policy.user_has_permission_for_instance(
        moderator, "delete", in_mine
    )


def test_a_group_moderator_is_scoped_the_same_way(client, forums):
    mine, other = forums
    group = Group.objects.create(name="Fern team")
    user = _admin_user("team-member")
    user.groups.add(group)
    ForumModerator.objects.create(forum=mine, group=group)
    in_mine, _ = _topic(mine, "fronds")
    in_other, _ = _topic(other, "spines")
    client.force_login(User.objects.get(pk=user.pk))

    assert client.get(_edit_url(in_mine)).status_code == 200
    assert client.get(_edit_url(in_other), **XHR).status_code == 403


def test_the_topic_listing_shows_a_forum_moderator_only_their_forums(
    client, forums, moderator
):
    mine, other = forums
    _topic(mine, "fronds")
    _topic(other, "spines")
    client.force_login(moderator)

    body = client.get(
        reverse(Topic.snippet_viewset.get_url_name("list"))
    ).content.decode()

    assert "fronds" in body and "spines" not in body


def test_a_move_is_offered_only_to_forums_the_moderator_moderates(forums, moderator):
    mine, other = forums
    third = make_forum(name="Palms", slug="palms")
    ForumModerator.objects.create(forum=third, user=moderator)
    topic, _ = _topic(mine, "fronds")
    form_class = Topic.snippet_viewset.get_form_class()
    assert issubclass(form_class, TopicAdminForm)

    form = form_class(instance=topic, for_user=moderator)
    choices = set(form.fields["board"].queryset.values_list("pk", flat=True))

    assert choices == {mine.pk, third.pk}
    assert other.pk not in choices


def test_a_post_moves_only_into_topics_of_forums_the_moderator_moderates(
    forums, moderator
):
    mine, other = forums
    fronds, post = _topic(mine, "fronds")
    ferns_too, _ = _topic(mine, "ferns-too")
    spines, _ = _topic(other, "spines")
    form_class = Post.snippet_viewset.get_form_class()
    assert issubclass(form_class, PostAdminForm)

    form = form_class(instance=post, for_user=moderator)
    choices = set(form.fields["topic"].queryset.values_list("pk", flat=True))

    assert choices == {fronds.pk, ferns_too.pk}
    assert spines.pk not in choices


def test_change_post_everywhere_still_offers_every_topic(forums, moderator):
    mine, other = forums
    _, post = _topic(mine, "fronds")
    spines, _ = _topic(other, "spines")
    _grant(moderator, "change_post")
    moderator = User.objects.get(pk=moderator.pk)

    form = Post.snippet_viewset.get_form_class()(instance=post, for_user=moderator)

    assert spines.pk in set(form.fields["topic"].queryset.values_list("pk", flat=True))


def test_the_topic_chooser_lists_a_forum_moderator_only_their_forums(
    client, forums, moderator
):
    mine, other = forums
    _topic(mine, "fronds")
    _topic(other, "spines")
    client.force_login(moderator)
    chooser = Topic.snippet_viewset.chooser_viewset

    for name in ("choose", "choose_results"):
        page = client.get(reverse(chooser.get_url_name(name)), **XHR)
        assert page.status_code == 200
        body = page.content.decode()
        assert "fronds" in body and "spines" not in body, name


def test_a_report_offers_a_forum_moderator_only_their_posts_and_no_message(
    forums, moderator
):
    mine, other = forums
    _, post = _topic(mine, "fronds")
    _, elsewhere = _topic(other, "spines")
    report = Report.objects.create(post=post, reporter=post.author, reason="spam")
    dm = Conversation.between(post.author, elsewhere.author)
    Message.objects.create(conversation=dm, sender=post.author, body="private")
    form_class = Report.snippet_viewset.get_form_class()
    assert issubclass(form_class, ReportAdminForm)

    form = form_class(instance=report, for_user=moderator)
    posts = set(form.fields["post"].queryset.values_list("pk", flat=True))

    assert post.pk in posts and elsewhere.pk not in posts
    assert not form.fields["message"].queryset.exists()


def test_the_pending_queue_shows_a_forum_moderator_only_their_forums(
    client, forums, moderator
):
    mine, other = forums
    _pending_topic(mine, "held-fern")
    _, theirs = _pending_topic(other, "held-cactus")
    client.force_login(moderator)

    page = client.get(reverse("wagtail_forum_pending:index"))
    approve = client.post(reverse("wagtail_forum_pending:approve", args=[theirs.pk]))

    assert page.status_code == 200
    body = page.content.decode()
    assert "held-fern" in body and "held-cactus" not in body
    # Approving another forum's row finds nothing to decide.
    assert approve.status_code == 302
    theirs.refresh_from_db()
    assert theirs.live is False


def test_the_reports_queue_shows_a_forum_moderator_only_their_forums(
    client, forums, moderator
):
    mine, other = forums
    _, fern_post = _topic(mine, "fronds")
    _, cactus_post = _topic(other, "spines")
    reporter = User.objects.create_user(username="reporter")
    Report.objects.create(post=fern_post, reporter=reporter, reason=Report.SPAM)
    Report.objects.create(post=cactus_post, reporter=reporter, reason=Report.SPAM)
    client.force_login(moderator)

    page = client.get(reverse("wagtail_forum_reports:moderation_queue"))

    assert page.status_code == 200
    body = page.content.decode()
    assert "fronds" in body and "spines" not in body


def test_a_member_with_no_forum_is_still_refused_the_queues(client, forums):
    client.force_login(_admin_user("nobody"))

    assert client.get(reverse("wagtail_forum_pending:index"), **XHR).status_code == 403


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_the_category_index_lists_each_forums_moderators(forums, moderator):
    mine, other = forums
    group = Group.objects.create(name="Fern team")
    ForumModerator.objects.create(forum=mine, group=group)

    resp = APIClient().get("/forum/categories/")

    rows = {f["slug"]: f for c in resp.json()["results"] for f in c["forums"]}
    assert rows["ferns"]["moderators"] == ["fern-mod", "Fern team"]
    assert rows["cacti"]["moderators"] == []


# Mixed permissions (round-1 review): every bypass of the forum check asks for
# the model permission the view itself needs, never any moderation action.


def _grant(user, *codenames):
    perms = Permission.objects.filter(
        content_type__app_label="wagtail_forum", codename__in=codenames
    )
    assert perms.count() == len(codenames), codenames
    user.user_permissions.add(*perms)
    user = User.objects.get(pk=user.pk)
    assert all(user.has_perm(f"wagtail_forum.{c}") for c in codenames)
    return user


def _url(topic, name):
    return reverse(Topic.snippet_viewset.get_url_name(name), args=[topic.pk])


@pytest.mark.parametrize("global_perm", ["view_topic", "lock_topic"])
def test_a_moderator_with_another_global_permission_still_edits_only_their_forum(
    client, forums, moderator, global_perm
):
    mine, other = forums
    in_mine, _ = _topic(mine, "fronds")
    in_other, _ = _topic(other, "spines")
    user = _grant(moderator, global_perm)
    client.force_login(user)

    assert client.get(_url(in_mine, "edit")).status_code == 200
    assert client.get(_url(in_other, "edit"), **XHR).status_code == 403
    assert client.get(_url(in_other, "unpublish"), **XHR).status_code == 403
    form = Topic.snippet_viewset.get_form_class()(instance=in_mine, for_user=user)
    assert set(form.fields["board"].queryset.values_list("pk", flat=True)) == {mine.pk}


def test_a_moderator_with_global_view_may_inspect_and_list_every_forum(
    client, forums, moderator
):
    mine, other = forums
    _topic(mine, "fronds")
    in_other, _ = _topic(other, "spines")
    client.force_login(_grant(moderator, "view_topic"))

    body = client.get(
        reverse(Topic.snippet_viewset.get_url_name("list"))
    ).content.decode()

    assert "fronds" in body and "spines" in body
    assert client.get(_url(in_other, "inspect")).status_code == 200


@pytest.mark.parametrize("moderates", [False, True])
def test_a_delete_only_user_keeps_the_delete_view_and_the_full_listing(
    client, forums, moderates
):
    mine, other = forums
    _topic(mine, "fronds")
    in_other, _ = _topic(other, "spines")
    user = _grant(_admin_user("deleter"), "delete_topic")
    if moderates:
        ForumModerator.objects.create(forum=mine, user=user)
    client.force_login(user)

    body = client.get(
        reverse(Topic.snippet_viewset.get_url_name("list"))
    ).content.decode()

    assert "fronds" in body and "spines" in body
    assert client.get(_url(in_other, "delete")).status_code == 200
    # Deleting is not editing.
    assert client.get(_url(in_other, "edit"), **XHR).status_code == 403
