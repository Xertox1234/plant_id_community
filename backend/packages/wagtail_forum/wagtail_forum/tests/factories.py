"""Shared test factories for forum structure (todo 665).

Boards were Wagtail pages (``index.add_child(instance=ForumBoard(...))``) until
todo 665 replaced them with ``Forum`` rows. Every test that needs a board now
calls :func:`make_forum`, which parents it under a category, so no test has to
know that a forum must belong to one.
"""

from wagtail_forum.models import Forum

DEFAULT_CATEGORY_SLUG = "test-category"


def make_category(name="Plants", slug=DEFAULT_CATEGORY_SLUG, **fields):
    """The category with ``slug``, created on first use (category slugs are
    unique among categories)."""
    category, _ = Forum.objects.get_or_create(
        forum_type=Forum.CATEGORY,
        slug=slug,
        defaults={"name": name, **fields},
    )
    return category


def make_forum(name="General", slug="general", *, category=None, **fields):
    """A visible ``forum_type="forum"`` row under ``category`` (the shared test
    category when omitted). Extra ``fields`` (``description``, ``is_hidden``,
    ``position``, counters) pass straight to the model."""
    return Forum.objects.create(
        forum_type=Forum.FORUM,
        parent=category if category is not None else make_category(),
        name=name,
        slug=slug,
        **fields,
    )


def hide_forum(forum):
    """Make ``forum`` invisible to the API (``is_hidden``). Replaces the
    page-era ``board.unpublish()`` / ``PageViewRestriction`` idioms, which hid a
    board the same way (todo 665)."""
    Forum.objects.filter(pk=forum.pk).update(is_hidden=True)
    forum.is_hidden = True
