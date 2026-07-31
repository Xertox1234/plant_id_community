"""Accepted-answer endpoint + clearing rule (audit H6, roadmap Wave 2 slice 2).

The happy path is small; the surface worth pinning is the permission rule, the
422 body validation, and above all the CLEARING rule — a Solved badge must
never survive its answer becoming invisible, and the two ways that happens
(unpublish, hard delete) take different code paths.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.fixture(autouse=True)
def clear_idempotency_cache():
    """LocMemCache is process-global — stop keys bleeding between tests."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def _board(slug):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _moderator(username):
    user = User.objects.create_user(username=username)
    user.user_permissions.add(
        Permission.objects.get(
            codename="change_post", content_type__app_label="wagtail_forum"
        )
    )
    return User.objects.get(pk=user.pk)  # re-fetch: perm cache is per-instance


def _thread(slug, *, live=True):
    """A live topic with an opening post and one live reply by another user."""
    board = _board(slug)
    asker = User.objects.create_user(username=f"asker-{slug}")
    answerer = User.objects.create_user(username=f"answerer-{slug}")
    topic = Topic.objects.create(
        board=board, title="T", slug=f"t-{slug}", author=asker, live=live
    )
    Post.objects.create(topic=topic, author=asker, is_opening_post=True, live=True)
    reply = Post.objects.create(topic=topic, author=answerer, live=True)
    return topic, reply, asker, answerer


def _mark(client, topic, post):
    return client.post(
        f"/forum/topics/{topic.id}/solution/", {"post_id": post.id}, format="json"
    )


@pytest.mark.django_db
def test_topic_author_can_accept_a_reply():
    topic, reply, asker, _ = _thread("accept")
    client = APIClient()
    client.force_authenticate(asker)

    resp = _mark(client, topic, reply)

    assert resp.status_code == 200
    assert resp.data["is_solved"] is True
    assert resp.data["solved_post_id"] == reply.id
    assert resp.data["solved_at"] is not None
    topic.refresh_from_db()
    assert topic.solved_post_id == reply.id
    assert topic.solved_at is not None


@pytest.mark.django_db
def test_a_bystander_cannot_accept_an_answer():
    topic, reply, _, _ = _thread("bystander")
    intruder = User.objects.create_user(username="intruder")
    client = APIClient()
    client.force_authenticate(intruder)

    resp = _mark(client, topic, reply)

    assert resp.status_code == 403
    topic.refresh_from_db()
    assert topic.solved_post_id is None


@pytest.mark.django_db
def test_a_moderator_can_accept_an_answer_on_someone_elses_topic():
    topic, reply, _, _ = _thread("mod")
    client = APIClient()
    client.force_authenticate(_moderator("mod-user"))

    resp = _mark(client, topic, reply)

    assert resp.status_code == 200
    topic.refresh_from_db()
    assert topic.solved_post_id == reply.id


@pytest.mark.django_db
def test_anonymous_cannot_accept_an_answer():
    topic, reply, _, _ = _thread("anon")

    resp = _mark(APIClient(), topic, reply)

    assert resp.status_code == 401
    topic.refresh_from_db()
    assert topic.solved_post_id is None


@pytest.mark.django_db
def test_a_hidden_topic_404s_before_the_permission_check():
    # No existence leak: a draft topic must 404 for a caller who would ALSO have
    # failed the permission check — otherwise the 403-vs-404 split confirms it
    # exists (audit M6/M7).
    topic, reply, _, _ = _thread("hidden", live=False)
    intruder = User.objects.create_user(username="hidden-intruder")
    client = APIClient()
    client.force_authenticate(intruder)

    assert _mark(client, topic, reply).status_code == 404


@pytest.mark.django_db
def test_a_post_from_another_topic_is_rejected():
    topic, _, asker, _ = _thread("mine")
    _, other_reply, _, _ = _thread("theirs")
    client = APIClient()
    client.force_authenticate(asker)

    resp = _mark(client, topic, other_reply)

    assert resp.status_code == 422
    topic.refresh_from_db()
    assert topic.solved_post_id is None


@pytest.mark.django_db
def test_a_non_live_post_cannot_be_accepted():
    # Accepting a post still in the moderation queue would badge the topic
    # Solved over content no reader can see.
    topic, _, asker, answerer = _thread("pending")
    pending = Post.objects.create(topic=topic, author=answerer, live=False)
    client = APIClient()
    client.force_authenticate(asker)

    assert _mark(client, topic, pending).status_code == 422


@pytest.mark.django_db
def test_the_opening_post_cannot_be_accepted():
    topic, _, asker, _ = _thread("opening")
    opening = topic.posts.get(is_opening_post=True)
    client = APIClient()
    client.force_authenticate(asker)

    assert _mark(client, topic, opening).status_code == 422


@pytest.mark.django_db
def test_delete_clears_the_accepted_answer():
    topic, reply, asker, _ = _thread("clear")
    client = APIClient()
    client.force_authenticate(asker)
    _mark(client, topic, reply)

    resp = client.delete(f"/forum/topics/{topic.id}/solution/")

    assert resp.status_code == 200
    assert resp.data["is_solved"] is False
    assert resp.data["solved_post_id"] is None
    assert resp.data["solved_at"] is None
    topic.refresh_from_db()
    assert topic.solved_post_id is None
    assert topic.solved_at is None


@pytest.mark.django_db
def test_delete_on_an_unsolved_topic_is_a_noop_not_an_error():
    topic, _, asker, _ = _thread("noop")
    client = APIClient()
    client.force_authenticate(asker)

    resp = client.delete(f"/forum/topics/{topic.id}/solution/")

    assert resp.status_code == 200
    assert resp.data["is_solved"] is False


@pytest.mark.django_db
def test_a_bystander_cannot_clear_an_accepted_answer():
    topic, reply, asker, _ = _thread("clear-guard")
    owner = APIClient()
    owner.force_authenticate(asker)
    _mark(owner, topic, reply)

    intruder = APIClient()
    intruder.force_authenticate(User.objects.create_user(username="clear-intruder"))
    resp = intruder.delete(f"/forum/topics/{topic.id}/solution/")

    assert resp.status_code == 403
    topic.refresh_from_db()
    assert topic.solved_post_id == reply.id


@pytest.mark.django_db
def test_remarking_the_same_post_keeps_the_original_solved_at():
    # `solved_at` means "when this answer was accepted", not "when someone last
    # tapped the button" — a double-tap must not re-stamp it.
    topic, reply, asker, _ = _thread("remark")
    client = APIClient()
    client.force_authenticate(asker)
    first = _mark(client, topic, reply)

    second = _mark(client, topic, reply)

    assert second.status_code == 200
    assert second.data["solved_at"] == first.data["solved_at"]


@pytest.mark.django_db
def test_accepting_an_answer_writes_no_revision_and_does_not_republish():
    # Topic is a DraftStateMixin/RevisionMixin snippet, so a careless full
    # save() here would write a revision (polluting moderation history) or
    # move last_published_at. Accepting an answer is metadata, not a content
    # edit — `save(update_fields=[...])` is what keeps it so.
    topic, reply, asker, _ = _thread("norev")
    before = Topic.objects.get(pk=topic.pk)
    client = APIClient()
    client.force_authenticate(asker)

    _mark(client, topic, reply)

    topic.refresh_from_db()
    assert topic.revisions.count() == before.revisions.count()
    assert topic.last_published_at == before.last_published_at
    assert topic.live is before.live


@pytest.mark.django_db
def test_accepting_a_second_answer_replaces_the_first():
    topic, reply, asker, answerer = _thread("replace")
    other = Post.objects.create(topic=topic, author=answerer, live=True)
    client = APIClient()
    client.force_authenticate(asker)
    _mark(client, topic, reply)

    resp = _mark(client, topic, other)

    assert resp.status_code == 200
    assert resp.data["solved_post_id"] == other.id
    topic.refresh_from_db()
    assert topic.solved_post_id == other.id


@pytest.mark.django_db
def test_idempotency_key_replays_instead_of_reprocessing():
    topic, reply, asker, _ = _thread("idem")
    client = APIClient()
    client.force_authenticate(asker)

    first = _mark_with_key(client, topic, reply, "k1")
    second = _mark_with_key(client, topic, reply, "k1")

    assert first.status_code == second.status_code == 200
    assert first.data == second.data


@pytest.mark.django_db
def test_reusing_an_idempotency_key_with_a_different_body_is_422():
    topic, reply, asker, answerer = _thread("idem-clash")
    other = Post.objects.create(topic=topic, author=answerer, live=True)
    client = APIClient()
    client.force_authenticate(asker)
    _mark_with_key(client, topic, reply, "k2")

    resp = _mark_with_key(client, topic, other, "k2")

    assert resp.status_code == 422


def _mark_with_key(client, topic, post, key):
    return client.post(
        f"/forum/topics/{topic.id}/solution/",
        {"post_id": post.id},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


# --- The clearing rule (spec: "no dangling Solved badge pointing at a hidden
# post"). Two distinct code paths — unpublish leaves the row in place, so the
# FK's SET_NULL never fires; delete removes it, so `solved_at` is the field at
# risk. Both are pinned.


@pytest.mark.django_db
def test_unpublishing_the_accepted_post_clears_the_solved_state():
    topic, reply, asker, _ = _thread("unpub")
    client = APIClient()
    client.force_authenticate(asker)
    _mark(client, topic, reply)

    reply.unpublish()

    topic.refresh_from_db()
    assert topic.solved_post_id is None
    assert topic.solved_at is None


@pytest.mark.django_db
def test_deleting_the_accepted_post_clears_both_solved_fields():
    topic, reply, asker, _ = _thread("del")
    client = APIClient()
    client.force_authenticate(asker)
    _mark(client, topic, reply)

    reply.delete()

    topic.refresh_from_db()
    assert topic.solved_post_id is None
    # SET_NULL alone would leave this populated — a topic "solved at 14:03"
    # with no answer.
    assert topic.solved_at is None


@pytest.mark.django_db
def test_unpublishing_an_unrelated_post_leaves_the_solved_state_alone():
    topic, reply, asker, answerer = _thread("unrelated")
    bystander_post = Post.objects.create(topic=topic, author=answerer, live=True)
    client = APIClient()
    client.force_authenticate(asker)
    _mark(client, topic, reply)

    bystander_post.unpublish()

    topic.refresh_from_db()
    assert topic.solved_post_id == reply.id


# --- Serializer exposure


@pytest.mark.django_db
def test_topic_detail_exposes_the_solved_fields_and_the_affordance():
    topic, reply, asker, answerer = _thread("detail")
    client = APIClient()
    client.force_authenticate(asker)
    _mark(client, topic, reply)

    resp = client.get(f"/forum/topics/{topic.id}/")

    assert resp.status_code == 200
    assert resp.data["is_solved"] is True
    assert resp.data["solved_post_id"] == reply.id
    assert resp.data["solved_at"] is not None
    assert resp.data["can_mark_solution"] is True

    # The answerer is neither the topic author nor a moderator.
    other = APIClient()
    other.force_authenticate(answerer)
    assert other.get(f"/forum/topics/{topic.id}/").data["can_mark_solution"] is False


@pytest.mark.django_db
def test_topic_detail_reports_unsolved_for_a_fresh_topic():
    topic, _, asker, _ = _thread("fresh")
    client = APIClient()
    client.force_authenticate(asker)

    resp = client.get(f"/forum/topics/{topic.id}/")

    assert resp.data["is_solved"] is False
    assert resp.data["solved_post_id"] is None
    assert resp.data["solved_at"] is None


@pytest.mark.django_db
def test_topic_list_exposes_the_solved_badge_fields():
    topic, reply, asker, _ = _thread("list")
    client = APIClient()
    client.force_authenticate(asker)
    _mark(client, topic, reply)

    resp = client.get(f"/forum/boards/{topic.board.slug}/topics/")

    assert resp.status_code == 200
    row = next(r for r in resp.data["results"] if r["id"] == topic.id)
    assert row["is_solved"] is True
    assert row["solved_post_id"] == reply.id


@pytest.mark.django_db
def test_anonymous_readers_see_the_solved_badge_but_no_affordance():
    topic, reply, asker, _ = _thread("anon-read")
    owner = APIClient()
    owner.force_authenticate(asker)
    _mark(owner, topic, reply)

    resp = APIClient().get(f"/forum/topics/{topic.id}/")

    assert resp.data["is_solved"] is True
    assert resp.data["can_mark_solution"] is False
