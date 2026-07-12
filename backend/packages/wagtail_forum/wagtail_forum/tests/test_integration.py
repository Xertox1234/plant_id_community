"""End-to-end moderation-pipeline test crossing all of Plan 1B's seams.

The per-task tests publish via direct ``revision.publish()``; this one drives the
full path a real new user takes — ``submit_for_moderation`` -> Wagtail workflow ->
``SpamCheckTask`` -> finish-action publish -> ``published`` signal -> counter
maintenance + trust promotion -> the promoted trust changing the NEXT decision.
"""

import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.workflow import ensure_default_workflow, submit_for_moderation

User = get_user_model()

SPAM = "http://a.com http://b.com http://c.com http://d.com http://e.com"


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _submit(topic, author, text, opening=False):
    post = Post(
        topic=topic,
        author=author,
        is_opening_post=opening,
        body=[{"type": "paragraph", "value": f"<p>{text}</p>"}],
    )
    post.save()
    return submit_for_moderation(post, author), post


@pytest.mark.django_db
def test_new_user_grinds_through_workflow_to_member_then_autopublishes_spam():
    user = User.objects.create_user(username="grind")
    ForumProfile.for_user(user)  # trust NEW
    ensure_default_workflow()
    topic = Topic.objects.create(board=_board(), title="T", slug="t", author=user)

    # Five clean posts, each routed through the moderation workflow (the user is
    # below MEMBER until the fifth publish promotes them).
    for i in range(5):
        status, _ = _submit(
            topic, user, f"a clean and friendly post {i}", opening=(i == 0)
        )
        assert status == "published"

    profile = ForumProfile.for_user(user)
    # Counters were maintained via the WORKFLOW publish path (not direct publish):
    assert profile.post_count == 5
    # ...and the fifth publish promoted the author to MEMBER (threshold = 5).
    assert profile.trust_level == TrustLevel.MEMBER

    # Now MEMBER: the trust bypass means a spammy sixth post auto-publishes with
    # NO spam check (this is the documented v1 trusted-grind risk, asserted here
    # so the bypass is visible and intentional, not silent).
    status, spam_post = _submit(topic, user, SPAM)
    assert status == "published"
    spam_post.refresh_from_db()
    assert spam_post.live is True
