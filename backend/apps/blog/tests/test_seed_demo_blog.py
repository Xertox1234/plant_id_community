"""Tests for `manage.py seed_demo_blog` (Canopy PR 3, spec §5).

Page-creating (BlogIndexPage/BlogPostPage are Wagtail pages) — run locally
with --create-db on a partial re-run (backend/CLAUDE.md stale-test-DB gotcha).
"""

from datetime import timedelta

import pytest
from apps.blog.models import BlogCategory, BlogIndexPage, BlogPostPage
from apps.blog.seed_content import AUTHOR_NAMES, CATEGORIES, POSTS
from apps.forum_host.seed_content import DEMO_EMAIL_DOMAIN
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone
from wagtail.images import get_image_model
from wagtail.models import Site

User = get_user_model()

EXPECTED_COVERS = {f"Seed: {p['cover']}" for p in POSTS}


def _world_counts():
    return (
        User.objects.count(),
        BlogCategory.objects.count(),
        BlogPostPage.objects.count(),
        get_image_model().objects.count(),
    )


@override_settings(DEBUG=False)
@pytest.mark.django_db
def test_refuses_without_confirm_when_not_debug():
    with pytest.raises(CommandError, match="--confirm"):
        call_command("seed_demo_blog")


@override_settings(DEBUG=False)
@pytest.mark.django_db
def test_confirm_seeds_when_not_debug():
    call_command("seed_demo_blog", confirm=True)
    assert BlogPostPage.objects.count() == len(POSTS)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_refuses_when_real_users_exist_even_with_confirm():
    User.objects.create_user(username="alice", password="x")
    with pytest.raises(CommandError, match="real user"):
        call_command("seed_demo_blog", confirm=True)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_superuser_does_not_trip_the_guard():
    User.objects.create_superuser(
        username="admin", email="admin@example.com", password="x"
    )
    call_command("seed_demo_blog")
    assert BlogPostPage.objects.count() == len(POSTS)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_refuses_to_adopt_a_real_account_on_an_author_username():
    # Same adoption hole the forum seed closed: a real superuser sitting on a
    # demo username sails past the census (superusers are excused by design)
    # and must be refused at the per-account check, leaving nothing created.
    real_admin = User.objects.create_superuser(
        username="june_park", email="june@realcompany.com", password="x"
    )
    with pytest.raises(CommandError, match="june_park"):
        call_command("seed_demo_blog")

    real_admin.refresh_from_db()
    assert real_admin.email == "june@realcompany.com"
    assert real_admin.has_usable_password() is True
    assert real_admin.first_name == ""  # names never touched on a refusal
    assert BlogPostPage.objects.count() == 0


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_author_names_set_only_when_blank():
    # Fill-if-blank (spec §5): a demo-shaped account whose name was manually
    # customised keeps the custom name; a blank one gets the cast name.
    custom = User.objects.create_user(
        username="iris_delgado",
        email=f"iris_delgado@{DEMO_EMAIL_DOMAIN}",
        first_name="Custom",
        last_name="Name",
    )
    custom.set_unusable_password()
    custom.save()

    call_command("seed_demo_blog")

    custom.refresh_from_db()
    assert (custom.first_name, custom.last_name) == ("Custom", "Name")
    for username, (first, last) in AUTHOR_NAMES.items():
        if username == "iris_delgado":
            continue
        user = User.objects.get(username=username)
        assert (user.first_name, user.last_name) == (first, last)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_run_twice_is_idempotent():
    call_command("seed_demo_blog")
    counts_1 = _world_counts()
    published_1 = dict(BlogPostPage.objects.values_list("slug", "first_published_at"))

    call_command("seed_demo_blog")
    counts_2 = _world_counts()
    published_2 = dict(BlogPostPage.objects.values_list("slug", "first_published_at"))

    assert counts_1 == counts_2
    assert published_1 == published_2


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_reuses_an_existing_blog_index():
    site_root = Site.objects.get(is_default_site=True).root_page
    index = site_root.add_child(instance=BlogIndexPage(title="Blog", slug="blog"))
    index.save_revision().publish()

    call_command("seed_demo_blog")

    assert BlogIndexPage.objects.count() == 1
    assert BlogPostPage.objects.first().get_parent().pk == index.pk


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_world_shape():
    call_command("seed_demo_blog")

    assert BlogPostPage.objects.count() == len(POSTS)
    assert BlogCategory.objects.count() == len(CATEGORIES)

    # Routable tree (audit H1 analogue): the index must live under the Site's
    # root_page or every post URL is None and nothing is ever served.
    site_root = Site.objects.get(is_default_site=True).root_page
    index = BlogIndexPage.objects.get()
    assert index.is_descendant_of(site_root)
    assert index.get_url() is not None

    now = timezone.now()
    for spec in POSTS:
        post = BlogPostPage.objects.get(slug=spec["slug"])
        assert post.live is True
        assert post.author.username == spec["author"]
        assert [c.slug for c in post.categories.all()] == [spec["category"]]
        assert post.view_count == spec["view_count"]
        assert post.featured_image is not None
        assert post.featured_image.title == f"Seed: {spec['cover']}"
        # Back-dating (publish-fields lesson, LEARNINGS 2026-08-15): the
        # curated age must land on first/last_published_at, not just the
        # child-table publish_date.
        expected = now - timedelta(days=spec["age_days"])
        assert abs(post.first_published_at - expected) < timedelta(minutes=5)
        assert abs(post.last_published_at - expected) < timedelta(minutes=5)
        assert post.publish_date == expected.date()
        # Honesty contract: reading_time is auto-computed at save() from the
        # real body — assert PRESENCE and plausibility, not a pinned value
        # (DRF-SkipField lesson: a silently-absent value must fail loudly).
        assert post.reading_time is not None
        assert post.reading_time >= 2

    seeded_images = get_image_model().objects.filter(title__startswith="Seed: ")
    # cover-variegation / cover-fiddle names must not collide with forum
    # seed titles; in THIS suite only blog covers exist.
    assert {img.title for img in seeded_images} == EXPECTED_COVERS

    # Popular ordering is deterministic from seeded view_counts alone
    # (spec §12: the endpoint never excludes zero-view posts).
    ordered = list(
        BlogPostPage.objects.order_by("-view_count").values_list("slug", flat=True)
    )
    assert ordered == [
        "killed-by-kindness",
        "fiddle-leaf-adjusting",
        "variegation-isnt-magic",
        "spider-mites-early",
        "prune-like-you-mean-it",
        "small-space-jungle",
    ]
