import pytest
from django.core.management import call_command
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
