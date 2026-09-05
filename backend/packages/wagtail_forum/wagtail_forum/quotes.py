"""Structured post quotes (todo 342) — the package half.

A `post_quote` block carries the quoted post's id and its text. Three rules:

1. **Validated on write** (`api/sanitize.py` → `resolve_quotable_posts`): the
   quoted post must be live on a live, visible board, and its author must
   not be block-paired with the writer; the count per body is capped. A
   quote that fails is a 400, never silently stripped — the writer chose it.
2. **Resolved on read in ONE query per page** (`api/serializers.py` →
   `build_forum_quote_map`): the envelope carries the text plus a safe
   attribution (author, topic id) and `available=False` when the quoted
   post has since gone away — the stored text still renders.
3. **Notifies the quoted author** with the QUOTE verb (host fan-out mirrors
   mentions: `resolve_quoted_authors`), subject to the same block/visibility
   rules, a mention taking precedence over a quote for the same person.
"""

from __future__ import annotations

from django.db.models import Q

from .conf import get_setting
from .models import Post, UserBlock


def quoted_post_ids(raw_data) -> list[int]:
    """Distinct quoted post ids in a body's raw StreamField data, first-seen
    order. Non-integer ids are ignored here (the write validator rejects
    them)."""
    seen: list[int] = []
    for block in raw_data:
        if not isinstance(block, dict) or block.get("type") != "post_quote":
            continue
        value = block.get("value")
        pid = value.get("post") if isinstance(value, dict) else None
        if isinstance(pid, int) and not isinstance(pid, bool) and pid not in seen:
            seen.append(pid)
    return seen


def visible_quoted_posts(ids) -> dict[int, Post]:
    """{id: Post} for the quoted posts that are live on a live, visible
    board — one query, the author (and avatar) joined for the attribution.
    Only `topic_id` is read downstream, so the topic itself is not joined."""
    from .api.views import _visible_boards  # local import — avoids a cycle

    ids = [i for i in ids if isinstance(i, int)]
    if not ids:
        return {}
    qs = Post.objects.filter(
        pk__in=ids, live=True, topic__live=True, topic__board__in=_visible_boards()
    ).select_related("author__wagtail_forum_profile__avatar")
    return {post.pk: post for post in qs}


def resolve_quotable_posts(ids, writer) -> dict[int, Post]:
    """The subset of `ids` the writer may quote: visible (above) and not
    authored by someone block-paired with the writer, either direction."""
    posts = visible_quoted_posts(ids)
    if not posts or writer is None or not getattr(writer, "is_authenticated", False):
        return posts
    author_ids = {p.author_id for p in posts.values() if p.author_id}
    if not author_ids:
        return posts
    blocked = set(
        UserBlock.objects.filter(
            Q(blocker=writer, blocked_id__in=author_ids)
            | Q(blocked=writer, blocker_id__in=author_ids)
        ).values_list("blocker_id", "blocked_id")
    )
    paired = {b for pair in blocked for b in pair if b != writer.pk}
    return {pid: p for pid, p in posts.items() if p.author_id not in paired}


def resolve_quoted_authors(post, *, exclude_pks=()) -> list[tuple[object, Post]]:
    """[(author, quoted_post)] for the posts `post` quotes — deduped per
    author (their first quoted post), capped at QUOTES_MAX_PER_POST, only
    visible quoted posts, excluding `exclude_pks` (the quoting author,
    already-mentioned users). Blocked pairs are the host's concern
    (`_drop_blocked_pairs`), as for mentions."""
    ids = quoted_post_ids(post.body.raw_data)[: get_setting("QUOTES_MAX_PER_POST")]
    posts = visible_quoted_posts(ids)
    out: list[tuple[object, Post]] = []
    seen: set[int] = set()
    for pid in ids:
        quoted = posts.get(pid)
        if quoted is None or quoted.author_id is None:
            continue
        if quoted.author_id in exclude_pks or quoted.author_id in seen:
            continue
        seen.add(quoted.author_id)
        out.append((quoted.author, quoted))
    return out
