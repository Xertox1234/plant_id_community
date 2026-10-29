"""Safe delete and type change for forum rows (todo 667; spec 2026-10-28 §2).

phpBB asks *move topics to [forum]* or *delete topics* before a forum goes,
but never checks the target server-side; every function here does
(:func:`validate_topic_target`, :func:`validate_forum_target`). Each runs in
one transaction, so a refused or failed step leaves the structure as it was.

- :func:`empty_forum` moves or deletes a forum's topics so the row can be
  deleted or turned into a category (``Topic.board`` is ``PROTECT``).
- :func:`empty_category` moves a category's forums under another category.
- :func:`change_type` turns a forum into a category or a category into a
  forum (link conversions arrive with the link URL field, todo 670).

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
from django.db.models import Case, Max, Value, When
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
        # .update() skips auto_now; /sync/ clients find moved topics by it.
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
        for offset, child in enumerate(children):
            child.parent = target
            child.position = start + offset
        Forum.objects.bulk_update(children, ["parent", "position"])
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


def change_type(
    forum: Forum,
    new_type: str,
    *,
    action: TopicsAction | None = None,
    target: Forum | None = None,
    category: Forum | None = None,
) -> Forum:
    """Turn a forum into a category, or a category into a forum.

    - forum → category: its topics are moved to ``target`` or deleted first
      (``action``, the delete flow's choice), so no category ever holds a
      topic; the row leaves its category and its counters reset.
    - category → forum: refused while it holds forums or links; it then
      needs the ``category`` it will sit in.

    Link conversions are todo 670's (they need the link URL field)."""
    with transaction.atomic():
        forum = Forum.objects.select_for_update().get(pk=forum.pk)
        if new_type == forum.forum_type:
            raise ValidationError(_("The row already has that type."))
        if forum.forum_type == Forum.FORUM and new_type == Forum.CATEGORY:
            _check_slug_free(forum, Forum.CATEGORY)
            empty_forum(forum, action, target)
            forum.forum_type = Forum.CATEGORY
            forum.parent = None
            forum.position = next_position(None)
            forum.topic_count = 0
            forum.post_count = 0
        elif forum.forum_type == Forum.CATEGORY and new_type == Forum.FORUM:
            if Forum.objects.filter(parent=forum).exists():
                raise ValidationError(
                    _(
                        "This category still holds forums. Move or delete them "
                        "before turning it into a forum."
                    )
                )
            if category is None or category.pk == forum.pk:
                raise ValidationError(_("Choose the category the forum belongs to."))
            category = Forum.objects.filter(
                pk=category.pk, forum_type=Forum.CATEGORY
            ).first()
            if category is None:
                raise ValidationError(_("Choose the category the forum belongs to."))
            _check_slug_free(forum, Forum.FORUM)
            forum.forum_type = Forum.FORUM
            forum.parent = category
            forum.position = next_position(category.pk)
        else:
            raise ValidationError(
                _("Only a forum can become a category, and a category a forum.")
            )
        forum.full_clean(exclude=["slug"])
        forum.save()
    return forum
