"""A link posted on its own becomes a ``link_preview`` card (todo 428): a
snapshot of the linked page taken once at write time through the host's
fetcher, so every client shows the card and a read never fetches. Links in
prose, links past the cap, and links whose fetch fails stay tappable links.

The fetcher is the dotted-path host hook, faked here — no test reaches the
network."""

import threading
import time

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, TrustLevel

from ..test_embeds import YOUTUBE_VIMEO_FINDERS

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")

HERE = "wagtail_forum.tests.api.test_link_previews"
IMAGE = "forum/link-previews/" + "a" * 64 + ".webp"

# Every URL the fake fetcher was asked for, across threads.
CALLS = []
_calls_lock = threading.Lock()


def _record(url):
    with _calls_lock:
        CALLS.append(url)


def fake_fetcher(url, *, deadline=None):
    _record(url)
    host = url.split("/")[2]
    return {
        "title": f"Title of {host}",
        "description": "A description the page wrote.",
        "site_name": host,
        "domain": host,
        "image": "",
    }


def none_fetcher(url, *, deadline=None):
    _record(url)
    return None


def raising_fetcher(url, *, deadline=None):
    _record(url)
    raise RuntimeError("fetcher bug")


# Held until the timeout test releases it, so the late fetch finishes
# inside that test and cannot record into a later one.
_release_slow = threading.Event()


def slow_fetcher(url, *, deadline=None):
    _record(url)
    _release_slow.wait(5)
    return {"title": "late"}


def image_fetcher(url, *, deadline=None):
    return {**fake_fetcher(url), "image": IMAGE}


def hotlink_fetcher(url, *, deadline=None):
    return {**fake_fetcher(url), "image": "https://cdn.example.org/og.png"}


def _fetcher(name):
    return override_settings(WAGTAILFORUM_LINK_PREVIEW_FETCHER=f"{HERE}.{name}")


@pytest.fixture(autouse=True)
def reset_calls():
    CALLS.clear()
    yield
    CALLS.clear()


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _member(username="author"):
    user = User.objects.create_user(username=username)
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.MEMBER  # autopublishes, no moderation hold
    profile.save(update_fields=["trust_level"])
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _create(client, board, body, slug="link-thread"):
    return client.post(
        f"/forum/boards/{board.slug}/topics/",
        {"title": "Links", "slug": slug, "body": body},
        format="json",
    )


def _paragraph(html):
    return {"type": "paragraph", "value": html}


def _stored(post=None):
    post = post or Post.objects.get()
    return [(b["type"], b["value"]) for b in post.body.raw_data]


def _card(url, host):
    return {
        "url": url,
        "title": f"Title of {host}",
        "description": "A description the page wrote.",
        "site_name": host,
        "domain": host,
        "image": "",
    }


def _linked(url):
    return f'<a href="{url}" rel="noopener noreferrer nofollow">{url}</a>'


# --- conversion ---------------------------------------------------------


@pytest.mark.django_db
@_fetcher("fake_fetcher")
@pytest.mark.parametrize(
    ("html", "url"),
    [
        # The mobile composer: bare text, no <p>.
        ("https://example.com/a/long/path?x=1", "https://example.com/a/long/path?x=1"),
        # The web shape, and the web's autolinked shape.
        ("<p>https://example.com/</p>", "https://example.com/"),
        (
            '<p><a href="https://example.com/page">https://example.com/page</a></p>',
            "https://example.com/page",
        ),
    ],
)
def test_a_link_posted_on_its_own_is_stored_as_a_card(html, url):
    resp = _create(_client(_member()), _board(), [_paragraph(html)])

    assert resp.status_code == 201, resp.data
    assert _stored() == [("link_preview", _card(url, "example.com"))]
    assert CALLS == [url]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fetcher",
    [None, f"{HERE}.none_fetcher", f"{HERE}.raising_fetcher", f"{HERE}.nowhere"],
)
def test_no_card_leaves_a_tappable_link_not_plain_text(fetcher):
    url = "https://example.com/"
    with override_settings(WAGTAILFORUM_LINK_PREVIEW_FETCHER=fetcher):
        resp = _create(_client(_member()), _board(), [_paragraph(url)])

    assert resp.status_code == 201, resp.data
    assert _stored() == [("paragraph", _linked(url))]


@pytest.mark.django_db
@_fetcher("slow_fetcher")
@override_settings(WAGTAILFORUM_LINK_PREVIEW_FETCH_TIMEOUT_SECONDS=0.1)
def test_a_fetch_that_outlives_the_window_leaves_a_link():
    url = "https://example.com/"
    _release_slow.clear()
    try:
        started = time.monotonic()
        resp = _create(_client(_member()), _board(), [_paragraph(url)])
        elapsed = time.monotonic() - started
    finally:
        _release_slow.set()

    assert resp.status_code == 201, resp.data
    assert elapsed < 4  # the author did not wait for the fetch
    assert _stored() == [("paragraph", _linked(url))]


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_only_the_first_five_distinct_links_become_cards():
    urls = [f"https://site{n}.example/" for n in range(7)]
    body = [_paragraph(url) for url in urls] + [_paragraph(urls[0])]

    resp = _create(_client(_member()), _board(), body)

    assert resp.status_code == 201, resp.data
    stored = _stored()
    assert [kind for kind, _ in stored] == ["link_preview"] * 5 + [
        "paragraph",
        "paragraph",
        # A repeat of a URL that already has a card is a card at no cost.
        "link_preview",
    ]
    assert stored[5] == ("paragraph", _linked(urls[5]))
    # Links past the cap are never fetched.
    assert sorted(CALLS) == sorted(urls[:5])


@pytest.mark.django_db
@_fetcher("fake_fetcher")
@override_settings(
    WAGTAILFORUM_ALLOW_EMBED_BLOCKS=True, WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS
)
def test_a_video_link_is_still_an_embed_and_the_caps_are_separate(monkeypatch):
    monkeypatch.setattr("wagtail_forum.api.sanitize.warm_embeds", lambda urls: None)
    videos = [f"https://youtu.be/dQw4w9WgXc{n}" for n in range(6)]
    links = [f"https://site{n}.example/" for n in range(5)]

    resp = _create(
        _client(_member()), _board(), [_paragraph(url) for url in videos + links]
    )

    assert resp.status_code == 201, resp.data
    kinds = [kind for kind, _ in _stored()]
    # Five videos embed; the sixth stays a link, never a card; and the five
    # other links all still get cards — the video cap did not eat theirs.
    assert kinds == ["embed"] * 5 + ["paragraph"] + ["link_preview"] * 5
    assert sorted(CALLS) == sorted(links)


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_a_link_inside_prose_stays_in_the_prose_as_a_link():
    resp = _create(
        _client(_member()),
        _board(),
        [_paragraph("<p>Look at this: https://example.com/a.</p>")],
    )

    assert resp.status_code == 201, resp.data
    assert _stored() == [
        ("paragraph", f"<p>Look at this: {_linked('https://example.com/a')}.</p>")
    ]
    assert CALLS == []


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_a_submitted_card_keeps_only_its_url():
    """A member cannot post a card whose title or image say something the
    linked page does not: every field but the URL is re-derived."""
    url = "https://example.com/"
    forged = {
        "type": "link_preview",
        "value": {
            "url": url,
            "title": "Your bank: log in here",
            "description": "forged",
            "image": IMAGE,
            "site_name": "bank.example",
            "domain": "bank.example",
        },
    }

    resp = _create(_client(_member()), _board(), [forged])

    assert resp.status_code == 201, resp.data
    assert _stored() == [("link_preview", _card(url, "example.com"))]


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_the_read_envelope_sent_back_is_accepted():
    """``image_url: null`` is not a string; a client echoing what it read
    must not get a 400 for it."""
    envelope = {
        "type": "link_preview",
        "value": {
            "url": "https://example.com/",
            "title": "t",
            "description": "",
            "site_name": "",
            "domain": "",
            "image_url": None,
        },
    }

    resp = _create(_client(_member()), _board(), [envelope])

    assert resp.status_code == 201, resp.data
    assert _stored()[0][0] == "link_preview"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value",
    [None, "https://example.com/", {"title": "no url"}, {"url": 42}],
)
def test_a_malformed_card_is_a_400(value):
    resp = _create(
        _client(_member()), _board(), [{"type": "link_preview", "value": value}]
    )

    assert resp.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("fetcher", [None, f"{HERE}.fake_fetcher"])
def test_a_submitted_card_that_cannot_be_a_card_becomes_its_link(fetcher):
    bad = {"type": "link_preview", "value": {"url": "javascript:alert(1)"}}
    good = {"type": "link_preview", "value": {"url": "https://example.com/"}}
    with override_settings(WAGTAILFORUM_LINK_PREVIEW_FETCHER=fetcher):
        resp = _create(_client(_member()), _board(), [bad, good])

    assert resp.status_code == 201, resp.data
    stored = _stored()
    assert stored[0] == ("paragraph", "<p>javascript:alert(1)</p>")
    if fetcher is None:
        assert stored[1] == ("paragraph", f"<p>{_linked('https://example.com/')}</p>")
    else:
        assert stored[1][0] == "link_preview"
        # The host fetcher is only ever handed an http(s) link.
        assert CALLS == ["https://example.com/"]


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_a_body_that_is_refused_costs_no_fetch():
    resp = _create(
        _client(_member()),
        _board(),
        [_paragraph("https://example.com/"), {"type": "image", "value": 999999}],
    )

    assert resp.status_code == 400
    assert CALLS == []


@pytest.mark.django_db
@_fetcher("hotlink_fetcher")
def test_a_card_never_stores_a_third_party_image():
    _create(_client(_member()), _board(), [_paragraph("https://example.com/")])

    assert _stored()[0][1]["image"] == ""


# --- edit ---------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "resend",
    [
        # The web editor turns a card back into its link (like an embed).
        lambda url, _card: _paragraph(f'<p><a href="{url}">{url}</a></p>'),
        # A client that echoes the block it read.
        lambda url, card: {"type": "link_preview", "value": card},
    ],
)
def test_an_edit_that_keeps_a_card_reuses_it_without_fetching(resend):
    url = "https://example.com/"
    user = _member()
    with _fetcher("fake_fetcher"):
        _create(_client(user), _board(), [_paragraph(url)])
    post = Post.objects.get()
    stored = post.body.raw_data[0]["value"]
    CALLS.clear()

    with _fetcher("raising_fetcher"):
        resp = _client(user).patch(
            f"/forum/posts/{post.id}/",
            {"body": [resend(url, stored), _paragraph("An added line.")]},
            format="json",
        )

    assert resp.status_code == 200, resp.data
    post.refresh_from_db()
    assert _stored(post)[0] == ("link_preview", _card(url, "example.com"))
    assert CALLS == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "resend",
    [
        # Web: the card goes back into the editor as its link.
        lambda url, _card: _paragraph(f'<p><a href="{url}">{url}</a></p>'),
        # Mobile: the edit field holds the bare URL.
        lambda url, _card: _paragraph(url),
        # A client that echoes the block it read.
        lambda url, card: {"type": "link_preview", "value": card},
    ],
)
def test_an_edit_keeps_a_stored_card_while_no_fetcher_is_set(resend):
    """The host's kill switch (or a host that later drops its fetcher) stops
    NEW cards. It must not strip the cards already stored the next time their
    post is edited for an unrelated typo: reusing a stored card needs no
    fetch (slice C review)."""
    url = "https://example.com/"
    user = _member()
    with _fetcher("fake_fetcher"):
        _create(_client(user), _board(), [_paragraph(url)])
    post = Post.objects.get()
    stored = post.body.raw_data[0]["value"]

    with override_settings(WAGTAILFORUM_LINK_PREVIEW_FETCHER=None):
        resp = _client(user).patch(
            f"/forum/posts/{post.id}/",
            {"body": [resend(url, stored), _paragraph("A fixed typo.")]},
            format="json",
        )

    assert resp.status_code == 200, resp.data
    post.refresh_from_db()
    assert _stored(post)[0] == ("link_preview", _card(url, "example.com"))


# --- read ---------------------------------------------------------------


@pytest.mark.django_db
def test_reading_a_card_never_contacts_the_linked_site():
    url = "https://example.com/some/long/path?x=1"
    with _fetcher("fake_fetcher"):
        _create(_client(_member()), _board(), [_paragraph(url)])
    topic_id = Post.objects.get().topic_id
    CALLS.clear()

    with _fetcher("raising_fetcher"):
        resp = APIClient().get(f"/forum/topics/{topic_id}/posts/")

    assert resp.status_code == 200
    assert CALLS == []
    block = resp.data["results"][0]["body"][0]
    assert block["type"] == "link_preview"
    assert block["value"] == {
        "url": url,
        "title": "Title of example.com",
        "description": "A description the page wrote.",
        "site_name": "example.com",
        "domain": "example.com",
        "image_url": None,
    }


@pytest.mark.django_db
def test_a_cached_image_is_served_from_our_storage():
    with _fetcher("image_fetcher"):
        _create(_client(_member()), _board(), [_paragraph("https://example.com/")])
    topic_id = Post.objects.get().topic_id

    value = (
        APIClient()
        .get(f"/forum/topics/{topic_id}/posts/")
        .data["results"][0]["body"][0]["value"]
    )

    from django.core.files.storage import default_storage

    # Absolute against the request, like an image block's URL: local storage
    # answers a relative /media/... the mobile client cannot resolve.
    assert default_storage.url(IMAGE).startswith("/")
    assert value["image_url"] == "http://testserver" + default_storage.url(IMAGE)


def _read_stored_card(stored):
    """Serve a card written straight to the column, as a CMS edit or an
    import would (past the API's write-side rules)."""
    _create(_client(_member()), _board(), [_paragraph("placeholder")])
    post = Post.objects.get()
    post.body = [{"type": "link_preview", "value": stored}]
    post.save()
    return (
        APIClient()
        .get(f"/forum/topics/{post.topic_id}/posts/")
        .data["results"][0]["body"][0]["value"]
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "https://user:pw@example.com/", "", "ftp://x.org/"]
)
def test_a_stored_card_without_a_safe_link_is_served_as_null(url):
    assert _read_stored_card({"url": url, "title": "x"}) is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "image",
    [
        "https://cdn.example.org/og.png",  # a hotlink
        "original_images/secret.png",  # another media file
        "forum/link-previews/../x.webp",
        "forum/link-previews/" + "a" * 64 + ".svg",
    ],
)
def test_a_stored_card_serves_only_a_cached_image(image):
    value = _read_stored_card({"url": "https://example.com/", "image": image})

    assert value["url"] == "https://example.com/"
    assert value["image_url"] is None


# --- todo 448 items 1-3 and 9: the gate before a host turns the fetcher on ---


@pytest.fixture
def one_worker_pool(monkeypatch):
    """A private one-thread pool in place of the process-wide one, so a test
    can make the queue back up without touching other tests' fetches."""
    from concurrent.futures import ThreadPoolExecutor

    from wagtail_forum import link_previews

    pool = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(link_previews, "_executor", pool)
    yield pool
    pool.shutdown(wait=True)


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_LINK_PREVIEW_FETCH_TIMEOUT_SECONDS=0.2)
def test_a_fetch_still_queued_when_the_window_closes_is_cancelled(one_worker_pool):
    """Item 1: the pool was busy, so the second link never started inside
    the window. It must be dropped, not run later for nobody — a burst of
    posts would otherwise build a backlog that times out every post after."""
    from wagtail_forum.link_previews import fetch_snapshots

    release = threading.Event()
    started = []

    def blocking_fetcher(url, *, deadline=None):
        started.append(url)
        release.wait(5)
        return {"title": url}

    try:
        snapshots = fetch_snapshots(
            blocking_fetcher, ["https://a.example.com/", "https://b.example.com/"]
        )
    finally:
        release.set()
    one_worker_pool.shutdown(wait=True)  # anything still queued runs now

    assert snapshots == {}
    assert started == ["https://a.example.com/"]


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_LINK_PREVIEW_FETCH_TIMEOUT_SECONDS=2)
def test_every_fetcher_gets_the_window_end_counted_from_submit(one_worker_pool):
    """Item 9: the second fetch waits ~0.3 s for the one thread, yet gets the
    SAME deadline as the first — the package's window, not a fresh one from
    when a thread picked it up."""
    from wagtail_forum.link_previews import fetch_snapshots

    deadlines = {}

    def recording_fetcher(url, *, deadline=None):
        deadlines[url] = deadline
        if url.startswith("https://a."):
            time.sleep(0.3)
        return {"title": url}

    submitted = time.monotonic()
    snapshots = fetch_snapshots(
        recording_fetcher, ["https://a.example.com/", "https://b.example.com/"]
    )

    assert set(snapshots) == {"https://a.example.com/", "https://b.example.com/"}
    first, second = (
        deadlines["https://a.example.com/"],
        deadlines["https://b.example.com/"],
    )
    assert first == second
    assert submitted + 2 <= first <= submitted + 2.1


@pytest.mark.django_db
@_fetcher("fake_fetcher")
@pytest.mark.parametrize(
    "html",
    [
        "<p><code>https://api.example.com/v1/things</code></p>",
        '<p><a href="https://api.example.com/v1/x"><code>https://api.example.com/v1/x</code></a></p>',
    ],
)
def test_a_link_written_as_code_is_never_a_card(html):
    """Item 2: a URL in a code sample is code. It is not fetched and stays
    in its paragraph as the author wrote it."""
    resp = _create(_client(_member()), _board(), [_paragraph(html)])

    assert resp.status_code == 201, resp.data
    [(block_type, value)] = _stored()
    assert block_type == "paragraph"
    assert "<code>" in value
    assert CALLS == []


# Every shape is_card_url might meet. Whatever it accepts, the block's own
# URLBlock must accept too (item 3).
CARD_URL_SHAPES = [
    "https://example.com/",
    "https://example.com",
    "http://example.com:8080/a?b=1#c",
    "https://sub.example.co.uk/path/to/page",
    "https://bücher.example/",
    "https://xn--bcher-kva.example/",
    "http://93.184.216.34/",
    "http://[2001:db8::1]/",
    "https://localhost/",
    "https://example.com./",
    "https://my_site.example.com/",
    "https://-leading.example.com/",
    "https://trailing-.example.com/",
    "http://intranet/",
    "https://example.com/" + "a" * 2000,
    "https://exa mple.com/",
    "https://example.com/%zz",
]


@pytest.mark.parametrize("url", CARD_URL_SHAPES)
def test_is_card_url_never_accepts_what_the_block_refuses(url):
    from django.core.exceptions import ValidationError
    from wagtail_forum.blocks import LinkPreviewBlock
    from wagtail_forum.link_previews import is_card_url

    if not is_card_url(url):
        return
    try:
        LinkPreviewBlock().child_blocks["url"].clean(url)
    except ValidationError as exc:  # pragma: no cover - the failure message
        pytest.fail(f"is_card_url accepts {url!r} but URLBlock refuses it: {exc}")


def test_an_underscore_host_is_not_a_card_url():
    from wagtail_forum.link_previews import is_card_url

    assert is_card_url("https://example.com/")
    assert not is_card_url("https://my_site.example.com/")


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_a_host_the_block_refuses_stays_a_link_and_the_post_still_cleans():
    """Item 3 end to end: before the fix this saved as a card, and a
    moderator's later /cms/ save of the post failed with "Enter a valid URL"
    on a block they never touched. The stored body must clean as the CMS
    form would clean it."""
    from wagtail_forum.blocks import ForumBodyBlock

    url = "https://my_site.example.com/page"
    resp = _create(_client(_member()), _board(), [_paragraph(url)])

    assert resp.status_code == 201, resp.data
    assert [t for t, _ in _stored()] == ["paragraph"]
    assert CALLS == []
    ForumBodyBlock().clean(Post.objects.get().body)
