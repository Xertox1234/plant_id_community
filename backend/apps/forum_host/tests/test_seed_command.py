import pytest
from django.core.management import call_command
from wagtail.models import Collection
from wagtail_forum.models import ForumBoard, ForumIndex


@pytest.mark.django_db
def test_seed_default_forum_is_idempotent():
    call_command("seed_default_forum")
    call_command("seed_default_forum")  # second run must not duplicate
    assert ForumIndex.objects.count() == 1
    assert ForumBoard.objects.count() == 1
    board = ForumBoard.objects.get()
    assert board.live is True
    assert board.slug == "general-discussion"


@pytest.mark.django_db
def test_seed_default_forum_creates_single_image_collection():
    # Deploy-time seeding of the forum image collection (todo 247): two runs must
    # yield exactly one "Forum Images" collection, so the request-time lazy
    # get-or-create never races duplicates into existence.
    call_command("seed_default_forum")
    call_command("seed_default_forum")  # second run must not duplicate
    assert Collection.objects.filter(name="Forum Images").count() == 1
