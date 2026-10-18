"""A link posted on its own becomes a ``link_preview`` card (todo 428): a
snapshot of the linked page taken once at write time through the host's
fetcher, so every client shows the card and a read never fetches. Links in
prose, links past the cap, and links whose fetch fails stay tappable links.

The fetcher is the dotted-path host hook, faked here — no test reaches the
network."""

import json
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
    return (
        f'<a href="{url}" target="_blank" rel="noopener noreferrer nofollow">{url}</a>'
    )


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
        # A URL gets one card: a repeat stays its link (todo 535).
        "paragraph",
    ]
    assert stored[5] == ("paragraph", _linked(urls[5]))
    assert stored[7] == ("paragraph", _linked(urls[0]))
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


@pytest.fixture
def first_fetch_started(monkeypatch):
    """An Event the test's fetcher sets when it starts. The window does not
    open until it is set, so "the first fetch is running, the second is
    queued" holds however slowly the pool thread is scheduled (todo 539
    item 7)."""
    from wagtail_forum import link_previews

    started = threading.Event()
    real_wait = link_previews.wait_futures

    def wait_after_start(futures, timeout=None):
        assert started.wait(5), "the first fetch never started"
        return real_wait(futures, timeout=timeout)

    monkeypatch.setattr(link_previews, "wait_futures", wait_after_start)
    return started


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_LINK_PREVIEW_FETCH_TIMEOUT_SECONDS=0.2)
def test_a_fetch_still_queued_when_the_window_closes_is_cancelled(
    one_worker_pool, first_fetch_started
):
    """Item 1: the pool was busy, so the second link never started inside
    the window. It must be dropped, not run later for nobody — a burst of
    posts would otherwise build a backlog that times out every post after."""
    from wagtail_forum.link_previews import fetch_snapshots

    release = threading.Event()
    started = []

    def blocking_fetcher(url, *, deadline=None):
        started.append(url)
        first_fetch_started.set()
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


# --- todo 448 items 4, 6, 7, 10, 11 and 13 -------------------------------


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_a_sole_link_with_sentence_punctuation_cards_the_link_without_it():
    """Item 7: the trailing dot is the sentence's, as it is for an auto-link."""
    resp = _create(_client(_member()), _board(), [_paragraph("https://example.com/a.")])

    assert resp.status_code == 201, resp.data
    assert _stored() == [
        ("link_preview", _card("https://example.com/a", "example.com"))
    ]
    assert CALLS == ["https://example.com/a"]


@pytest.mark.django_db
@_fetcher("fake_fetcher")
@override_settings(
    WAGTAILFORUM_ALLOW_EMBED_BLOCKS=True, WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS
)
def test_a_video_link_written_as_code_stays_code(monkeypatch):
    """Item 10: the video path skips code as the card path does (item 2)."""
    monkeypatch.setattr("wagtail_forum.api.sanitize.warm_embeds", lambda urls: None)
    html = "<p><code>https://www.youtube.com/watch?v=dQw4w9WgXcQ</code></p>"

    resp = _create(_client(_member()), _board(), [_paragraph(html)])

    assert resp.status_code == 201, resp.data
    [(block_type, value)] = _stored()
    assert block_type == "paragraph"
    assert "<code>" in value
    assert CALLS == []


@pytest.mark.parametrize(
    "image",
    ["https://cdn.example.org/og.png", "original_images/secret.png", 7, None],
)
def test_a_reused_card_carries_only_a_cached_image_name(image):
    """Item 6: the edit path keeps the fetcher's rule for a stored image."""
    from wagtail_forum.link_previews import link_preview_snapshots

    raw = [
        {
            "type": "link_preview",
            "value": {"url": "https://example.com/", "image": image},
        }
    ]

    assert link_preview_snapshots(raw)["https://example.com/"]["image"] == ""


def test_a_reused_card_keeps_a_cached_image_name():
    from wagtail_forum.link_previews import link_preview_snapshots

    raw = [
        {
            "type": "link_preview",
            "value": {"url": "https://example.com/", "image": IMAGE},
        }
    ]

    assert link_preview_snapshots(raw)["https://example.com/"]["image"] == IMAGE


def _sized_body(size, tail):
    """One paragraph whose JSON is exactly ``size`` characters, ending in
    ``tail``."""
    shell = len(json.dumps([_paragraph(f"<p> {tail}</p>")]))
    filler = ("lorem ipsum " * 10_000)[: size - shell].rstrip()
    filler += "m" * (size - shell - len(filler))
    body = [_paragraph(f"<p>{filler} {tail}</p>")]
    assert len(json.dumps(body)) == size
    return body


@pytest.mark.django_db
def test_a_body_that_auto_linking_pushes_over_the_cap_is_refused():
    """Item 4: the cap holds for what is STORED. Before, this saved at more
    than the cap, and resending it unchanged on edit was then refused."""
    from wagtail_forum.api.sanitize import MAX_BODY_CHARS

    body = _sized_body(MAX_BODY_CHARS - 10, "https://a.example/ https://b.example/")

    resp = _create(_client(_member()), _board(), body)

    assert resp.status_code == 400
    assert "too large" in str(resp.data)
    assert not Post.objects.exists()


@pytest.mark.django_db
def test_a_body_that_saved_resaves_unchanged():
    from wagtail_forum.api.sanitize import MAX_BODY_CHARS

    user = _member()
    body = _sized_body(MAX_BODY_CHARS - 1_000, "https://a.example/ https://b.example/")
    assert _create(_client(user), _board(), body).status_code == 201
    post = Post.objects.get()
    stored = list(post.body.raw_data)

    resp = _client(user).patch(
        f"/forum/posts/{post.id}/",
        {"body": [{"type": b["type"], "value": b["value"]} for b in stored]},
        format="json",
    )

    assert resp.status_code == 200, resp.data
    post.refresh_from_db()
    assert [b["value"] for b in post.body.raw_data] == [b["value"] for b in stored]


class _Raw:
    def __init__(self, raw_data):
        self.raw_data = raw_data


def test_a_card_only_body_has_an_empty_excerpt():
    """Item 11, closed by the owner (2026-09-28): a card's title is the
    linked page's words, not the author's, so a card-only topic lists with
    no excerpt."""
    from wagtail_forum.api.views import plain_text_excerpt

    card = {
        "type": "link_preview",
        "value": _card("https://example.com/", "example.com"),
    }

    assert plain_text_excerpt(_Raw([card]), 200) == ""
    assert plain_text_excerpt(_Raw([card, _paragraph("<p>Mine.</p>")]), 200) == "Mine."


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_a_link_in_prose_opens_in_a_new_tab_whatever_target_was_sent():
    """Item 13: every body link opens in a new tab, as a card does; a
    client-supplied target never survives."""
    resp = _create(
        _client(_member()),
        _board(),
        [
            _paragraph(
                '<p>See <a href="https://example.com/a" target="_self">this</a> '
                "and https://example.com/b.</p>"
            )
        ],
    )

    assert resp.status_code == 201, resp.data
    [(_, value)] = _stored()
    assert value == (
        '<p>See <a href="https://example.com/a" target="_blank" '
        'rel="noopener noreferrer nofollow">this</a> and '
        f"{_linked('https://example.com/b')}.</p>"
    )


@pytest.mark.django_db
def test_a_stored_card_whose_url_ends_in_punctuation_survives_an_edit():
    """Item 7 must not strand a card stored before trimming: both clients
    resend a card as its link, and the untrimmed link names the card."""
    url = "https://example.com/a."
    user = _member()
    with _fetcher("fake_fetcher"):
        _create(_client(user), _board(), [_paragraph("Seed.")])
    post = Post.objects.get()
    post.body = [{"type": "link_preview", "value": _card(url, "example.com")}]
    post.save()

    with override_settings(WAGTAILFORUM_LINK_PREVIEW_FETCHER=None):
        resp = _client(user).patch(
            f"/forum/posts/{post.id}/",
            {"body": [_paragraph(url), _paragraph("A fixed typo.")]},
            format="json",
        )

    assert resp.status_code == 200, resp.data
    post.refresh_from_db()
    assert _stored(post)[0] == ("link_preview", _card(url, "example.com"))


# --- todo 535: follow-ups from todo 448's reviews ------------------------------


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_item1_a_body_refused_for_its_stored_size_costs_no_fetch():
    """Auto-linking the prose puts the body over the cap. The refusal comes
    BEFORE the card fetch, so the sole link below is never fetched and no
    preview image is stored for a post that does not save."""
    from wagtail_forum.api.sanitize import MAX_BODY_CHARS

    card_paragraph = _paragraph("<p>https://card.example/</p>")
    extra = len(json.dumps(card_paragraph)) + len(", ")
    body = _sized_body(
        MAX_BODY_CHARS - 10 - extra, "https://a.example/ https://b.example/"
    ) + [card_paragraph]
    assert len(json.dumps(body)) == MAX_BODY_CHARS - 10

    resp = _create(_client(_member()), _board(), body)

    assert resp.status_code == 400
    assert "too large" in str(resp.data)
    assert CALLS == []


def _many_links_body(size, links=300):
    """One paragraph of ``links`` links, written without the attributes the
    server adds, padded so its JSON is exactly ``size`` characters."""
    anchors = " ".join(
        f'<a href="https://l.example/{n}">https://l.example/{n}</a>'
        for n in range(links)
    )
    shell = len(json.dumps([_paragraph(f"<p>{anchors} </p>")]))
    filler = "m" * (size - shell)
    body = [_paragraph(f"<p>{anchors} {filler}</p>")]
    assert len(json.dumps(body)) == size
    return body


@pytest.mark.django_db
def test_item2_a_near_cap_post_with_many_links_stays_editable():
    """The server adds ``target`` and ``rel`` to every link: 56 JSON
    characters each, about 17k here. They do not count toward the cap, so
    the post saves, its stored body resends unchanged, and a post stored
    before the server added ``target`` still accepts an edit."""
    from wagtail_forum.api.sanitize import MAX_BODY_CHARS

    user = _member()
    body = _many_links_body(MAX_BODY_CHARS - 2_000)
    resp = _create(_client(user), _board(), body)
    assert resp.status_code == 201, resp.data
    post = Post.objects.get()
    stored = list(post.body.raw_data)
    assert len(json.dumps(stored)) > MAX_BODY_CHARS  # the markup is stored

    resend = [{"type": b["type"], "value": b["value"]} for b in stored]
    resp = _client(user).patch(
        f"/forum/posts/{post.id}/", {"body": resend}, format="json"
    )
    assert resp.status_code == 200, resp.data
    post.refresh_from_db()
    assert [b["value"] for b in post.body.raw_data] == [b["value"] for b in stored]

    # A body stored before todo 448 item 13 has no target="_blank": an edit
    # adds 16 characters per link, and must still save.
    legacy = [
        {"type": b["type"], "value": b["value"].replace(' target="_blank"', "")}
        for b in stored
    ]
    resp = _client(user).patch(
        f"/forum/posts/{post.id}/", {"body": legacy}, format="json"
    )
    assert resp.status_code == 200, resp.data
    post.refresh_from_db()
    assert [b["value"] for b in post.body.raw_data] == [b["value"] for b in stored]


@pytest.mark.django_db
def test_item2_the_markup_words_typed_as_text_buy_no_room():
    """Only the attributes on a real ``<a>`` start tag are discounted: the
    same words typed in prose count in full."""
    from wagtail_forum.api.sanitize import MAX_BODY_CHARS

    padding = ' target="_blank" rel="noopener noreferrer nofollow"' * 200
    body = _sized_body(MAX_BODY_CHARS + 100, padding)

    resp = _create(_client(_member()), _board(), body)

    assert resp.status_code == 400
    assert "too large" in str(resp.data)


def test_item2_the_measure_discounts_only_server_link_markup_and_card_fields():
    from wagtail_forum.api.sanitize import (
        MAX_BODY_MARKUP_TOLERANCE,
        _measured_body_chars,
    )

    rich, links = {"paragraph"}, {"link_preview"}
    marked = ' target="_blank" rel="noopener noreferrer nofollow"'
    markup = len(json.dumps(marked)) - 2

    # A real link: its server attributes are not counted.
    anchor = [_paragraph(f'<p><a href="https://x.example/"{marked}>x</a></p>')]
    assert _measured_body_chars(anchor, rich, links) == (
        len(json.dumps(anchor)) - markup
    )
    # The same words as text, or in a heading: counted in full.
    for block in (
        _paragraph(f"<p>{marked}</p>"),
        {"type": "heading", "value": f"<a{marked}>"},
    ):
        assert _measured_body_chars([block], rich, links) == len(json.dumps([block]))
    # The discount is bounded.
    many = [_paragraph(f'<p><a href="https://x.example/"{marked}>x</a></p>' * 1_000)]
    assert 1_000 * markup > MAX_BODY_MARKUP_TOLERANCE
    assert _measured_body_chars(many, rich, links) == (
        len(json.dumps(many)) - MAX_BODY_MARKUP_TOLERANCE
    )
    # A card counts as its URL alone.
    card = {"type": "link_preview", "value": _card("https://c.example/", "c.example")}
    assert _measured_body_chars([card], rich, links) == len(
        json.dumps([{"type": "link_preview", "value": {"url": "https://c.example/"}}])
    )


def full_fetcher(url, *, deadline=None):
    """A snapshot with every field at its stored cap: the largest card."""
    from wagtail_forum import link_previews

    _record(url)
    return {
        "title": "t" * link_previews.TITLE_MAX_LENGTH,
        "description": "d" * link_previews.DESCRIPTION_MAX_LENGTH,
        "site_name": "s" * link_previews.SITE_NAME_MAX_LENGTH,
        "domain": "full.example",
        "image": "",
    }


@pytest.mark.django_db
@_fetcher("full_fetcher")
@pytest.mark.parametrize("as_card", [False, True], ids=["paragraphs", "resent-cards"])
def test_item1_a_link_repeated_in_every_block_gets_one_card(as_card):
    """Every size check counts a card as its URL alone, which is honest
    only while the cards are capped. A URL repeated in all 100 blocks gets
    ONE card, fetched once; every repeat is stored as its link, so the
    stored body stays within the cap the measure checked."""
    from wagtail_forum.api.sanitize import MAX_BODY_BLOCKS, MAX_BODY_CHARS

    url = "https://full.example/page"
    if as_card:
        block = {"type": "link_preview", "value": {"url": url, "image_url": None}}
    else:
        block = _paragraph(url)

    resp = _create(_client(_member()), _board(), [block] * MAX_BODY_BLOCKS)

    assert resp.status_code == 201, resp.data
    stored = _stored()
    assert [kind for kind, _ in stored] == ["link_preview"] + ["paragraph"] * (
        MAX_BODY_BLOCKS - 1
    )
    assert stored[0][1]["title"] == "t" * 200
    # A resent card falls back to its link wrapped in a <p>, as every
    # card that cannot be a card does.
    link = f"<p>{_linked(url)}</p>" if as_card else _linked(url)
    assert set(stored[1:]) == {("paragraph", link)}
    assert CALLS == [url]
    assert len(json.dumps(list(Post.objects.get().body.raw_data))) < MAX_BODY_CHARS


@pytest.mark.parametrize(
    "url, host",
    [
        ("https://example.com/secret?token=1", "example.com"),
        ("http://ex\x1bample.com/", "'ex\\x1bample.com'"),
        ("http://" + "a" * 600 + "/", repr("a" * 253)),
        (None, "?"),
        ("not a url", "?"),
        # Todo 539 item 6: only hostname and IP characters are logged bare.
        ("http://a b.example/", "'a b.example'"),
        ("http://host=evil/", "'host=evil'"),
        ("http://[::1]:8080/", "::1"),
        ("http://93.184.216.34/", "93.184.216.34"),
        ("https://my_host.example/", "my_host.example"),
    ],
    ids=[
        "plain",
        "control-character",
        "too-long",
        "not-a-string",
        "no-host",
        "space",
        "equals",
        "ipv6",
        "ipv4",
        "underscore",
    ],
)
def test_item7_log_host_names_only_a_safe_host(url, host):
    from wagtail_forum.link_previews import log_host

    assert log_host(url) == host


@pytest.mark.django_db
def test_item8_fetch_snapshots_logs_the_host_not_the_url():
    import unittest

    from wagtail_forum.link_previews import fetch_snapshots

    with unittest.TestCase().assertLogs("wagtail_forum", "WARNING") as logged:
        assert (
            fetch_snapshots(raising_fetcher, ["https://a.example/secret?token=1"]) == {}
        )

    lines = [r.getMessage() for r in logged.records]
    assert lines == ["[LINK_PREVIEW] fetcher raised for host a.example"]


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_LINK_PREVIEW_FETCH_TIMEOUT_SECONDS=0.2)
def test_item8_a_slow_or_queued_fetch_logs_the_host_not_the_url(
    one_worker_pool, first_fetch_started
):
    import unittest

    from wagtail_forum.link_previews import fetch_snapshots

    release = threading.Event()

    def blocking_fetcher(url, *, deadline=None):
        first_fetch_started.set()
        release.wait(5)
        return {"title": url}

    try:
        with unittest.TestCase().assertLogs("wagtail_forum", "WARNING") as logged:
            fetch_snapshots(
                blocking_fetcher,
                ["https://a.example/secret?t=1", "https://b.example/secret?t=2"],
            )
    finally:
        release.set()
    one_worker_pool.shutdown(wait=True)

    lines = sorted(r.getMessage() for r in logged.records)
    assert lines == [
        "[LINK_PREVIEW] fetch never started in 0.2s (pool busy), "
        "saving as a link to host b.example",
        "[LINK_PREVIEW] fetch still running after 0.2s, "
        "saving as a link to host a.example",
    ]


# --- todo 539: follow-ups from PR #978's reviews --------------------------------


def _body_types():
    from wagtail.blocks import RichTextBlock
    from wagtail_forum.blocks import ForumBodyBlock, LinkPreviewBlock

    blocks = ForumBodyBlock().child_blocks.items()
    return (
        {name for name, block in blocks if isinstance(block, RichTextBlock)},
        {name for name, block in blocks if isinstance(block, LinkPreviewBlock)},
    )


def _pre_fetch_measure(body):
    """What the size check before the fetch measured BEFORE todo 539: every
    resent card as its paragraph, an image as sent."""
    from wagtail_forum.api.sanitize import _measured_body_chars, _stored_without_cards

    rich, links = _body_types()
    return _measured_body_chars(_stored_without_cards(body, rich, links), rich, links)


def _filled_to_cap(tail):
    """``[filler paragraph] + tail``, the filler sized so that the old
    pre-fetch measure of the body is exactly ``MAX_BODY_CHARS``."""
    from wagtail_forum.api.sanitize import MAX_BODY_CHARS

    filler = "m" * 1_000
    body = [_paragraph(f"<p>{filler}</p>")] + tail
    filler += "m" * (MAX_BODY_CHARS - _pre_fetch_measure(body))
    body = [_paragraph(f"<p>{filler}</p>")] + tail
    assert _pre_fetch_measure(body) == MAX_BODY_CHARS
    return body


@pytest.mark.django_db
@_fetcher("none_fetcher")
def test_539_item1_each_rich_text_value_is_auto_linked_once(monkeypatch):
    """The size check before the fetch and the cleaned pass share one
    auto-link per distinct value; before, every block was auto-linked twice."""
    from wagtail_forum.api import sanitize

    seen = []
    real = sanitize.autolink_rich_text

    def counting(html_fragment):
        seen.append(html_fragment)
        return real(html_fragment)

    monkeypatch.setattr(sanitize, "autolink_rich_text", counting)

    resp = _create(
        _client(_member()),
        _board(),
        [
            _paragraph("<p>See https://a.example/ for more.</p>"),
            _paragraph("<p>Plain words.</p>"),
            # No card (the fetcher answers None): stored as its link.
            _paragraph("https://b.example/"),
            {"type": "link_preview", "value": {"url": "https://c.example/"}},
        ],
    )

    assert resp.status_code == 201, resp.data
    assert len(seen) == len(set(seen)) == 4


@pytest.mark.django_db
def test_539_item2_a_near_cap_card_from_a_bare_link_resends_unchanged():
    """The card came from a bare-URL paragraph (the mobile composer sends no
    ``<p>``), in a body at the cap. Resent as the read envelope, the card is
    a card the stored body already has: measured as its URL, as when it was
    stored, not as a ``<p>``-wrapped link 7 characters longer, which
    refused the edit."""
    from wagtail_forum.api.sanitize import MAX_BODY_CHARS

    url = "https://example.com/"
    user = _member()
    body = _filled_to_cap([_paragraph(url)])
    with _fetcher("fake_fetcher"):
        assert _create(_client(user), _board(), body).status_code == 201
    post = Post.objects.get()
    stored = list(post.body.raw_data)
    assert stored[1]["type"] == "link_preview"
    resent = [
        {"type": "paragraph", "value": stored[0]["value"]},
        {"type": "link_preview", "value": {**stored[1]["value"], "image_url": None}},
    ]
    # The old measure refused exactly this resend.
    assert _pre_fetch_measure(resent) > MAX_BODY_CHARS
    CALLS.clear()

    with _fetcher("raising_fetcher"):
        resp = _client(user).patch(
            f"/forum/posts/{post.id}/", {"body": resent}, format="json"
        )

    assert resp.status_code == 200, resp.data
    post.refresh_from_db()
    assert _stored(post)[1] == ("link_preview", _card(url, "example.com"))
    assert CALLS == []


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_539_item3_a_legacy_image_is_measured_as_stored_before_any_fetch():
    """A bare-PK image is stored as the ImageBlock dict, alt recovered from
    the image's description. The check before the fetch measures that, so a
    body it puts over the cap is refused without fetching the card."""
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.collections import get_forum_image_collection

    user = _member()
    image = get_image_model().objects.create(
        title="seedling",
        file=get_test_image_file(),
        collection=get_forum_image_collection(),
        uploaded_by_user=user,
        description="a" * 250,
    )
    body = _filled_to_cap(
        [{"type": "image", "value": image.id}, _paragraph("https://card.example/")]
    )

    resp = _create(_client(user), _board(), body)

    assert resp.status_code == 400
    assert "too large" in str(resp.data)
    assert CALLS == []


@pytest.mark.django_db
@_fetcher("fake_fetcher")
@override_settings(
    WAGTAILFORUM_ALLOW_EMBED_BLOCKS=True, WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS
)
def test_539_item3_a_refused_body_costs_no_provider_fetch(monkeypatch):
    warmed = []
    monkeypatch.setattr("wagtail_forum.api.sanitize.warm_embeds", warmed.append)

    resp = _create(
        _client(_member()),
        _board(),
        [
            _paragraph("https://youtu.be/dQw4w9WgXcQ"),
            {"type": "image", "value": 999999},
        ],
    )

    assert resp.status_code == 400
    assert warmed == []


@pytest.mark.django_db
@_fetcher("fake_fetcher")
@override_settings(
    WAGTAILFORUM_ALLOW_EMBED_BLOCKS=True, WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS
)
def test_539_item3_an_accepted_body_still_warms_its_embeds(monkeypatch):
    warmed = []
    monkeypatch.setattr("wagtail_forum.api.sanitize.warm_embeds", warmed.append)

    resp = _create(
        _client(_member()), _board(), [_paragraph("https://youtu.be/dQw4w9WgXcQ")]
    )

    assert resp.status_code == 201, resp.data
    assert warmed == [["https://youtu.be/dQw4w9WgXcQ"]]


def test_539_item4_a_raw_angle_bracket_in_a_link_keeps_its_discount():
    """nh3 leaves a raw ``>`` (and ``<``) inside a quoted attribute value;
    the start tag ends at the first ``>`` outside quotes."""
    from wagtail_forum.api.sanitize import _server_markup_chars, sanitize_rich_text

    marked = ' target="_blank" rel="noopener noreferrer nofollow"'
    markup = len(json.dumps(marked)) - 2
    for href in ("https://x.example/?q=a>b", "https://x.example/?q=a<b"):
        cleaned = sanitize_rich_text(f'<p><a href="{href}" title="c>d">x</a></p>')
        assert href in cleaned
        assert _server_markup_chars(cleaned) == markup


def _backtracking_repeats(parsed):
    """Every greedy or lazy (so backtracking) repeat in a parsed pattern.

    Walks every node that holds a sub-pattern (todo 550 item 4): an
    ATOMIC_GROUP's argument is the sub-pattern itself, not a tuple ending in
    one, and a repeat inside a lookaround or a conditional backtracks too."""
    from re import _constants as sre

    found = []
    for op, av in parsed:
        if op in (sre.MAX_REPEAT, sre.MIN_REPEAT):
            found.append(op)
        if op in (sre.MAX_REPEAT, sre.MIN_REPEAT, sre.POSSESSIVE_REPEAT):
            found += _backtracking_repeats(av[2])
        elif op == sre.BRANCH:
            for branch in av[1]:
                found += _backtracking_repeats(branch)
        elif op == sre.SUBPATTERN:
            found += _backtracking_repeats(av[-1])
        elif op == sre.ATOMIC_GROUP:
            found += _backtracking_repeats(av)
        elif op in (sre.ASSERT, sre.ASSERT_NOT):
            found += _backtracking_repeats(av[1])
        elif op == sre.GROUPREF_EXISTS:
            for arm in av[1:]:
                if arm is not None:
                    found += _backtracking_repeats(arm)
    return found


@pytest.mark.parametrize(
    "pattern, repeats",
    [
        ("(a*)", 1),
        ("(?>a*)", 1),
        ("(?>a)", 0),
        ("(?=a*)", 1),
        ("(?!a*?)", 1),
        ("(?<=a)", 0),
        ("(a)(?(1)a*|b*)", 2),
        ("(a)(?(1)a*)", 1),
        ("a*+", 0),
        # Nested repeats and alternation (todo 576 item 3): the recursion
        # through MAX_REPEAT, POSSESSIVE_REPEAT and BRANCH is pinned too.
        ("(?:a*)*", 2),
        ("(?:a*)*+", 1),
        ("a*|b*", 2),
        ("(?:a*|b*)*", 3),
    ],
)
def test_550_item4_the_repeat_walk_reaches_every_sub_pattern(pattern, repeats):
    """The linearity guard below must see a backtracking repeat wherever the
    pattern nests it: before, an atomic group raised TypeError and a repeat
    inside a lookaround or a conditional went unseen."""
    from re import _parser

    assert len(_backtracking_repeats(_parser.parse(pattern, 0))) == repeats


def test_539_item4_the_anchor_scan_of_raw_input_is_linear():
    """The measure runs on the raw client body. The old pattern
    ``<a\\b[^>]*>`` scanned to the end of the string from every ``<a``:
    about 4 s for this input.

    Counted, not timed (todo 545 item 3): with no backtracking repeat, a
    failed attempt at a ``<a`` costs exactly the span the pattern minus its
    closing ``>`` matches there, so the sum of those spans is the scan's
    work. ``re._parser`` is private API; the venv pins the interpreter."""
    import re
    from re import _parser

    from wagtail_forum.api.sanitize import (
        _ANCHOR_START_TAG,
        MAX_BODY_RAW_CHARS,
        _server_markup_chars,
    )

    pattern = _ANCHOR_START_TAG.pattern
    assert _backtracking_repeats(_parser.parse(pattern, _ANCHOR_START_TAG.flags)) == []
    assert pattern.endswith(">")
    scan = re.compile(pattern[:-1], _ANCHOR_START_TAG.flags)

    for chunk in ("<a ", '<a "', '<a "<a '):
        raw = chunk * (MAX_BODY_RAW_CHARS // len(chunk))
        budget = 4 * len(raw)
        work = 0
        for start in range(len(raw)):
            attempt = scan.match(raw, start)
            if attempt:
                work += attempt.end() - start
                assert work <= budget, f"quadratic scan of {chunk!r} * n"
        assert _server_markup_chars(raw) == 0


# --- a link on its own line is split out (todo 655) ---------------------

WEB_SPLIT = "<p>Intro</p><p>https://example.com/a</p><p>Outro</p>"
MOBILE_SPLIT = "Intro<br>https://example.com/a<br>Outro"


@pytest.mark.django_db
@_fetcher("fake_fetcher")
@pytest.mark.parametrize(
    ("html", "intro", "outro"),
    [
        (WEB_SPLIT, "<p>Intro</p>", "<p>Outro</p>"),
        (MOBILE_SPLIT, "Intro", "Outro"),
        # One web paragraph with hard breaks (Shift+Enter).
        (
            "<p>Intro<br>https://example.com/a<br>Outro</p>",
            "<p>Intro</p>",
            "<p>Outro</p>",
        ),
    ],
)
def test_655_a_link_line_between_text_is_stored_as_its_own_card(html, intro, outro):
    resp = _create(_client(_member()), _board(), [_paragraph(html)])

    assert resp.status_code == 201, resp.data
    assert _stored() == [
        ("paragraph", intro),
        ("link_preview", _card("https://example.com/a", "example.com")),
        ("paragraph", outro),
    ]
    assert CALLS == ["https://example.com/a"]


def _link_lines(urls):
    return "<br>".join(["Five favourite plant sites:", *urls, "Enjoy."])


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_655_five_link_lines_from_an_untrusted_author_publish_as_five_cards():
    """Under the default spam limit (5, owner decision 2026-10-17), a post
    carrying all five cards is not held, even from a NEW member whose post
    the heuristic screens; a sixth link is."""
    from wagtail_forum.workflow import ensure_default_workflow

    ensure_default_workflow()
    board = _board()
    author = User.objects.create_user(username="newbie")
    assert ForumProfile.for_user(author).trust_level == TrustLevel.NEW
    urls = [f"https://site{n}.example/" for n in range(6)]

    five = _create(_client(author), board, [_paragraph(_link_lines(urls[:5]))])
    assert five.status_code == 201, five.data
    assert five.data["status"] == "published"
    kinds = [kind for kind, _ in _stored()]
    assert kinds == ["paragraph"] + ["link_preview"] * 5 + ["paragraph"]

    six = _create(
        _client(author), board, [_paragraph(_link_lines(urls))], slug="six-links"
    )
    assert six.status_code == 201, six.data
    assert six.data["status"] == "pending"


@pytest.mark.django_db
@_fetcher("fake_fetcher")
@override_settings(
    WAGTAILFORUM_ALLOW_EMBED_BLOCKS=True, WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS
)
def test_655_a_sixth_link_line_stays_a_link_and_a_video_line_embeds(monkeypatch):
    monkeypatch.setattr("wagtail_forum.api.sanitize.warm_embeds", lambda urls: None)
    urls = [f"https://site{n}.example/" for n in range(6)]
    video = "https://youtu.be/dQw4w9WgXcQ"

    resp = _create(
        _client(_member()), _board(), [_paragraph(_link_lines([*urls, video]))]
    )

    assert resp.status_code == 201, resp.data
    stored = _stored()
    assert [kind for kind, _ in stored] == (
        ["paragraph"] + ["link_preview"] * 5 + ["paragraph", "embed", "paragraph"]
    )
    # The sixth stays a tappable link, never fetched; the video embeds.
    assert stored[6] == ("paragraph", _linked(urls[5]))
    assert stored[7] == ("embed", video)
    assert sorted(CALLS) == sorted(urls[:5])


@pytest.mark.django_db
@_fetcher("fake_fetcher")
@pytest.mark.parametrize(
    "html",
    [
        "<p>Read https://example.com/a first.</p><p>Outro</p>",
        "Read https://example.com/a first.<br>Outro",
        "<ul><li>https://example.com/a</li></ul><p>Outro</p>",
        "<ol><li><p>https://example.com/a</p></li></ol><p>Outro</p>",
        "<p><code>https://example.com/a</code></p><p>Outro</p>",
        "Intro<br><code>https://example.com/a</code><br>Outro",
        "<pre>https://example.com/a</pre><p>Outro</p>",
        "<blockquote>https://example.com/a</blockquote><p>Outro</p>",
        "<blockquote><p>https://example.com/a</p></blockquote><p>Outro</p>",
    ],
)
def test_655_a_url_in_a_sentence_list_code_or_quote_is_not_split_out(html):
    resp = _create(_client(_member()), _board(), [_paragraph(html)])

    assert resp.status_code == 201, resp.data
    assert [kind for kind, _ in _stored()] == ["paragraph"]
    assert CALLS == []


@pytest.mark.parametrize(
    "html",
    [
        "<p>Plain prose, <strong>bold</strong> and <em>italic</em>.</p><p>More.</p>",
        "Line one<br>Line two with https://example.com/a inside<br><br>Line three",
        "<ul><li>https://example.com/a</li><li>b</li></ul>",
        "<p><code>https://example.com/a</code></p>",
        # A paragraph that IS one link is not split either (it is carded whole).
        "https://example.com/a",
        "<p>https://example.com/a</p>",
        "<p><a href='https://example.com/a'>https://example.com/a</a></p><br>",
        "",
    ],
)
def test_655_a_paragraph_with_no_link_line_is_left_unchanged(html):
    from wagtail_forum.api.sanitize import _split_link_paragraphs

    block = {"type": "paragraph", "value": html, "id": "kept"}
    split = _split_link_paragraphs([block])

    assert split == [block]
    assert split[0] is block  # the very same block: byte for byte


def test_655_the_first_piece_keeps_the_block_id_and_no_id_is_duplicated():
    from wagtail_forum.api.sanitize import _split_link_paragraphs

    split = _split_link_paragraphs(
        [{"type": "paragraph", "value": MOBILE_SPLIT, "id": "kept"}]
    )

    assert split == [
        {"type": "paragraph", "value": "Intro", "id": "kept"},
        {"type": "paragraph", "value": "https://example.com/a"},
        {"type": "paragraph", "value": "Outro"},
    ]


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_657_a_near_cap_body_with_a_link_line_saves_whole():
    """A body that fits ``MAX_BODY_BLOCKS`` saved before the split existed,
    so the split must never refuse it (todo 657, replacing todo 655's
    "split past the cap is refused"): 99 paragraphs plus one that would
    split into three is stored as 100 blocks, that paragraph whole."""
    body = [_paragraph(f"<p>Line {n}</p>") for n in range(99)]
    body.append(_paragraph(MOBILE_SPLIT))

    resp = _create(_client(_member()), _board(), body)

    assert resp.status_code == 201, resp.data
    stored = _stored()
    assert len(stored) == 100
    assert stored[-1][0] == "paragraph"
    assert "Intro" in stored[-1][1]
    assert "https://example.com/a" in stored[-1][1]
    assert "Outro" in stored[-1][1]
    assert not any(kind == "link_preview" for kind, _ in stored)
    assert CALLS == []


@pytest.mark.django_db
@_fetcher("fake_fetcher")
def test_657_the_split_uses_what_the_cap_leaves_and_no_more():
    """96 paragraphs leave room for two more blocks: the first link
    paragraph splits (+2) and its link becomes a card; the second stays
    whole, its link an ordinary line, and nothing fetches it."""
    body = [_paragraph(f"<p>Line {n}</p>") for n in range(96)]
    body.append(_paragraph(MOBILE_SPLIT))
    body.append(_paragraph("Before<br>https://example.com/b<br>After"))

    resp = _create(_client(_member()), _board(), body)

    assert resp.status_code == 201, resp.data
    stored = _stored()
    assert len(stored) == 100
    assert [kind for kind, _ in stored[96:99]] == [
        "paragraph",
        "link_preview",
        "paragraph",
    ]
    assert stored[97][1]["url"] == "https://example.com/a"
    assert stored[99][0] == "paragraph"
    assert "https://example.com/b" in stored[99][1]
    assert CALLS == ["https://example.com/a"]


def test_657_split_link_paragraphs_never_exceeds_the_budget():
    """A declined split frees the slots its links took, so a later sole
    link line that fits the budget still splits out."""
    from wagtail_forum.api.sanitize import _split_link_paragraphs

    value = [
        {"type": "paragraph", "value": MOBILE_SPLIT},
        {"type": "paragraph", "value": "https://example.com/a<br>Tail"},
    ]
    split = _split_link_paragraphs(value, budget=1)

    assert split == [
        {"type": "paragraph", "value": MOBILE_SPLIT},
        {"type": "paragraph", "value": "https://example.com/a"},
        {"type": "paragraph", "value": "Tail"},
    ]


@pytest.mark.django_db
@_fetcher("fake_fetcher")
@pytest.mark.parametrize(
    "html",
    [
        # One paragraph of 101 URL lines.
        "<br>".join(f"https://site{n}.example/" for n in range(101)),
        # 50 link lines, each between lines of text.
        "<br>".join(
            line
            for n in range(50)
            for line in (f"Site {n}:", f"https://site{n}.example/")
        )
        + "<br>The end.",
    ],
)
def test_655_a_wall_of_link_lines_still_saves(html):
    """A wall of links saved as one block before the split existed, so the
    split must never turn it into a 400: only the link lines that can still
    become a card are split out (the first five distinct), the rest stay
    lines of their paragraph."""
    resp = _create(_client(_member()), _board(), [_paragraph(html)])

    assert resp.status_code == 201, resp.data
    stored = _stored()
    assert len(stored) <= 12
    cards = [value["url"] for kind, value in stored if kind == "link_preview"]
    assert cards == [f"https://site{n}.example/" for n in range(5)]
    assert sorted(CALLS) == sorted(cards)


def test_655_a_repeated_or_over_cap_link_line_is_not_split_out():
    from wagtail_forum.api.sanitize import _split_link_paragraphs

    urls = [f"https://site{n}.example/" for n in range(6)]
    split = _split_link_paragraphs(
        [
            {"type": "link_preview", "value": {"url": urls[0]}},
            {"type": "paragraph", "value": "<br>".join(["Intro", *urls, urls[1]])},
        ]
    )

    # urls[0] is already a card and urls[5] is past the cap of five, so both
    # stay lines of a run; the repeat of urls[1] does too.
    assert [block["value"] for block in split[1:]] == [
        f"Intro<br>{urls[0]}",
        urls[1],
        urls[2],
        urls[3],
        urls[4],
        f"{urls[5]}<br>{urls[1]}",
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("written", "resent"),
    [
        # Web: bodyBlocksToDoc -> docToBodyBlocks merges the split post back
        # into ONE paragraph, with the card as its link (the exact HTML pinned
        # by web/src/utils/forumBody.test.ts, todo 655).
        (
            WEB_SPLIT,
            '<p>Intro</p><p><a target="_blank" rel="noopener noreferrer" '
            'class="text-primary hover:underline" href="https://example.com/a">'
            "https://example.com/a</a></p><p>Outro</p>",
        ),
        # Mobile: ForumComposeArgs.edit rebuilds "Intro\nurl\nOutro", which
        # buildParagraphBody sends back <br>-joined (pinned by
        # forum_composer_link_preview_test.dart).
        (MOBILE_SPLIT, MOBILE_SPLIT),
        ("Intro<br><br>https://example.com/a<br><br>Outro",) * 2,
    ],
)
def test_655_an_unchanged_resave_of_a_split_post_stores_the_same_body(written, resent):
    user = _member()
    with _fetcher("fake_fetcher"):
        _create(_client(user), _board(), [_paragraph(written)])
    post = Post.objects.get()
    before = _stored(post)
    assert [kind for kind, _ in before] == ["paragraph", "link_preview", "paragraph"]
    CALLS.clear()

    with _fetcher("raising_fetcher"):
        resp = _client(user).patch(
            f"/forum/posts/{post.id}/",
            {"body": [_paragraph(resent)]},
            format="json",
        )

    assert resp.status_code == 200, resp.data
    post.refresh_from_db()
    assert _stored(post) == before
    assert CALLS == []
