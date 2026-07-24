import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _topic_with_posts(n):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="ada")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    for i in range(n):
        Post.objects.create(
            topic=topic,
            author=author,
            is_opening_post=(i == 0),
            live=True,
            body=[{"type": "paragraph", "value": "<p>hi</p>"}],
        )
    return topic


@pytest.mark.django_db
def test_post_list_serializes_streamfield_body():
    topic = _topic_with_posts(1)
    resp = APIClient().get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    post = resp.data["results"][0]
    assert post["topic_id"] == topic.id
    assert post["author"]["username"] == "ada"
    assert post["is_opening_post"] is True
    assert post["body"] == [
        {"type": "paragraph", "value": "<p>hi</p>", "id": post["body"][0]["id"]}
    ]
    assert post["reaction_counts"] == {}
    assert post["can_edit"] is False  # anonymous


@pytest.mark.django_db
def test_post_list_ordering_query_param_is_inert():
    # Phase 6 review (2026-07-11 audit): PostListView.list() calls
    # filter_queryset(), so the host's global OrderingFilter let ?ordering=
    # reverse the reading order. filter_backends=[] pins oldest-first as a
    # package contract (see the full rationale on BoardListView).
    topic = _topic_with_posts(3)
    client = APIClient()

    default_ids = [
        p["id"] for p in client.get(f"/forum/topics/{topic.id}/posts/").data["results"]
    ]
    resp = client.get(f"/forum/topics/{topic.id}/posts/", {"ordering": "-created_at"})

    assert resp.status_code == 200
    assert [p["id"] for p in resp.data["results"]] == default_ids  # param ignored


@pytest.mark.django_db
def test_post_list_is_cursor_paginated_with_bounded_queries():
    topic = _topic_with_posts(25)
    client = APIClient()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 20  # page_size
    assert resp.data["next"] is not None
    # Q1: PageViewRestriction prefetch (from _visible_boards().public())
    # Q2: topic lookup (wagtail_forum_topic with board__in=_visible_boards() subquery)
    # Q3: posts page with select_related author (cursor fetches page_size+1 rows; the
    #     extra row is the has-next probe — no separate COUNT query)
    # Pinned EXACTLY (docs/rules/testing.md). If this changes, explain the new number.
    assert len(ctx.captured_queries) == 3


def _topic_with_image_posts(n):
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.collections import get_forum_image_collection

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="ada")
    collection = get_forum_image_collection()
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    for i in range(n):
        image = get_image_model().objects.create(
            title=f"img{i}", file=get_test_image_file(), collection=collection
        )
        Post.objects.create(
            topic=topic,
            author=author,
            is_opening_post=(i == 0),
            live=True,
            body=[
                {"type": "paragraph", "value": "<p>hi</p>"},
                {"type": "image", "value": image.id},
            ],
        )
    return topic


@pytest.mark.django_db
def test_post_list_serializes_image_blocks_to_renditions():
    topic = _topic_with_image_posts(1)
    resp = APIClient().get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    blocks = resp.data["results"][0]["body"]
    assert [b["type"] for b in blocks] == ["paragraph", "image"]
    image_value = blocks[1]["value"]
    assert set(image_value) == {"id", "url", "alt", "width", "height"}
    assert image_value["alt"] == "img0"
    assert image_value["url"].startswith("http://testserver")  # absolute, cross-origin
    assert image_value["width"] > 0 and image_value["height"] > 0


@pytest.mark.django_db
def test_post_list_with_images_is_not_n_plus_one():
    topic = _topic_with_image_posts(3)
    client = APIClient()
    # Warm renditions (generated once, then cached) so the pin measures the
    # production steady state, not first-render rendition generation.
    assert client.get(f"/forum/topics/{topic.id}/posts/").status_code == 200
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    # 3 base queries (Q1 visibility prefetch, Q2 topic lookup, Q3 posts page) +
    # the batched image fetch + its prefetched renditions — FLAT regardless of
    # how many image blocks the page carries (two-pass batching, no N+1).
    # Pinned EXACTLY (docs/rules/testing.md); explain any change to this number.
    assert len(ctx.captured_queries) == 5


@pytest.mark.django_db
def test_post_list_hides_posts_on_hidden_topic():
    topic = _topic_with_posts(1)
    topic.live = False
    topic.save()
    assert APIClient().get(f"/forum/topics/{topic.id}/posts/").status_code == 404


def _moderator(username):
    from django.contrib.auth.models import Permission

    user = User.objects.create_user(username=username)
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="wagtail_forum", codename="change_post"
        )
    )
    return User.objects.get(pk=user.pk)  # re-fetch to clear the permission cache


@pytest.mark.django_db
def test_author_affordances_reflect_write_rules():
    # Affordance parity (todo 252): the opening post is not deletable (DELETE
    # 409), so its author sees can_delete=false while a reply stays true; both
    # stay editable in an open topic.
    topic = _topic_with_posts(2)  # post 0 = opening, post 1 = reply
    author = User.objects.get(username="ada")
    client = APIClient()
    client.force_authenticate(author)
    resp = client.get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    by_opening = {p["is_opening_post"]: p for p in resp.data["results"]}
    assert by_opening[True]["can_edit"] is True
    assert by_opening[True]["can_delete"] is False  # opening post: not deletable
    assert by_opening[False]["can_edit"] is True
    assert by_opening[False]["can_delete"] is True  # reply: deletable


@pytest.mark.django_db
def test_author_can_edit_false_in_closed_topic():
    # Operand isolation: is_closed=True alone (topic.locked stays False). A frozen
    # topic makes the author's edit 409, so can_edit/can_delete must both be false.
    topic = _topic_with_posts(2)
    Topic.objects.filter(id=topic.id).update(is_closed=True)
    author = User.objects.get(username="ada")
    client = APIClient()
    client.force_authenticate(author)
    resp = client.get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    for p in resp.data["results"]:
        assert p["can_edit"] is False
        assert p["can_delete"] is False


@pytest.mark.django_db
def test_author_can_edit_false_in_locked_topic():
    # Operand isolation: topic.locked=True alone (is_closed stays False).
    topic = _topic_with_posts(2)
    Topic.objects.filter(id=topic.id).update(locked=True)
    author = User.objects.get(username="ada")
    client = APIClient()
    client.force_authenticate(author)
    resp = client.get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    for p in resp.data["results"]:
        assert p["can_edit"] is False


@pytest.mark.django_db
def test_moderator_affordance_bypasses_post_lock():
    # A moderator bypasses the per-post lock (Wagtail privileged-user semantics),
    # so they see can_edit=true on a locked post where the author sees false —
    # the affordance carries the same bypass as the write path.
    topic = _topic_with_posts(2)
    Post.objects.filter(topic=topic).update(locked=True)
    author = User.objects.get(username="ada")
    mod = _moderator("mod")

    author_client = APIClient()
    author_client.force_authenticate(author)
    author_resp = author_client.get(f"/forum/topics/{topic.id}/posts/")
    assert len(author_resp.data["results"]) == 2
    assert all(p["can_edit"] is False for p in author_resp.data["results"])

    mod_client = APIClient()
    mod_client.force_authenticate(mod)
    mod_resp = mod_client.get(f"/forum/topics/{topic.id}/posts/")
    assert all(p["can_edit"] is True for p in mod_resp.data["results"])


@pytest.mark.django_db
def test_post_list_affordances_add_no_per_post_queries():
    # The shared can_edit/can_delete predicate reads obj.topic; select_related
    # ("topic") folds that into the posts query, so the authenticated count stays
    # FLAT as posts grow — no N+1 from the affordance flags (todo 252). The author
    # path never calls has_perm (owner short-circuit). Pinned EXACTLY; explain any
    # change to this number (docs/rules/testing.md).
    topic = _topic_with_posts(20)  # one full page
    author = User.objects.get(username="ada")
    client = APIClient()
    client.force_authenticate(author)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 20
    # Q1 visibility prefetch, Q2 topic lookup, Q3 posts page (select_related
    # author+topic). Same 3 as the anonymous pin — the predicate adds no query.
    assert len(ctx.captured_queries) == 3


@pytest.mark.django_db
def test_post_list_author_carries_trust_level_and_display_name():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="ada")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>hi</p>"}],
    )
    # Set profile fields AFTER the post exists so the post-save trust signal
    # (which recomputes trust_level from post_count) has already run and won't
    # clobber these values. REGULAR (3) is unreachable from 1 post, proving the
    # serializer reads the stored profile, not a recomputed level.
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.collections import get_forum_image_collection

    avatar = get_image_model().objects.create(
        title="ada-avatar",
        file=get_test_image_file(),
        collection=get_forum_image_collection(),
        uploaded_by_user=author,
    )
    profile = ForumProfile.for_user(author)
    profile.trust_level = TrustLevel.REGULAR  # 3
    profile.display_name = "Ada L."
    profile.avatar = avatar
    profile.save(update_fields=["trust_level", "display_name", "avatar"])

    resp = APIClient().get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    got = resp.data["results"][0]["author"]
    assert got["username"] == "ada"
    assert got["display_name"] == "Ada L."
    assert got["trust_level"] == 3
    # The avatar serializes as the ABSOLUTE image file URL (todo 257 slice A) —
    # not just non-null, so the feature deliverable "avatar rendered on posts"
    # is actually proven, not merely query-pinned.
    assert got["avatar"] == f"http://testserver{avatar.file.url}"


@pytest.mark.django_db
def test_post_list_author_profiles_add_no_per_post_queries():
    # 20 posts by 20 DISTINCT authors, each with their own ForumProfile — the
    # worst case for an author-profile N+1. select_related folds every profile
    # into the single posts SELECT, so the count stays the pinned 3.
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    starter = User.objects.create_user(username="starter")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=starter, live=True
    )
    for i in range(20):
        u = User.objects.create_user(username=f"u{i}")
        Post.objects.create(
            topic=topic,
            author=u,
            is_opening_post=(i == 0),
            live=True,
            body=[{"type": "paragraph", "value": "<p>hi</p>"}],
        )
    client = APIClient()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 20
    # Pinned EXACTLY (docs/rules/testing.md): Q1 visibility prefetch, Q2 topic
    # lookup, Q3 posts page (author + author profile + topic all select_related).
    assert len(ctx.captured_queries) == 3


@pytest.mark.django_db
def test_post_list_author_without_profile_still_renders():
    # A reverse OneToOne select_related is a LEFT OUTER JOIN, so a post whose
    # author has no ForumProfile row must NOT be dropped from the results.
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="ghost")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>hi</p>"}],
    )
    ForumProfile.objects.filter(user=author).delete()  # purge any signal-created row

    resp = APIClient().get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    results = resp.data["results"]
    assert len(results) == 1  # row not dropped
    assert results[0]["author"]["username"] == "ghost"
    assert results[0]["author"]["trust_level"] is None
    assert results[0]["author"]["display_name"] == "ghost"  # username fallback
    assert results[0]["author"]["avatar"] is None  # no profile → no avatar
