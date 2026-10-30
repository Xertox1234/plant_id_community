import pytest
from django.core.management import call_command
from wagtail.models import Collection, Page, Site
from wagtail_forum.models import Forum, ForumIndex
from wagtail_forum.services.forum_permissions import is_hidden_for_everyone
from wagtail_forum.tests.factories import make_forum


@pytest.mark.django_db
def test_seed_default_forum_is_idempotent():
    call_command("seed_default_forum")
    call_command("seed_default_forum")  # second run must not duplicate
    assert ForumIndex.objects.count() == 1
    # Todo 665: boards are Forum rows, and every forum sits under a category.
    category = Forum.objects.get(forum_type=Forum.CATEGORY)
    board = Forum.objects.get(forum_type=Forum.FORUM)
    assert Forum.objects.count() == 2
    assert category.slug == "general"
    assert board.parent == category
    assert board.slug == "general-discussion"
    assert is_hidden_for_everyone(board) is False


@pytest.mark.django_db
def test_seed_default_forum_parents_a_new_forum_under_an_existing_category():
    # A database migrated by 0041 already has the "General" category; the seed
    # must reuse it rather than add a second one.
    existing = Forum.objects.create(
        forum_type=Forum.CATEGORY, name="Plants", slug="plants"
    )
    call_command("seed_default_forum")
    call_command("seed_default_forum")
    assert list(Forum.objects.filter(forum_type=Forum.CATEGORY)) == [existing]
    board = Forum.objects.get(forum_type=Forum.FORUM)
    assert board.parent == existing


@pytest.mark.django_db
def test_seed_default_forum_pages_are_routable():
    # Audit 2026-07-17 H1: seeding under the depth-1 treebeard root instead of
    # the Site's root_page left the forum as a sibling of Home — outside every
    # site's routable tree, so page.url was None and serve()/route() never
    # reached it. The seed must attach under Site.root_page.
    call_command("seed_default_forum")
    site_root = Site.objects.get(is_default_site=True).root_page
    index = ForumIndex.objects.get()
    assert index.is_descendant_of(site_root)
    assert index.get_url() is not None


@pytest.mark.django_db
def test_seed_default_forum_publishes_with_revisions():
    # Audit 2026-07-17 L1: bare add_child() leaves live=True with zero
    # revisions and first_published_at=None (no page_published fired) —
    # seeded pages must have revision parity with admin-created ones. Boards
    # are Forum rows since todo 665, so the index is the one page left.
    call_command("seed_default_forum")
    index = ForumIndex.objects.get()
    assert index.live is True
    assert index.revisions.count() == 1
    assert index.first_published_at is not None


@pytest.mark.django_db
def test_seed_default_forum_repairs_misparented_index():
    # A DB seeded by the pre-audit command has ForumIndex under the tree root
    # (unroutable) and no revisions on either page. Re-running the seed must
    # move it under Site.root_page and publish revisions, rather than leaving
    # it broken behind the "already exists" branch.
    tree_root = Page.objects.filter(depth=1).first()
    tree_root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    make_forum(name="General Discussion", slug="general-discussion")
    call_command("seed_default_forum")
    site_root = Site.objects.get(is_default_site=True).root_page
    index = ForumIndex.objects.get()
    assert index.is_descendant_of(site_root)
    assert index.get_url() is not None
    assert index.revisions.count() == 1
    assert index.first_published_at is not None
    assert Forum.objects.filter(forum_type=Forum.FORUM).count() == 1


@pytest.mark.django_db
def test_seed_default_forum_creates_single_image_collection():
    # Deploy-time seeding of the forum image collection (todo 247): two runs must
    # yield exactly one "Forum Images" collection, so the request-time lazy
    # get-or-create never races duplicates into existence.
    call_command("seed_default_forum")
    call_command("seed_default_forum")  # second run must not duplicate
    assert Collection.objects.filter(name="Forum Images").count() == 1
