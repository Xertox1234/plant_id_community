"""Shared test factories for forum structure (todo 665).

Boards were Wagtail pages (``index.add_child(instance=ForumBoard(...))``) until
todo 665 replaced them with ``Forum`` rows. Every test that needs a board now
calls :func:`make_forum`, which parents it under a category, so no test has to
know that a forum must belong to one.
"""

from wagtail_forum.models import Forum
from wagtail_forum.services.forum_permissions import hide_for_everyone

DEFAULT_CATEGORY_SLUG = "test-category"


def make_category(
    name="Plants", slug=DEFAULT_CATEGORY_SLUG, *, is_hidden=False, **fields
):
    """The category with ``slug``, created on first use (category slugs are
    unique among categories). ``is_hidden=True`` gives it the "No access for
    everyone" grants that replaced the flag (todo 676)."""
    category, created = Forum.objects.get_or_create(
        forum_type=Forum.CATEGORY,
        slug=slug,
        defaults={"name": name, **fields},
    )
    if is_hidden and created:
        hide_forum(category)
    return category


def make_forum(
    name="General", slug="general", *, category=None, is_hidden=False, **fields
):
    """A visible ``forum_type="forum"`` row under ``category`` (the shared test
    category when omitted). Extra ``fields`` (``description``, ``position``,
    counters) pass straight to the model; ``is_hidden=True`` hides it with
    grants (``hide_forum``)."""
    forum = Forum.objects.create(
        forum_type=Forum.FORUM,
        parent=category if category is not None else make_category(),
        name=name,
        slug=slug,
        **fields,
    )
    if is_hidden:
        hide_forum(forum)
    return forum


def hide_forum(forum):
    """Make ``forum`` invisible to the API: *No access* for guests and
    members, what the old ``is_hidden`` flag became (todo 676). Staff and
    moderators still see it. Replaces the page-era ``board.unpublish()`` /
    ``PageViewRestriction`` idioms (todo 665)."""
    hide_for_everyone(forum)
