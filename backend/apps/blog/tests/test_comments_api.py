"""Blog comment protection (todo 352): spam + trust gating, rate limits that
return 429, parent/depth rules, own-pending visibility, and the closed
generic write surface."""

from datetime import date

import pytest
from apps.blog.models import BlogComment, BlogIndexPage, BlogPostPage
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from freezegun import freeze_time
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumProfile, TrustLevel
from wagtail_forum.spam.base import SpamBackend, SpamResult

User = get_user_model()
BASE = "/api/v1/blog"


def _post(author, *, allow_comments=True, slug="commentable"):
    root = Page.objects.get(id=1)
    index = BlogIndexPage.objects.filter(slug="blog").first()
    if index is None:
        index = BlogIndexPage(title="Blog", slug="blog")
        root.add_child(instance=index)
    post = BlogPostPage(
        title="Commentable post",
        slug=slug,
        author=author,
        publish_date=date.today(),
        introduction="<p>Intro.</p>",
        content_blocks=[("paragraph", "<p>Body.</p>")],
        meta_description="meta",
        allow_comments=allow_comments,
    )
    index.add_child(instance=post)
    post.save_revision().publish()
    return post


def _member(username, trust=TrustLevel.MEMBER, **kwargs):
    user = User.objects.create_user(username=username, **kwargs)
    profile = ForumProfile.for_user(user)
    profile.trust_level = trust
    profile.save(update_fields=["trust_level"])
    return user


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


class _AlwaysSpam(SpamBackend):
    def check(self, obj):
        return SpamResult(is_clean=False, reason="Too many links")


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


@pytest.mark.django_db
def test_trusted_member_comment_is_approved_and_public():
    author = _member("bp-author")
    post = _post(author)
    trusted = _member("bp-trusted", TrustLevel.MEMBER)

    resp = _client(trusted).post(
        f"{BASE}/posts/{post.pk}/add_comment/", {"content": "Nice read"}
    )

    assert resp.status_code == 201, resp.data
    assert resp.data["is_approved"] is True
    assert resp.data["author"]["username"] == "bp-trusted"
    listing = _client().get(f"{BASE}/posts/{post.pk}/comments/")
    assert [c["content"] for c in listing.data] == ["Nice read"]


@pytest.mark.django_db
def test_low_trust_comment_is_held_visible_to_its_author_only():
    author = _member("bp-author2")
    post = _post(author)
    newbie = _member("bp-new", TrustLevel.NEW)

    resp = _client(newbie).post(
        f"{BASE}/posts/{post.pk}/add_comment/", {"content": "First!"}
    )

    assert resp.status_code == 201
    assert resp.data["is_approved"] is False  # pending
    assert BlogComment.objects.get().is_approved is False
    assert (
        _client().get(f"{BASE}/posts/{post.pk}/comments/").data == []
    )  # public: hidden
    other = _member("bp-other", TrustLevel.MEMBER)
    assert _client(other).get(f"{BASE}/posts/{post.pk}/comments/").data == []
    mine = _client(newbie).get(f"{BASE}/posts/{post.pk}/comments/").data
    assert [(c["content"], c["is_approved"]) for c in mine] == [("First!", False)]
    # The generic (paginated) list hides it from non-staff too; staff see it.
    assert _client(other).get(f"{BASE}/comments/").data["results"] == []
    staff = User.objects.create_user(username="bp-staff", is_staff=True)
    staff_rows = _client(staff).get(f"{BASE}/comments/").data["results"]
    assert [c["content"] for c in staff_rows] == ["First!"]


class _CountingSpam(SpamBackend):
    calls = 0

    def check(self, obj):
        _CountingSpam.calls += 1
        return SpamResult(is_clean=False, reason="Too many links")


@pytest.mark.django_db
@override_settings(
    WAGTAILFORUM_SPAM_BACKEND="apps.blog.tests.test_comments_api._CountingSpam"
)
def test_spam_flagged_text_is_held_for_a_trusted_member_and_never_screened_below_trust():
    """Trust is checked FIRST: a below-threshold comment is held without a
    (possibly billable) backend call; at/above it the backend decides."""
    _CountingSpam.calls = 0
    author = _member("bp-author3")
    post = _post(author)
    trusted = _member("bp-trusted3", TrustLevel.LEADER)
    newbie = _member("bp-new3", TrustLevel.NEW)

    held = _client(newbie).post(
        f"{BASE}/posts/{post.pk}/add_comment/", {"content": "hello"}
    )
    assert held.status_code == 201 and held.data["is_approved"] is False
    assert _CountingSpam.calls == 0  # outcome was fixed — no backend call

    resp = _client(trusted).post(
        f"{BASE}/posts/{post.pk}/add_comment/", {"content": "buy now"}
    )
    assert resp.status_code == 201
    assert resp.data["is_approved"] is False
    assert _CountingSpam.calls == 1


@pytest.mark.django_db
def test_staff_comments_skip_the_gates():
    author = _member("bp-author4")
    post = _post(author)
    staff = User.objects.create_user(username="bp-staff4", is_staff=True)
    with override_settings(
        WAGTAILFORUM_SPAM_BACKEND="apps.blog.tests.test_comments_api._AlwaysSpam"
    ):
        resp = _client(staff).post(
            f"{BASE}/posts/{post.pk}/add_comment/", {"content": "ok"}
        )
    assert resp.status_code == 201 and resp.data["is_approved"] is True


@pytest.mark.django_db
@override_settings(BLOG_COMMENT_AUTO_APPROVE_TRUST_LEVEL=TrustLevel.LEADER)
def test_auto_approve_threshold_is_a_setting():
    author = _member("bp-author5")
    post = _post(author)
    member = _member("bp-member5", TrustLevel.MEMBER)
    resp = _client(member).post(
        f"{BASE}/posts/{post.pk}/add_comment/", {"content": "hi"}
    )
    assert resp.status_code == 201 and resp.data["is_approved"] is False


@pytest.mark.django_db
@override_settings(BLOG_RATELIMITS={"comment_create": "2/h"})
def test_comment_create_is_rate_limited_with_429_not_403():
    author = _member("bp-author6")
    post = _post(author)
    member = _member("bp-member6")
    client = _client(member)
    with freeze_time("2026-06-10 12:00:00"):
        for i in range(2):
            assert (
                client.post(
                    f"{BASE}/posts/{post.pk}/add_comment/", {"content": f"c{i}"}
                ).status_code
                == 201
            )
        resp = client.post(f"{BASE}/posts/{post.pk}/add_comment/", {"content": "c3"})
    assert resp.status_code == 429
    assert resp["Retry-After"]
    assert BlogComment.objects.count() == 2


@pytest.mark.django_db
def test_comments_disabled_is_403_for_read_and_write():
    author = _member("bp-author7")
    post = _post(author, allow_comments=False, slug="no-comments")
    member = _member("bp-member7")
    assert (
        _client(member)
        .post(f"{BASE}/posts/{post.pk}/add_comment/", {"content": "x"})
        .status_code
        == 403
    )
    assert _client().get(f"{BASE}/posts/{post.pk}/comments/").status_code == 403
    assert not BlogComment.objects.exists()


@pytest.mark.django_db
def test_anonymous_cannot_comment_and_empty_content_is_400():
    author = _member("bp-author8")
    post = _post(author)
    assert (
        _client()
        .post(f"{BASE}/posts/{post.pk}/add_comment/", {"content": "x"})
        .status_code
        == 401
    )
    member = _member("bp-member8")
    assert (
        _client(member)
        .post(f"{BASE}/posts/{post.pk}/add_comment/", {"content": "  "})
        .status_code
        == 400
    )


@pytest.mark.django_db
def test_replies_are_one_level_deep_and_bound_to_the_post():
    author = _member("bp-author9")
    post = _post(author)
    other_post = _post(author, slug="other-post")
    member = _member("bp-member9")
    newbie = _member("bp-new9", TrustLevel.NEW)
    client = _client(member)
    top = client.post(f"{BASE}/posts/{post.pk}/add_comment/", {"content": "top"}).data
    reply = client.post(
        f"{BASE}/posts/{post.pk}/add_comment/",
        {"content": "reply", "parent": top["id"]},
    )
    assert (
        reply.status_code == 201
        and reply.data["parent"] == top["id"]
        and reply.data["is_reply"] is True
    )

    # Depth cap: a reply to a reply is refused.
    nested = client.post(
        f"{BASE}/posts/{post.pk}/add_comment/",
        {"content": "deep", "parent": reply.data["id"]},
    )
    assert nested.status_code == 400 and "one level" in str(nested.data)
    # Cross-post, nonexistent and ANOTHER member's pending parent all get the
    # same generic error — the endpoint is not an id oracle.
    foreign = client.post(
        f"{BASE}/posts/{other_post.pk}/add_comment/",
        {"content": "x", "parent": top["id"]},
    )
    assert foreign.status_code == 400 and "not on this post" in str(foreign.data)
    missing = client.post(
        f"{BASE}/posts/{post.pk}/add_comment/", {"content": "x", "parent": 999999}
    )
    assert missing.status_code == 400 and "not on this post" in str(missing.data)
    pending = (
        _client(newbie)
        .post(f"{BASE}/posts/{post.pk}/add_comment/", {"content": "pending"})
        .data
    )
    assert pending["is_approved"] is False
    others_pending = client.post(
        f"{BASE}/posts/{post.pk}/add_comment/",
        {"content": "x", "parent": pending["id"]},
    )
    assert others_pending.status_code == 400 and "not on this post" in str(
        others_pending.data
    )
    # The author's OWN pending comment is visible to them but not repliable yet.
    own_pending = _client(newbie).post(
        f"{BASE}/posts/{post.pk}/add_comment/",
        {"content": "x", "parent": pending["id"]},
    )
    assert own_pending.status_code == 400 and "awaiting moderation" in str(
        own_pending.data
    )
    # The body can no longer retarget `post`.
    listing = _client().get(f"{BASE}/posts/{post.pk}/comments/").data
    assert [c["content"] for c in listing] == ["top"]
    assert [r["content"] for r in listing[0]["replies"]] == ["reply"]
    assert listing[0]["replies"][0]["replies"] == []


@pytest.mark.django_db
def test_own_pending_reply_is_visible_to_its_author_in_the_thread():
    author = _member("bp-author10")
    post = _post(author)
    member = _member("bp-member10")
    newbie = _member("bp-new10", TrustLevel.NEW)
    top = (
        _client(member)
        .post(f"{BASE}/posts/{post.pk}/add_comment/", {"content": "top"})
        .data
    )
    _client(newbie).post(
        f"{BASE}/posts/{post.pk}/add_comment/", {"content": "mine", "parent": top["id"]}
    )

    public = _client().get(f"{BASE}/posts/{post.pk}/comments/").data
    assert public[0]["replies"] == []
    mine = _client(newbie).get(f"{BASE}/posts/{post.pk}/comments/").data
    assert [(r["content"], r["is_approved"]) for r in mine[0]["replies"]] == [
        ("mine", False)
    ]


@pytest.mark.django_db
def test_generic_comment_writes_are_closed():
    """The ModelViewSet's POST/PUT/DELETE bypassed every gate — now 405."""
    author = _member("bp-author11")
    post = _post(author)
    member = _member("bp-member11")
    client = _client(member)
    assert (
        client.post(f"{BASE}/comments/", {"content": "x", "post": post.pk}).status_code
        == 405
    )
    top = client.post(f"{BASE}/posts/{post.pk}/add_comment/", {"content": "top"}).data
    assert (
        client.patch(f"{BASE}/comments/{top['id']}/", {"content": "edited"}).status_code
        == 405
    )
    assert client.delete(f"{BASE}/comments/{top['id']}/").status_code == 405


@pytest.mark.django_db
@override_settings(BLOG_RATELIMITS={"comment_flag": "2/h"})
def test_flag_is_deduped_per_user_rate_limited_and_never_self():
    author = _member("bp-author12")
    post = _post(author)
    poster = _member("bp-poster12")
    flagger = _member("bp-flagger12")
    top = (
        _client(poster)
        .post(f"{BASE}/posts/{post.pk}/add_comment/", {"content": "top"})
        .data
    )

    assert (
        _client(poster).post(f"{BASE}/comments/{top['id']}/flag/").status_code == 400
    )  # own
    client = _client(flagger)
    with freeze_time("2026-06-10 12:00:00"):
        assert client.post(f"{BASE}/comments/{top['id']}/flag/").status_code == 200
        assert (
            client.post(f"{BASE}/comments/{top['id']}/flag/").status_code == 200
        )  # deduped
        resp = client.post(f"{BASE}/comments/{top['id']}/flag/")
    assert resp.status_code == 429
    assert BlogComment.objects.get(pk=top["id"]).flag_count == 1


@pytest.mark.django_db
def test_unpublished_and_restricted_posts_are_404_for_comments():
    from wagtail.models import PageViewRestriction

    author = _member("bp-author13")
    member = _member("bp-member13")
    draft = _post(author, slug="draft-post")
    draft.unpublish()
    restricted = _post(author, slug="restricted-post")
    PageViewRestriction.objects.create(page=restricted, restriction_type="login")
    client = _client(member)
    for post in (draft, restricted):
        assert (
            client.post(
                f"{BASE}/posts/{post.pk}/add_comment/", {"content": "x"}
            ).status_code
            == 404
        )
        assert client.get(f"{BASE}/posts/{post.pk}/comments/").status_code == 404
    assert not BlogComment.objects.exists()


@pytest.mark.django_db
def test_five_distinct_flags_auto_flag_the_comment():
    from apps.blog.constants import COMMENT_AUTO_FLAG_THRESHOLD

    author = _member("bp-author14")
    post = _post(author)
    poster = _member("bp-poster14")
    top = (
        _client(poster)
        .post(f"{BASE}/posts/{post.pk}/add_comment/", {"content": "top"})
        .data
    )
    for i in range(COMMENT_AUTO_FLAG_THRESHOLD - 1):
        assert (
            _client(_member(f"bp-flag14-{i}"))
            .post(f"{BASE}/comments/{top['id']}/flag/")
            .status_code
            == 200
        )
    comment = BlogComment.objects.get(pk=top["id"])
    assert (
        comment.flag_count == COMMENT_AUTO_FLAG_THRESHOLD - 1
        and comment.is_flagged is False
    )

    _client(_member("bp-flag14-last")).post(f"{BASE}/comments/{top['id']}/flag/")

    comment.refresh_from_db()
    assert (
        comment.flag_count == COMMENT_AUTO_FLAG_THRESHOLD and comment.is_flagged is True
    )
    # …and it is pulled from public view into the pending queue.
    assert comment.is_approved is False
    assert _client().get(f"{BASE}/posts/{post.pk}/comments/").data == []


@pytest.mark.django_db
def test_comment_listings_query_counts_are_flat_in_replies():
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    author = _member("bp-author15")
    post = _post(author)
    member = _member("bp-member15")
    client = _client(member)
    for i in range(3):
        top = client.post(
            f"{BASE}/posts/{post.pk}/add_comment/", {"content": f"top {i}"}
        ).data
        for j in range(2):
            client.post(
                f"{BASE}/posts/{post.pk}/add_comment/",
                {"content": f"reply {i}.{j}", "parent": top["id"]},
            )

    anon = _client()
    with CaptureQueriesContext(connection) as ctx:
        resp = anon.get(f"{BASE}/posts/{post.pk}/comments/")
    assert len(resp.data) == 3 and all(len(c["replies"]) == 2 for c in resp.data)
    per_post = [q["sql"][:70] for q in ctx.captured_queries]

    with CaptureQueriesContext(connection) as ctx2:
        listing = anon.get(f"{BASE}/comments/")
    assert len(listing.data["results"]) == 9
    generic = [q["sql"][:70] for q in ctx2.captured_queries]
    # Flat in the number of comments. Per-post route: page view-restriction +
    # specific page (twice: get_object + the serializer's post) + top-level
    # comments + ONE reply prefetch. Generic route: COUNT + page + ONE reply
    # prefetch. A per-comment reply or parent query would add 3+ here.
    assert len(per_post) == 7, per_post
    assert len(generic) == 3, generic
    assert sum("blog_blogcomment" in q for q in per_post) == 2, per_post
    assert sum("blog_blogcomment" in q for q in generic) == 3, generic
