"""Post edit-history endpoints (todo 282 / audit M4).

Every edit already writes a `wagtailcore.Revision`; these two endpoints expose
what was already being stored. The interesting surface is not the happy path —
it is the privacy gate, because a revision is a verbatim snapshot of a body
that may since have been redacted.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.api.serializers import build_forum_image_map, serialize_forum_body
from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


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


def _post_with_history(slug, author, *, editors=()):
    """A live post plus one revision per entry in *editors* (None = the author)."""
    board = _board(slug)
    topic = Topic.objects.create(
        board=board, title="T", slug=f"t-{slug}", author=author, live=True
    )
    post = Post.objects.create(
        topic=topic, author=author, is_opening_post=True, live=True
    )
    post.save_revision(user=author)
    for editor in editors:
        post.save_revision(user=editor if editor is not None else author)
    return post


@pytest.mark.django_db
def test_revision_list_is_readable_by_the_author():
    author = User.objects.create_user(username="rev-author")
    post = _post_with_history("rev-a", author, editors=[None])

    client = APIClient()
    client.force_authenticate(author)
    resp = client.get(f"/forum/posts/{post.id}/revisions/")

    assert resp.status_code == 200
    assert len(resp.data) == 2
    # Newest first, and the identity shape is the unified author object (H26),
    # not an ad-hoc one.
    assert resp.data[0]["created_at"] >= resp.data[1]["created_at"]
    assert resp.data[0]["user"] == {
        "username": "rev-author",
        "display_name": "rev-author",
        "avatar": None,
        "trust_level": None,
    }


@pytest.mark.django_db
def test_revision_list_is_readable_by_a_moderator():
    author = User.objects.create_user(username="rev-author2")
    moderator = _moderator("rev-mod2")
    post = _post_with_history("rev-b", author, editors=[None])

    client = APIClient()
    client.force_authenticate(moderator)
    resp = client.get(f"/forum/posts/{post.id}/revisions/")

    assert resp.status_code == 200
    assert len(resp.data) == 2


@pytest.mark.django_db
def test_revision_list_is_403_for_an_unrelated_user():
    author = User.objects.create_user(username="rev-author3")
    stranger = User.objects.create_user(username="rev-stranger")
    post = _post_with_history("rev-c", author)

    client = APIClient()
    client.force_authenticate(stranger)
    assert client.get(f"/forum/posts/{post.id}/revisions/").status_code == 403


@pytest.mark.django_db
def test_revision_list_rejects_anonymous():
    author = User.objects.create_user(username="rev-author4")
    post = _post_with_history("rev-d", author)

    resp = APIClient().get(f"/forum/posts/{post.id}/revisions/")

    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_a_moderator_edit_makes_the_history_moderator_only():
    """The privacy decision, asserted.

    A moderator editing a post is the signal that something needed removing —
    and the thing removed is sitting in the revisions BEFORE that edit. So the
    author loses access to their own history once someone else has touched it,
    rather than being handed the redacted content back through a new endpoint.
    """
    author = User.objects.create_user(username="rev-author5")
    moderator = _moderator("rev-mod5")
    post = _post_with_history("rev-e", author, editors=[None])

    client = APIClient()
    client.force_authenticate(author)
    assert client.get(f"/forum/posts/{post.id}/revisions/").status_code == 200

    post.save_revision(user=moderator)  # the redaction

    assert client.get(f"/forum/posts/{post.id}/revisions/").status_code == 403
    # ...but the moderator can still audit it, which is the whole point.
    client.force_authenticate(moderator)
    assert client.get(f"/forum/posts/{post.id}/revisions/").status_code == 200


@pytest.mark.django_db
def test_an_unattributed_revision_also_locks_the_history():
    """A revision with no user cannot be shown to be the author's, so it counts
    as third-party. Conservative by design — the failure mode of guessing wrong
    is serving redacted content."""
    author = User.objects.create_user(username="rev-author6")
    post = _post_with_history("rev-f", author)
    post.save_revision(user=None)

    client = APIClient()
    client.force_authenticate(author)
    assert client.get(f"/forum/posts/{post.id}/revisions/").status_code == 403


@pytest.mark.django_db
def test_revision_detail_body_matches_the_live_body_shape():
    author = User.objects.create_user(username="rev-author7")
    board = _board("rev-g")
    topic = Topic.objects.create(
        board=board, title="T", slug="t-rev-g", author=author, live=True
    )
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[("paragraph", "<p>original</p>")],
    )
    revision = post.save_revision(user=author)

    client = APIClient()
    client.force_authenticate(author)
    resp = client.get(f"/forum/posts/{post.id}/revisions/{revision.id}/")

    assert resp.status_code == 200
    snapshot = revision.as_object()
    expected = serialize_forum_body(
        snapshot.body, image_map=build_forum_image_map([snapshot])
    )
    # Compared against serialize_forum_body's own output, not a hand-written
    # literal: the contract is "same shape as the live body", so the assertion
    # must track that function rather than a snapshot of today's output.
    assert resp.data["body"] == expected
    assert resp.data["id"] == revision.id


@pytest.mark.django_db
def test_revision_detail_404s_a_revision_from_another_post():
    """The revision id is scoped to the post in the URL — otherwise the
    per-post privacy gate is trivially bypassed by borrowing another post's
    (permitted) id."""
    author = User.objects.create_user(username="rev-author8")
    mine = _post_with_history("rev-h", author)
    other_author = User.objects.create_user(username="rev-author9")
    theirs = _post_with_history("rev-i", other_author)
    foreign_revision = theirs.revisions.first()

    client = APIClient()
    client.force_authenticate(author)
    resp = client.get(f"/forum/posts/{mine.id}/revisions/{foreign_revision.id}/")

    assert resp.status_code == 404


@pytest.mark.django_db
def test_revision_detail_is_403_for_an_unrelated_user():
    author = User.objects.create_user(username="rev-author10")
    stranger = User.objects.create_user(username="rev-stranger10")
    post = _post_with_history("rev-j", author)
    revision = post.revisions.first()

    client = APIClient()
    client.force_authenticate(stranger)
    assert (
        client.get(f"/forum/posts/{post.id}/revisions/{revision.id}/").status_code
        == 403
    )


@pytest.mark.django_db
def test_revision_list_query_count_is_flat_in_the_number_of_revisions():
    """No N+1 on the revision author.

    Pinned as a DELTA rather than an absolute, deliberately: the absolute count
    includes Django's per-user permission lookups, which are cached per user
    instance and would make the number depend on fixture order rather than on
    the endpoint. What this endpoint must guarantee is that 1 revision and 6
    cost the same, and that is exactly what the delta asserts.
    """
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file

    author = User.objects.create_user(username="rev-n1")
    profile = ForumProfile.for_user(author)
    # An avatar is load-bearing for this pin: serialize_forum_author
    # short-circuits on `avatar_id` before touching `.avatar`, so without one
    # the `__avatar` leg of the select_related chain is never traversed and
    # deleting it from the view would leave this test green.
    profile.avatar = get_image_model().objects.create(
        title="a", file=get_test_image_file()
    )
    profile.save(update_fields=["avatar"])
    post = _post_with_history("rev-k", author)

    client = APIClient()
    client.force_authenticate(author)
    client.get(f"/forum/posts/{post.id}/revisions/")  # warm the permission cache

    with CaptureQueriesContext(connection) as one:
        assert client.get(f"/forum/posts/{post.id}/revisions/").status_code == 200

    for _ in range(5):
        post.save_revision(user=author)

    with CaptureQueriesContext(connection) as many:
        resp = client.get(f"/forum/posts/{post.id}/revisions/")
    assert len(resp.data) == 6

    assert len(many.captured_queries) == len(one.captured_queries), (
        "revision-author lookup is N+1: "
        f"{len(one.captured_queries)} query(s) for 1 revision, "
        f"{len(many.captured_queries)} for 6 — "
        f"{[q['sql'] for q in many.captured_queries]}"
    )


@pytest.mark.django_db
def test_revision_detail_query_count_is_flat_in_the_number_of_images():
    """No N+1 on inline images: the detail body must batch through
    `build_forum_image_map`, exactly as the post-list path does."""
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.collections import get_forum_image_collection

    author = User.objects.create_user(username="rev-img")
    board = _board("rev-l")
    topic = Topic.objects.create(
        board=board, title="T", slug="t-rev-l", author=author, live=True
    )
    Image = get_image_model()
    collection = get_forum_image_collection()
    images = [
        Image.objects.create(
            title=f"i{n}", file=get_test_image_file(), collection=collection
        )
        for n in range(4)
    ]

    def _revision_with(image_objs):
        post = Post.objects.create(
            topic=topic,
            author=author,
            live=True,
            body=[("image", img) for img in image_objs],
        )
        return post, post.save_revision(user=author)

    one_post, one_rev = _revision_with(images[:1])
    many_post, many_rev = _revision_with(images)

    client = APIClient()
    client.force_authenticate(author)
    # Warm BOTH, not just one: Wagtail GENERATES a rendition on first access
    # (prefetch_renditions only prefetches ones that already exist), so an
    # unwarmed 4-image request pays 3 extra creations and looks exactly like an
    # N+1. Warming isolates the steady state, which is what this pins.
    client.get(f"/forum/posts/{one_post.id}/revisions/{one_rev.id}/")
    client.get(f"/forum/posts/{many_post.id}/revisions/{many_rev.id}/")

    with CaptureQueriesContext(connection) as one:
        assert (
            client.get(
                f"/forum/posts/{one_post.id}/revisions/{one_rev.id}/"
            ).status_code
            == 200
        )
    with CaptureQueriesContext(connection) as many:
        assert (
            client.get(
                f"/forum/posts/{many_post.id}/revisions/{many_rev.id}/"
            ).status_code
            == 200
        )

    assert len(many.captured_queries) == len(one.captured_queries), (
        "inline-image resolution is N+1: "
        f"{len(one.captured_queries)} query(s) for 1 image, "
        f"{len(many.captured_queries)} for 4"
    )


@pytest.mark.django_db
def test_revision_detail_resolves_image_blocks_like_the_live_body():
    """AC 3's "image blocks resolved", asserted on content rather than only on
    query count — the URLs must be ABSOLUTE, exactly as the live post body
    serializes them, or a client diffing the two sees a spurious change on
    every image."""
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.collections import get_forum_image_collection

    author = User.objects.create_user(username="rev-imgurl")
    board = _board("rev-m")
    topic = Topic.objects.create(
        board=board, title="T", slug="t-rev-m", author=author, live=True
    )
    image = get_image_model().objects.create(
        title="i", file=get_test_image_file(), collection=get_forum_image_collection()
    )
    post = Post.objects.create(
        topic=topic, author=author, live=True, body=[("image", image)]
    )
    revision = post.save_revision(user=author)

    client = APIClient()
    client.force_authenticate(author)
    resp = client.get(f"/forum/posts/{post.id}/revisions/{revision.id}/")

    assert resp.status_code == 200
    block = resp.data["body"][0]
    assert block["type"] == "image"
    assert block["value"]["url"].startswith("http://testserver"), block["value"]
    live = client.get(f"/forum/topics/{topic.id}/posts/").data["results"]
    live_block = next(
        b for p in live if p["id"] == post.id for b in p["body"] if b["type"] == "image"
    )
    assert block["value"] == live_block["value"]


@pytest.mark.django_db
def test_history_reflects_the_real_edit_path_not_just_save_revision():
    """Every other test here builds history with `save_revision()` directly.

    That is synthetic: the gate's whole premise is *who* a revision is
    attributed to, and attribution is decided by the production write path
    (PATCH -> submit_edit_for_moderation -> workflow). Drive the real endpoint
    once, so a future change that re-attributes revisions to a moderator or to
    the system cannot pass unnoticed.
    """
    author = User.objects.create_user(username="rev-e2e")
    profile = ForumProfile.for_user(author)
    profile.trust_level = 4  # autopublish, so the edit lands without moderation
    profile.save(update_fields=["trust_level"])
    board = _board("rev-n")
    topic = Topic.objects.create(
        board=board, title="T", slug="t-rev-n", author=author, live=True
    )
    post = Post.objects.create(
        topic=topic, author=author, live=True, body=[("paragraph", "<p>v1</p>")]
    )

    client = APIClient()
    client.force_authenticate(author)
    patched = client.patch(
        f"/forum/posts/{post.id}/",
        {"body": [{"type": "paragraph", "value": "<p>v2</p>"}]},
        format="json",
    )
    assert patched.status_code == 200, patched.data

    listed = client.get(f"/forum/posts/{post.id}/revisions/")
    assert listed.status_code == 200, "the author's own edit locked them out"
    assert len(listed.data) >= 1
    assert {r["user"]["username"] for r in listed.data} == {"rev-e2e"}


@pytest.mark.django_db
def test_history_of_an_account_deleted_authors_post_is_moderator_only():
    """The documented conservative edge: with `author_id is None` there is no
    author to grant access to, and only a moderator can have written a
    revision — so nobody but a moderator reads it."""
    author = User.objects.create_user(username="rev-gone")
    post = _post_with_history("rev-o", author)
    Post.objects.filter(pk=post.pk).update(author=None)

    client = APIClient()
    client.force_authenticate(author)
    assert client.get(f"/forum/posts/{post.id}/revisions/").status_code == 403

    client.force_authenticate(_moderator("rev-mod-gone"))
    assert client.get(f"/forum/posts/{post.id}/revisions/").status_code == 200


@pytest.mark.django_db
def test_revision_endpoints_inherit_the_board_visibility_guard():
    """Shared with the write endpoints, but pinned here too: a hidden board
    must 404 (no existence leak), not 403 — the privacy gate must never run
    before the visibility gate, or it leaks which posts exist."""
    author = User.objects.create_user(username="rev-hidden")
    post = _post_with_history("rev-p", author)
    revision = post.revisions.first()
    ForumBoard.objects.filter(pk=post.topic.board_id).update(live=False)

    client = APIClient()
    client.force_authenticate(author)
    assert client.get(f"/forum/posts/{post.id}/revisions/").status_code == 404
    assert (
        client.get(f"/forum/posts/{post.id}/revisions/{revision.id}/").status_code
        == 404
    )
