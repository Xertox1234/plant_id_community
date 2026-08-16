"""Tests for `manage.py seed_demo_content` (Task 7, Canopy forum content).

Page-creating (ForumBoard/ForumIndex are Wagtail pages) — run locally with
--create-db on a partial re-run (see backend/CLAUDE.md's stale-test-DB gotcha).

Controller ruling (2026-08-15): the brief's test list says "4 topics solved"
— that is a typo. The catalogue and spec §5's table mark 5 solved topics;
`test_world_shape` asserts 5 with the spec'd solvers.
"""

from datetime import timedelta

import pytest
from apps.forum_host.management.commands.seed_default_forum import (
    DEFAULT_BOARD_SLUG as LEGACY_STARTER_SLUG,
)
from apps.forum_host.seed_content import BOARDS, DEMO_EMAIL_DOMAIN, TOPICS, USERS
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone
from wagtail.images import get_image_model
from wagtail.models import Site
from wagtail_forum.models import (
    ForumBoard,
    ForumIdentificationAttachment,
    ForumProfile,
    Post,
    Reaction,
    Topic,
)

User = get_user_model()

# Spec §5's solved-topic table (controller ruling: 5, not the brief's typo'd 4).
EXPECTED_SOLVERS = {
    "estate-sale-trailing-plant": "sam_whitaker",
    "fuzzy-leaves-purple-undersides": "june_park",
    "tree-bark-peels-like-paper": "theo_brandt",
    "pothos-yellow-halo-leaves": "june_park",
    "white-cotton-blobs-jade": "june_park",
}

# The 8 distinct seed_assets/*.webp files referenced across the catalogue
# (some, like the balcony before/after pair, appear once each on the same
# topic — see balcony-jungle-v2's opening post + its first reply).
EXPECTED_IMAGE_ASSETS = {
    "post-monstera-albo.webp",
    "post-fiddle-leaf.webp",
    "post-hosta-damage.webp",
    "post-mealybugs.webp",
    "post-balcony-before.webp",
    "post-balcony-after.webp",
    "post-pothos-years.webp",
    "post-orchid-bloom.webp",
}


def _world_counts():
    return (
        User.objects.count(),
        ForumBoard.objects.count(),
        Topic.objects.count(),
        Post.objects.count(),
        Reaction.objects.count(),
        ForumIdentificationAttachment.objects.count(),
        get_image_model().objects.count(),
    )


@override_settings(DEBUG=False)
@pytest.mark.django_db
def test_refuses_without_confirm_when_not_debug():
    with pytest.raises(CommandError, match="--confirm"):
        call_command("seed_demo_content")


@override_settings(DEBUG=False)
@pytest.mark.django_db
def test_confirm_seeds_when_not_debug():
    # The layer-1 guard's actual production path (PR-2.5 plan: Railway runs
    # this with --confirm) — distinct from "refuses without --confirm" above,
    # which only proves the guard fires, not that it lets the real call
    # through.
    call_command("seed_demo_content", confirm=True)
    assert Topic.objects.count() == len(TOPICS)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_refuses_when_real_users_exist_even_with_confirm():
    User.objects.create_user(username="alice", password="x")
    with pytest.raises(CommandError, match="real user"):
        call_command("seed_demo_content", confirm=True)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_refuses_when_a_demo_username_has_a_real_email():
    # A demo username alone is not proof of a demo account — someone could
    # sign up as "iris_delgado" with their own address. The guard must key on
    # BOTH the demo username AND the @demo.houseplant-md.com email domain, so
    # this account still counts as REAL and aborts the seed.
    User.objects.create_user(
        username="iris_delgado", email="iris@example.com", password="x"
    )
    with pytest.raises(CommandError, match="real user"):
        call_command("seed_demo_content", confirm=True)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_superuser_does_not_trip_the_guard():
    User.objects.create_superuser(
        username="admin", email="admin@example.com", password="x"
    )
    call_command("seed_demo_content")
    assert Topic.objects.count() == len(TOPICS)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_refuses_to_adopt_a_superuser_holding_a_demo_username():
    """The adoption hole (round-2 review): guard layer 2 excuses superusers
    BY DESIGN (the Railway admin account must not block seeding), so a real
    superuser account that happens to sit on a demo username — real email,
    usable password — sails past that census check untouched. Without the
    fix at the _seed_users() adoption site, `get_or_create()` would then
    find that account, see created=False, and silently treat it as if it
    were the seed's own "iris_delgado" row: no content check catches this
    upstream, because the census guard's whole point is to let superusers
    through.

    "iris_delgado" is deliberately the FIRST entry in USERS (seed_content.py)
    so this failure fires on the very first loop iteration, before any other
    demo user, board, or topic is created — proving "no content created" is
    not an accident of iteration order but a real abort.
    """
    real_admin = User.objects.create_superuser(
        username="iris_delgado", email="iris@realcompany.com", password="x"
    )
    with pytest.raises(CommandError, match="iris_delgado"):
        call_command("seed_demo_content")

    # The real account itself must be left completely untouched — not
    # password-wiped, not email-rewritten, not adopted in any way.
    real_admin.refresh_from_db()
    assert real_admin.email == "iris@realcompany.com"
    assert real_admin.has_usable_password() is True

    # Nothing from the demo world was created off the back of this run.
    assert Topic.objects.count() == 0
    assert ForumBoard.objects.exclude(slug=LEGACY_STARTER_SLUG).count() == 0
    demo_usernames = {u["username"] for u in USERS} - {"iris_delgado"}
    assert not User.objects.filter(username__in=demo_usernames).exists()


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_seeds_the_five_boards_and_removes_empty_starter():
    call_command("seed_default_forum")
    assert ForumBoard.objects.filter(slug=LEGACY_STARTER_SLUG).exists()

    call_command("seed_demo_content")

    slugs = set(ForumBoard.objects.values_list("slug", flat=True))
    expected = {b["slug"] for b in BOARDS}
    assert expected <= slugs
    assert LEGACY_STARTER_SLUG not in slugs

    # Regression guard (audit 2026-07-17 H1): a board attached outside the
    # Site's routable tree has page.url == None and is never served. That
    # bug hit the pre-existing starter board; nothing previously asserted it
    # for boards created by THIS command.
    site_root = Site.objects.get(is_default_site=True).root_page
    for board in ForumBoard.objects.filter(slug__in=expected):
        assert board.is_descendant_of(site_root)
        assert board.get_url() is not None


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_keeps_starter_board_with_topics():
    call_command("seed_default_forum")
    starter = ForumBoard.objects.get(slug=LEGACY_STARTER_SLUG)
    Topic.objects.create(board=starter, title="Keep me", slug="keep-me")

    call_command("seed_demo_content")

    assert ForumBoard.objects.filter(slug=LEGACY_STARTER_SLUG).exists()
    assert ForumBoard.objects.count() == len(BOARDS) + 1


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_run_twice_is_idempotent():
    call_command("seed_demo_content")
    counts_1 = _world_counts()
    updated_1 = dict(Topic.objects.values_list("slug", "updated_at"))

    call_command("seed_demo_content")
    counts_2 = _world_counts()
    updated_2 = dict(Topic.objects.values_list("slug", "updated_at"))

    assert counts_1 == counts_2
    assert updated_1 == updated_2


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_world_shape():
    call_command("seed_demo_content")

    assert Topic.objects.count() == len(TOPICS)

    pinned = Topic.objects.get(slug="bloom-watch-2026")
    assert pinned.is_pinned is True

    solved_topics = Topic.objects.filter(solved_post__isnull=False).select_related(
        "solved_post__author"
    )
    assert solved_topics.count() == 5
    actual_solvers = {t.slug: t.solved_post.author.username for t in solved_topics}
    assert actual_solvers == EXPECTED_SOLVERS

    attachment = ForumIdentificationAttachment.objects.get(
        topic__slug="tree-bark-peels-like-paper"
    )
    assert attachment.provider == "plant_id"
    assert len(attachment.candidates) == 2

    # _get_image()'s dedupe-by-title branch is otherwise unexercised (every
    # asset is referenced exactly once per run-one, and run-two short-circuits
    # before _get_image is ever reached): assert the real files actually
    # landed as Wagtail Image rows, one per distinct asset, not one per
    # reference.
    # "Seed: post-*" = the forum's own assets; seed_demo_content now also
    # seeds the blog (PR 3), whose covers are "Seed: cover-*" and asserted
    # in apps/blog/tests/test_seed_demo_blog.py.
    seeded_images = get_image_model().objects.filter(title__startswith="Seed: post-")
    assert seeded_images.count() == len(EXPECTED_IMAGE_ASSETS)
    assert {
        img.title.removeprefix("Seed: ") for img in seeded_images
    } == EXPECTED_IMAGE_ASSETS

    # balcony-jungle-v2's opening post and first reply each carry a distinct
    # image block — confirms the StreamField "image" block actually resolves
    # to the seeded Image (not merely that a block of that type exists).
    balcony = Topic.objects.get(slug="balcony-jungle-v2")
    opening_post, first_reply = list(balcony.posts.order_by("created_at"))[:2]
    opening_image_titles = [
        block.value.title for block in opening_post.body if block.block_type == "image"
    ]
    reply_image_titles = [
        block.value.title for block in first_reply.body if block.block_type == "image"
    ]
    assert opening_image_titles == ["Seed: post-balcony-before.webp"]
    assert reply_image_titles == ["Seed: post-balcony-after.webp"]

    # Board counters (topic_count/post_count) are maintained only by the
    # published signal's _refresh_board_counters, not by the command's final
    # .update() pass — this is what the board cards Tasks 9-12 screenshot
    # actually read, so a signal regression here must fail loudly, not
    # render as an empty-looking board.
    board_slugs = {b["slug"] for b in BOARDS}
    for board in ForumBoard.objects.filter(slug__in=board_slugs):
        assert board.topic_count > 0
        assert board.post_count > 0

    for topic in Topic.objects.all():
        posts = list(topic.posts.order_by("created_at"))
        assert posts, f"{topic.slug} has no posts"
        newest = max(p.created_at for p in posts)
        assert topic.last_post_at == newest
        for earlier, later in zip(posts, posts[1:]):
            assert earlier.created_at < later.created_at

    demo_usernames = {u["username"] for u in USERS}
    for user in User.objects.filter(username__in=demo_usernames):
        assert user.has_usable_password() is False
        assert user.email.endswith(f"@{DEMO_EMAIL_DOMAIN}")

    for username in ("iris_delgado", "sam_whitaker"):
        profile = ForumProfile.objects.get(user__username=username)
        assert profile.trust_level == 4


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_recount_after_unpublish_keeps_last_post_at_backdated():
    """A post-seed counter recount must not snap a topic's curated age back
    to the seed-run's real wall-clock (review finding #3a).

    signals._refresh_topic_counters derives Topic.last_post_at from live
    posts' first_published_at. The seed command back-dates created_at/
    updated_at via a bare .update(), which bypasses Wagtail's publish path
    entirely — so first_published_at is left at the real seed-run time
    unless the command ALSO back-dates it. Unpublishing any one reply
    triggers exactly such a recount (signals.update_counters_on_unpublish);
    without the fix the recomputed last_post_at lands within seconds of
    "now" instead of staying in the seeded past.
    """
    call_command("seed_demo_content")

    topic = Topic.objects.get(slug="estate-sale-trailing-plant")
    posts = list(topic.posts.order_by("created_at"))
    latest_reply = posts[-1]
    assert not latest_reply.is_opening_post  # sanity: a real reply, not the opener

    seeded_last_post_at = topic.last_post_at
    before_unpublish = timezone.now()

    latest_reply.unpublish()

    topic.refresh_from_db()
    assert topic.last_post_at is not None
    # Comfortably in the seed-run's back-dated past, nowhere near "now".
    assert topic.last_post_at < before_unpublish - timedelta(hours=1)
    # Moved to the new latest LIVE post (further into the past), not just
    # "coincidentally stayed put".
    assert topic.last_post_at < seeded_last_post_at


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_solved_at_is_the_solution_posts_own_timestamp():
    """solved_at must be the ACCEPTED post's own timestamp, not the thread's
    newest post's (review finding #3b) — a solution is frequently not the
    last reply; later replies are often follow-up chatter after the answer
    already landed. True for this seed topic: the solution is reply #2 of 6.
    """
    call_command("seed_demo_content")

    topic = Topic.objects.get(slug="estate-sale-trailing-plant")
    assert topic.solved_post is not None
    posts = list(topic.posts.order_by("created_at"))
    newest_reply = posts[-1]
    assert topic.solved_post.pk != newest_reply.pk  # sanity: not the last post

    assert topic.solved_at == topic.solved_post.created_at
    assert topic.solved_at < newest_reply.created_at
