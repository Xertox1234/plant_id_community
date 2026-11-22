"""Blog authors never show a member's legal name (todo 731).

Sign in with Apple, Google or Firebase copies the provider's name into
``first_name``/``last_name``. Blog comments and bylines reach anonymous
readers, so every public author payload follows the forum rule (owner
decisions 2026-11-21 and 2026-11-22): the chosen (forum) display name, else
the username, never ``get_full_name()``, and no ``first_name``/``last_name``.
"""

import json
from datetime import date

import pytest
from apps.blog.models import BlogComment, BlogIndexPage, BlogPostPage
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumProfile

User = get_user_model()
V1 = "/api/v1/blog"
V2 = "/api/v2/blog-posts"

FIRST, LAST = "Juniper", "Applewhite"
FULL_NAME = f"{FIRST} {LAST}"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def _named_user(username, forum_name=""):
    user = User.objects.create_user(username=username, first_name=FIRST, last_name=LAST)
    assert user.get_full_name() == FULL_NAME
    if forum_name:
        profile = ForumProfile.for_user(user)
        profile.display_name = forum_name
        profile.save(update_fields=["display_name"])
    return user


def _post(author, slug="privacy-post"):
    root = Page.objects.get(id=1)
    index = BlogIndexPage.objects.filter(slug="blog").first()
    if index is None:
        index = BlogIndexPage(title="Blog", slug="blog")
        root.add_child(instance=index)
    post = BlogPostPage(
        title="Privacy post",
        slug=slug,
        author=author,
        publish_date=date.today(),
        introduction="<p>Intro.</p>",
        content_blocks=[("paragraph", "<p>Body.</p>")],
        meta_description="meta",
        allow_comments=True,
    )
    index.add_child(instance=post)
    post.save_revision().publish()
    return post


def _authors(payload):
    """Every dict under an ``author`` key, at any depth."""
    found = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "author" and isinstance(value, dict):
                found.append(value)
            found.extend(_authors(value))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(_authors(item))
    return found


def _assert_no_legal_name(response, expected_names):
    assert response.status_code == 200, response.content
    body = response.content.decode()
    assert FULL_NAME not in body
    assert FIRST not in body
    assert LAST not in body
    authors = _authors(json.loads(body))
    assert authors, "no author payload in the response"
    for author in authors:
        assert "first_name" not in author
        assert "last_name" not in author
        assert author["display_name"] in expected_names
        assert author["display_name"] != FULL_NAME


@pytest.mark.django_db
def test_anonymous_comment_listing_never_shows_a_legal_name():
    staff = _named_user("staff-writer")
    post = _post(staff)
    commenter = _named_user("fern-fan")
    replier = _named_user("moss-maker", forum_name="Moss Maker")
    parent = BlogComment.objects.create(
        post=post, author=commenter, content="Lovely", is_approved=True
    )
    BlogComment.objects.create(
        post=post, author=replier, content="Agreed", parent=parent, is_approved=True
    )
    anon = APIClient()

    for url in (f"{V1}/comments/", f"{V1}/posts/{post.pk}/comments/"):
        resp = anon.get(url)
        _assert_no_legal_name(resp, {"fern-fan", "Moss Maker"})

    listing = anon.get(f"{V1}/posts/{post.pk}/comments/").json()
    top = listing[0]
    assert top["author"]["display_name"] == "fern-fan"  # no forum name: username
    assert top["replies"][0]["author"]["display_name"] == "Moss Maker"  # chosen


@pytest.mark.django_db
def test_v1_post_bylines_never_show_a_legal_name():
    staff = _named_user("staff-writer")
    post = _post(staff)
    anon = APIClient()

    _assert_no_legal_name(anon.get(f"{V1}/posts/"), {"staff-writer"})
    _assert_no_legal_name(anon.get(f"{V1}/posts/{post.pk}/"), {"staff-writer"})


@pytest.mark.django_db
def test_v2_post_bylines_use_the_chosen_name_never_the_legal_name():
    staff = _named_user("staff-writer", forum_name="The Plant Desk")
    post = _post(staff)
    anon = APIClient()

    _assert_no_legal_name(anon.get(f"{V2}/"), {"The Plant Desk"})
    _assert_no_legal_name(anon.get(f"{V2}/{post.pk}/"), {"The Plant Desk"})


@pytest.mark.django_db
def test_public_name_rule():
    plain = _named_user("plain-user")
    chosen = _named_user("chosen-user", forum_name="Chosen")
    assert plain.public_name == "plain-user"
    assert chosen.public_name == "Chosen"
    # The member's own profile name is unchanged.
    assert plain.display_name == FULL_NAME
