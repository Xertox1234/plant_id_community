"""Safe delete and type change for forum rows (todo 667; spec 2026-10-28 §2).

phpBB asks *move topics to [forum]* or *delete topics* before a forum goes,
but never checks the target server-side; every function here does
(:func:`validate_topic_target`, :func:`validate_forum_target`). Each runs in
one transaction, so a refused or failed step leaves the structure as it was.

- :func:`empty_forum` moves or deletes a forum's topics so the row can be
  deleted or turned into a category (``Topic.board`` is ``PROTECT``).
- :func:`empty_category` moves a category's forums under another category.
- :func:`change_type` moves a row between category, forum and link (link
  conversions: todo 670).

Moving topics is a bulk UPDATE, which fires no model signal: this module
recounts both forums itself and sends ``signals.topics_moved`` so a host can keep
old topic URLs working (``apps/forum_host/redirects.py`` writes the redirect
rows). Deleting goes through ``Topic.delete()`` one topic at a time, so the
package's own delete receivers recount profiles and write the sync tombstones
exactly as a moderator's delete does.
"""

from __future__ import annotations

from typing import Literal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, Max, QuerySet, Value, When
from django.utils import timezone
from django.utils.translation import gettext as _
from wagtail.models import Revision

from ..models import Forum, Topic
from ..signals import _refresh_board_counters, topics_moved

TopicsAction = Literal["move", "delete"]
MOVE: TopicsAction = "move"
DELETE: TopicsAction = "delete"

# Rows per UPDATE when rewriting stored revisions.
_REVISION_BATCH_SIZE = 500


def validate_topic_target(source: Forum, target: Forum | None) -> Forum:
    """The forum ``source``'s topics may move to: an existing ``forum`` row
    that is not ``source`` itself (never a category or a link, which hold no
    topics)."""
    if target is None or target.pk is None:
        raise ValidationError(_("Choose the forum to move the topics to."))
    fresh = Forum.objects.filter(pk=target.pk).first()
    if fresh is None:
        raise ValidationError(_("That forum no longer exists."))
    if fresh.pk == source.pk:
        raise ValidationError(_("Topics cannot be moved to the forum being emptied."))
    if fresh.forum_type != Forum.FORUM:
        raise ValidationError(_("Topics can only be moved to a forum."))
    return fresh


def validate_forum_target(source: Forum, target: Forum | None) -> Forum:
    """The category ``source``'s forums may move to: an existing category
    that is not ``source`` itself."""
    if target is None or target.pk is None:
        raise ValidationError(_("Choose the category to move the forums to."))
    fresh = Forum.objects.filter(pk=target.pk).first()
    if fresh is None:
        raise ValidationError(_("That category no longer exists."))
    if fresh.pk == source.pk:
        raise ValidationError(
            _("Forums cannot be moved to the category being emptied.")
        )
    if fresh.forum_type != Forum.CATEGORY:
        raise ValidationError(_("Forums can only be moved to a category."))
    return fresh


def next_position(parent_id: int | None) -> int:
    """The position after the last row of a level: categories among
    categories (``parent_id`` None), forums and links within their category."""
    siblings = Forum.objects.filter(parent_id=parent_id)
    if parent_id is None:
        siblings = siblings.filter(forum_type=Forum.CATEGORY)
    last = siblings.aggregate(last=Max("position"))["last"]
    return 0 if last is None else last + 1


def _level(parent_id: int | None) -> QuerySet[Forum]:
    """The rows of one level, in display order: the categories (``parent_id``
    None) or the forums and links of one category."""
    rows = Forum.objects.filter(parent_id=parent_id)
    if parent_id is None:
        rows = rows.filter(forum_type=Forum.CATEGORY)
    return rows.order_by("position", "pk")


def move_forum(forum_id: int, parent_id: int | None, position: int) -> Forum:
    """Put row ``forum_id`` at index ``position`` under ``parent_id`` (None:
    the category level) and renumber both the level it left and the level it
    joined 0..n-1, in one transaction (the structure tree's drag and drop and
    its move buttons, todo 668; spec 2026-10-28 §5).

    The type and parent rules are ``Forum.clean``'s: a category stays at the
    top level, a forum or link sits in a category, and only a category holds
    rows. ``position`` past the end of the level means the end. A forum that
    leaves a hidden category for a visible one is hidden, as
    :func:`empty_category` does, so a drag never publishes it."""
    if position < 0:
        raise ValidationError(_("The position must be zero or more."))
    with transaction.atomic():
        forum = Forum.objects.select_for_update().filter(pk=forum_id).first()
        if forum is None:
            raise Forum.DoesNotExist(_("That row no longer exists."))
        old_parent_id = forum.parent_id
        parent = None
        if parent_id is not None:
            parent = Forum.objects.select_for_update().filter(pk=parent_id).first()
            if parent is None:
                raise ValidationError(_("That category no longer exists."))
            if parent.pk == forum.pk:
                raise ValidationError(_("A row cannot be placed inside itself."))
        old_parent = forum.parent if old_parent_id is not None else None
        forum.parent = parent
        try:
            # Only the parent rules: a move changes nothing else, and a link
            # saved without a URL before todo 670 must still move.
            forum._clean_parent()
        except ValidationError as error:
            # Forum.clean reports on the "parent" field; the tree has no
            # field to show it on, so the caller gets the plain messages.
            raise ValidationError(error.messages) from error

        # Lock both levels (each in pk order) so two concurrent moves cannot
        # interleave their renumbering. The moved row and its parent are locked
        # first, so the order is not global: two staff moving rows into each
        # other's level at once can deadlock, and Postgres rolls one back.
        list(
            Forum.objects.select_for_update()
            .filter(pk__in=_level(parent_id).values("pk"))
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        if old_parent_id != parent_id:
            list(
                Forum.objects.select_for_update()
                .filter(pk__in=_level(old_parent_id).values("pk"))
                .order_by("pk")
                .values_list("pk", flat=True)
            )

        changed: list[Forum] = []
        siblings = [row for row in _level(parent_id) if row.pk != forum.pk]
        siblings.insert(min(position, len(siblings)), forum)
        if old_parent_id != parent_id:
            if (
                old_parent is not None
                and old_parent.is_hidden
                and parent is not None
                and not parent.is_hidden
            ):
                forum.is_hidden = True
            left = [row for row in _level(old_parent_id) if row.pk != forum.pk]
            for index, row in enumerate(left):
                if row.position != index:
                    row.position = index
                    changed.append(row)
        for index, row in enumerate(siblings):
            if row is forum or row.position != index:
                row.position = index
                changed.append(row)
        Forum.objects.bulk_update(changed, ["parent", "position", "is_hidden"])
    return forum


def _free_slug(slug: str, topic_id: int, taken: set[str]) -> str:
    """``slug`` made unique in ``taken`` with the topic's id (then a counter),
    kept inside the field's 255 characters."""
    max_length = Topic._meta.get_field("slug").max_length or 255
    suffix = f"-{topic_id}"
    n = 1
    while True:
        candidate = f"{slug[: max_length - len(suffix)]}{suffix}"
        if candidate not in taken:
            return candidate
        n += 1
        suffix = f"-{topic_id}-{n}"


def _rewrite_revisions(
    target: Forum, renamed: dict[int, tuple[str, str]], topic_ids: list[int]
) -> None:
    """Point the moved topics' stored revisions at ``target``.

    Publishing a revision restores every field it serialized, ``board`` and
    ``slug`` included (``Topic.with_content_json``), so a held or draft
    revision saved before the move would put the topic back on the old forum
    (a deleted row, or a category) or on a slug the target already uses."""
    topic_type = ContentType.objects.get_for_model(Topic)
    revisions = Revision.objects.filter(
        base_content_type=topic_type, object_id__in=[str(pk) for pk in topic_ids]
    ).only("pk", "object_id", "content")
    changed = []
    for revision in revisions.iterator(chunk_size=_REVISION_BATCH_SIZE):
        content = dict(revision.content)
        content["board"] = target.pk
        old_new = renamed.get(int(revision.object_id))
        if old_new is not None and content.get("slug") == old_new[0]:
            content["slug"] = old_new[1]
        if content != revision.content:
            revision.content = content
            changed.append(revision)
    Revision.objects.bulk_update(changed, ["content"], batch_size=_REVISION_BATCH_SIZE)


def move_topics(source: Forum, target: Forum) -> int:
    """Move every topic of ``source`` to ``target`` in one transaction and
    recount both forums. A topic whose slug the target already uses gets
    ``<slug>-<id>`` (``uniq_topic_slug_per_board``). Returns the count moved."""
    target = validate_topic_target(source, target)
    with transaction.atomic():
        rows = list(
            Topic.objects.select_for_update()
            .filter(board=source)
            .order_by("pk")
            .values_list("pk", "slug")
        )
        if not rows:
            return 0
        source_slugs = {slug for _pk, slug in rows}
        final = set(Topic.objects.filter(board=target).values_list("slug", flat=True))
        moves: list[tuple[int, str, str]] = []
        renamed: dict[int, tuple[str, str]] = {}
        for pk, slug in rows:
            new_slug = slug
            if slug in final:
                new_slug = _free_slug(slug, pk, final | source_slugs)
                renamed[pk] = (slug, new_slug)
            final.add(new_slug)
            moves.append((pk, slug, new_slug))
        now = timezone.now()
        if renamed:
            # Renamed while still in the source: no new slug is a source slug,
            # so this cannot clash there, and the board UPDATE below then
            # lands on a set of slugs unique in the target.
            Topic.objects.filter(pk__in=renamed).update(
                slug=Case(
                    *[
                        When(pk=pk, then=Value(new))
                        for pk, (_old, new) in renamed.items()
                    ]
                )
            )
        ids = [pk for pk, _slug in rows]
        # .update() skips auto_now; an unfiltered /sync/ finds moved topics by
        # it. A client syncing with ?board= never sees them leave (no tombstone).
        Topic.objects.filter(pk__in=ids).update(board=target, updated_at=now)
        _rewrite_revisions(target, renamed, ids)
        _refresh_board_counters(source.pk)
        _refresh_board_counters(target.pk)
        topics_moved.send(sender=Forum, source=source, target=target, moves=moves)
    return len(rows)


def delete_topics(source: Forum) -> int:
    """Delete every topic of ``source`` with its posts and everything that
    cascades from them. Returns the count deleted."""
    with transaction.atomic():
        topics = list(Topic.objects.select_for_update().filter(board=source))
        for topic in topics:
            topic.delete()
    return len(topics)


def empty_forum(
    forum: Forum, action: TopicsAction | None, target: Forum | None = None
) -> int:
    """Move (``MOVE``, to ``target``) or delete (``DELETE``) the topics of
    ``forum`` so it can be deleted or retyped. A forum with no topics needs
    no action. Returns the count of topics moved or deleted."""
    if not Topic.objects.filter(board=forum).exists():
        return 0
    if action == MOVE:
        return move_topics(forum, validate_topic_target(forum, target))
    if action == DELETE:
        return delete_topics(forum)
    raise ValidationError(_("Choose whether to move or delete this forum's topics."))


def empty_category(category: Forum, target: Forum | None) -> int:
    """Move the forums and links of ``category`` to the end of ``target``,
    keeping their order. Topic URLs carry no category, so nothing redirects.
    Forums inherit a hidden category's visibility, so leaving a hidden
    category for a visible one hides them rather than publishing them.
    A category with no forums needs no target. Returns the count moved."""
    with transaction.atomic():
        children = list(
            Forum.objects.select_for_update()
            .filter(parent=category)
            .order_by("position", "pk")
        )
        if not children:
            return 0
        target = validate_forum_target(category, target)
        start = next_position(target.pk)
        keep_hidden = category.is_hidden and not target.is_hidden
        for offset, child in enumerate(children):
            child.parent = target
            child.position = start + offset
            if keep_hidden:
                child.is_hidden = True
        Forum.objects.bulk_update(children, ["parent", "position", "is_hidden"])
    return len(children)


def _check_slug_free(forum: Forum, new_type: str) -> None:
    clashes = Forum.objects.filter(slug=forum.slug).exclude(pk=forum.pk)
    if new_type == Forum.CATEGORY:
        clashes = clashes.filter(forum_type=Forum.CATEGORY)
    else:
        clashes = clashes.exclude(forum_type=Forum.CATEGORY)
    if clashes.exists():
        raise ValidationError(
            _("Another row of that type already uses the slug “%(slug)s”.")
            % {"slug": forum.slug}
        )


def _check_category(forum: Forum, category: Forum | None) -> Forum:
    """The category a retyped row will sit in: an existing category that is
    not the row itself."""
    if category is None or category.pk is None or category.pk == forum.pk:
        raise ValidationError(_("Choose the category the forum belongs to."))
    fresh = Forum.objects.filter(pk=category.pk, forum_type=Forum.CATEGORY).first()
    if fresh is None:
        raise ValidationError(_("Choose the category the forum belongs to."))
    return fresh


def _refuse_if_holds_rows(forum: Forum) -> None:
    if Forum.objects.filter(parent=forum).exists():
        raise ValidationError(
            _(
                "This category still holds forums. Move or delete them "
                "before changing its type."
            )
        )


def change_type(
    forum: Forum,
    new_type: str,
    *,
    action: TopicsAction | None = None,
    target: Forum | None = None,
    category: Forum | None = None,
    link_url: str = "",
    track_clicks: bool = True,
) -> Forum:
    """Change a row between category, forum and link (phpBB's rules,
    simplified for two levels).

    - forum → category or link: its topics are moved to ``target`` or
      deleted first (``action``, the delete flow's choice), so no category or
      link ever holds a topic; its counters reset. A category leaves its
      category; a link stays in it.
    - category → forum or link: refused while it holds forums or links; it
      then needs the ``category`` it will sit in.
    - link → forum or category: the URL and its click count are cleared. A
      forum stays in the link's category; a category goes to the top level.

    Becoming a link needs ``link_url`` (http/https, ``Forum.clean``)."""
    with transaction.atomic():
        forum = Forum.objects.select_for_update().get(pk=forum.pk)
        old_type = forum.forum_type
        valid = {Forum.CATEGORY, Forum.FORUM, Forum.LINK}
        if new_type not in valid:
            raise ValidationError(_("Choose a category, a forum or a link."))
        if new_type == old_type:
            raise ValidationError(_("The row already has that type."))
        _check_slug_free(forum, new_type)

        if old_type == Forum.FORUM:
            empty_forum(forum, action, target)
            forum.topic_count = 0
            forum.post_count = 0
        elif old_type == Forum.CATEGORY:
            _refuse_if_holds_rows(forum)
            forum.parent = _check_category(forum, category)
            forum.position = next_position(forum.parent.pk)
        else:  # a link
            forum.click_count = 0
            forum.track_clicks = Forum._meta.get_field("track_clicks").default

        if new_type == Forum.CATEGORY:
            forum.parent = None
            forum.position = next_position(None)
        if new_type == Forum.LINK:
            forum.link_url = link_url
            forum.track_clicks = track_clicks
            forum.click_count = 0
        else:
            forum.link_url = ""
        forum.forum_type = new_type
        forum.full_clean(exclude=["slug"])
        forum.save()
    return forum
