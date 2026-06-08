import pytest
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex


@pytest.mark.django_db
def test_board_nests_under_forum_index():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(
        instance=ForumBoard(title="General", slug="general", description="Chat")
    )

    assert board.get_parent().specific == index
    assert board.topic_count == 0
    assert board.post_count == 0
    assert list(index.get_children().type(ForumBoard)) == [board.page_ptr]
