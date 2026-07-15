import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page, PageViewRestriction
from wagtail_forum.mentions import resolve_mentioned_users
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()


def _topic_and_post(
    topic_author,
    post_author=None,
    body_text="",
    is_opening_post=False,
    restricted=False,
):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    if restricted:
        PageViewRestriction.objects.create(page=board, restriction_type="login")
    topic = Topic.objects.create(board=board, title="T", slug="t", author=topic_author)
    body = [{"type": "paragraph", "value": f"<p>{body_text}</p>"}] if body_text else []
    post = Post.objects.create(
        topic=topic,
        author=post_author or topic_author,
        body=body,
        is_opening_post=is_opening_post,
    )
    return topic, post


@pytest.mark.django_db
def test_resolves_multiple_mentions():
    author = User.objects.create_user(username="author")
    alice = User.objects.create_user(username="alice")
    bob = User.objects.create_user(username="bob")
    _, post = _topic_and_post(author, body_text="hi @alice and @bob")

    resolved = resolve_mentioned_users(post)

    assert {u.pk for u in resolved} == {alice.pk, bob.pk}


@pytest.mark.django_db
def test_dedups_repeated_mention():
    author = User.objects.create_user(username="author2")
    alice = User.objects.create_user(username="alice2")
    _, post = _topic_and_post(author, body_text="@alice2 thanks @alice2!")

    resolved = resolve_mentioned_users(post)

    assert [u.pk for u in resolved] == [alice.pk]


@pytest.mark.django_db
def test_caps_at_mention_max_per_post(settings):
    settings.WAGTAILFORUM_MENTION_MAX_PER_POST = 2
    author = User.objects.create_user(username="author3")
    users = [User.objects.create_user(username=f"user3{i}") for i in range(4)]
    text = " ".join(f"@{u.username}" for u in users)
    _, post = _topic_and_post(author, body_text=text)

    resolved = resolve_mentioned_users(post)

    assert len(resolved) == 2
    assert {u.pk for u in resolved} == {users[0].pk, users[1].pk}


@pytest.mark.django_db
def test_exact_case_match_only():
    """No case-insensitive uniqueness on username (plain AbstractUser) — an
    exact match is the only safe lookup that can't raise
    MultipleObjectsReturned on a case collision (todo 253 slice 4 review)."""
    author = User.objects.create_user(username="author4")
    User.objects.create_user(username="alice4")
    _, post = _topic_and_post(author, body_text="hey @Alice4")

    resolved = resolve_mentioned_users(post)

    assert resolved == []


@pytest.mark.django_db
def test_excludes_pks():
    author = User.objects.create_user(username="author5")
    alice = User.objects.create_user(username="alice5")
    _, post = _topic_and_post(author, body_text="@alice5 @author5")

    resolved = resolve_mentioned_users(post, exclude_pks={author.pk})

    assert [u.pk for u in resolved] == [alice.pk]


@pytest.mark.django_db
def test_empty_when_board_not_public():
    author = User.objects.create_user(username="author6")
    User.objects.create_user(username="alice6")
    _, post = _topic_and_post(author, body_text="@alice6", restricted=True)

    resolved = resolve_mentioned_users(post)

    assert resolved == []


@pytest.mark.django_db
def test_ignores_unknown_username():
    author = User.objects.create_user(username="author7")
    _, post = _topic_and_post(author, body_text="hi @nobody7")

    resolved = resolve_mentioned_users(post)

    assert resolved == []


@pytest.mark.django_db
def test_does_not_match_email_address_domain():
    """ "@" mid-token (an email address, extremely common in a plant-ID forum
    — "email me at X@gmail.com") must not resolve as a mention, even if a
    user happens to be named after the domain fragment (todo 253 slice 4
    review)."""
    author = User.objects.create_user(username="author10")
    User.objects.create_user(username="gmail")
    _, post = _topic_and_post(author, body_text="reach me at admin@gmail.com")

    resolved = resolve_mentioned_users(post)

    assert resolved == []


@pytest.mark.django_db
def test_ignores_at_token_inside_code_block():
    """A code sample's contents (e.g. a Python @property decorator) are not
    reader-visible prose — must not resolve as a mention (todo 253 slice 4
    review, verified via manage.py shell that plain_text_excerpt's raw
    stringification of a code block's value would otherwise expose this)."""
    author = User.objects.create_user(username="author11")
    User.objects.create_user(username="property")
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum11", slug="forum11"))
    board = index.add_child(instance=ForumBoard(title="General11", slug="general11"))
    topic = Topic.objects.create(board=board, title="T11", slug="t11", author=author)
    post = Post.objects.create(
        topic=topic,
        author=author,
        body=[
            {
                "type": "code",
                "value": {
                    "code": "@property\ndef bar(self): pass",
                    "language": "python",
                },
            }
        ],
    )

    resolved = resolve_mentioned_users(post)

    assert resolved == []


@pytest.mark.django_db
def test_ignores_at_token_inside_link_attribute_but_resolves_link_label():
    """An <a> tag's href/title attributes survive sanitization (api/sanitize.py
    allows both) but are never reader-visible — only the link's text label is.
    A mention hiding in an attribute must not resolve; a mention that IS the
    visible label still must (todo 253 slice 4 review)."""
    author = User.objects.create_user(username="author12")
    User.objects.create_user(username="victim")
    alice = User.objects.create_user(username="alice12")
    _, post = _topic_and_post(
        author,
        body_text=(
            '<a href="https://example.com/@victim" title="@victim">click</a> '
            'thanks <a href="https://example.com/profile">@alice12</a>'
        ),
    )

    resolved = resolve_mentioned_users(post)

    assert [u.pk for u in resolved] == [alice.pk]


@pytest.mark.django_db
def test_parses_title_for_opening_post():
    author = User.objects.create_user(username="author8")
    alice = User.objects.create_user(username="alice8")
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum8", slug="forum8"))
    board = index.add_child(instance=ForumBoard(title="General8", slug="general8"))
    topic = Topic.objects.create(
        board=board, title="Hello @alice8", slug="t8", author=author
    )
    post = Post.objects.create(
        topic=topic, author=author, body=[], is_opening_post=True
    )

    resolved = resolve_mentioned_users(post)

    assert [u.pk for u in resolved] == [alice.pk]


@pytest.mark.django_db
def test_reply_does_not_parse_topic_title():
    """A reply is not an opening post — _mention_scan_text() deliberately
    excludes the topic title for non-opening posts, so a mention in the TITLE
    must not leak into a reply's mention resolution."""
    author = User.objects.create_user(username="author9")
    User.objects.create_user(username="alice9")
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum9", slug="forum9"))
    board = index.add_child(instance=ForumBoard(title="General9", slug="general9"))
    topic = Topic.objects.create(
        board=board, title="Hello @alice9", slug="t9", author=author
    )
    reply = Post.objects.create(
        topic=topic, author=author, body=[], is_opening_post=False
    )

    resolved = resolve_mentioned_users(reply)

    assert resolved == []
