"""The host's embed provider allowlist (todo 344): youtube + vimeo only."""

from wagtail.embeds.finders import get_finders


def test_host_allows_exactly_youtube_and_vimeo_embeds():
    from wagtail_forum.embeds import TimeoutOEmbedFinder

    finders = get_finders()
    assert len(finders) == 1  # one oEmbed finder, restricted providers
    assert isinstance(finders[0], TimeoutOEmbedFinder)  # socket timeout on every fetch

    def accepted(url):
        return any(f.accept(url) for f in finders)

    assert accepted("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert accepted("https://youtu.be/dQw4w9WgXcQ")
    assert accepted("https://vimeo.com/148751763")
    # Real oEmbed providers Wagtail knows about, deliberately NOT allowed here.
    assert not accepted("https://www.dailymotion.com/video/x1")
    assert not accepted("https://twitter.com/x/status/1")
    assert not accepted("https://www.tiktok.com/@x/video/1")
