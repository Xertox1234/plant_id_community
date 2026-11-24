"""Structured post quotes (todo 342) — the package half.

A `post_quote` block carries the quoted post's id and its text. Three rules:

1. **Validated on write** (`api/sanitize.py` → `resolve_quotable_posts`): the
   quoted post must be live on a live, visible board, and its author must
   not be block-paired with the writer; the count per body is capped; the
   text must be one piece of the quoted post's own text (`quote_matches`). A
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

import re

from django.contrib.auth.models import AbstractBaseUser
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


# Python's ``\s`` plus U+FEFF, which JavaScript and Dart count as whitespace.
_WHITESPACE_RE = re.compile(r"[\s\ufeff]+")


def _collapse(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalise_quote(text: str) -> str:
    """A quote's text as it is compared (the rule the clients share): every
    run of whitespace is one space, and one trailing "…", the truncation
    mark, is dropped."""
    return _collapse(_collapse(text).removesuffix("…"))


def quotable_runs(raw_data) -> list[str]:
    """A body's quotable plain text, whitespace collapsed, one entry per
    unbroken run of blocks. Only a paragraph is HTML; heading, legacy quote
    and code text is plain by contract. An image has no text. Any other block
    (a nested ``post_quote``: someone else's words; an embed; a link card)
    ends the run, so an excerpt neither quotes it nor skips over it."""
    from .api.views import _rich_text_to_plain  # local import — avoids a cycle

    runs: list[list[str]] = [[]]
    for block in raw_data:
        kind, value = block.get("type"), block.get("value")
        if kind == "paragraph" and isinstance(value, str):
            runs[-1].append(_rich_text_to_plain(value))
        elif kind in ("heading", "quote") and isinstance(value, str):
            runs[-1].append(value)
        elif kind == "code" and isinstance(value, dict):
            runs[-1].append(str(value.get("code") or ""))
        elif kind != "image":
            runs.append([])
    return [text for run in runs if (text := _collapse(" ".join(run)))]


def quote_matches(text: str, runs: list[str]) -> bool:
    """Whether ``text`` is one contiguous piece of a post whose
    ``quotable_runs`` are ``runs`` (owner decision, audit 2026-11-24 F3). Text
    that is empty once normalised ("…") matches nothing."""
    wanted = normalise_quote(text)
    return bool(wanted) and any(wanted in run for run in runs)


def stored_quotes(raw_data) -> set[tuple[int, str]]:
    """``(post id, normalised text)`` of every post_quote a stored body
    carries: an edit that resends one keeps it, whatever became of its
    source."""
    return {
        (block["value"]["post"], normalise_quote(block["value"].get("text") or ""))
        for block in raw_data
        if isinstance(block, dict)
        and block.get("type") == "post_quote"
        and isinstance(block.get("value"), dict)
        and "post" in block["value"]
    }


def visible_quoted_posts(ids, reader=None, *, request=None) -> dict[int, Post]:
    """{id: Post} for the quoted posts that are live on a live board `reader`
    may read (the guest view when None; todo 676). Given `request`, the reader
    is its user and the password forums this session unlocked count (todo
    680, round-2 review) — one query, the author
    (and avatar) joined for the attribution. Only `topic_id` is read
    downstream, so the topic itself is not joined."""
    from .api.views import _visible_boards  # local import — avoids a cycle

    ids = [i for i in ids if isinstance(i, int)]
    if not ids:
        return {}
    qs = Post.objects.filter(
        pk__in=ids,
        live=True,
        topic__live=True,
        topic__board__in=_visible_boards(reader, request=request),
    ).select_related("author__wagtail_forum_profile__avatar")
    return {post.pk: post for post in qs}


def resolve_quotable_posts(ids, writer, *, request=None) -> dict[int, Post]:
    """The subset of `ids` the writer may quote: visible (above) and not
    authored by someone block-paired with the writer, either direction."""
    posts = visible_quoted_posts(ids, writer, request=request)
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


def resolve_quoted_authors(
    post, *, exclude_pks=()
) -> list[tuple[AbstractBaseUser, Post]]:
    """[(author, quoted_post)] for the posts `post` quotes — deduped per
    author (their first quoted post), capped at QUOTES_MAX_PER_POST, only
    visible quoted posts, excluding `exclude_pks` (the quoting author,
    already-mentioned users). Blocked pairs are the host's concern
    (`_drop_blocked_pairs`), as for mentions."""
    ids = quoted_post_ids(post.body.raw_data)[: get_setting("QUOTES_MAX_PER_POST")]
    posts = visible_quoted_posts(ids, post.author)
    out: list[tuple[AbstractBaseUser, Post]] = []
    seen: set[int] = set()
    for pid in ids:
        quoted = posts.get(pid)
        if quoted is None or quoted.author_id is None:
            continue
        if quoted.author_id in exclude_pks or quoted.author_id in seen:
            continue
        author = quoted.author
        if author is None:  # author_id is set, so never at runtime; narrows the type
            continue
        seen.add(quoted.author_id)
        out.append((author, quoted))
    if not out:
        return out
    # Only authors who may read the quoting post's forum hear about it
    # (todo 676), as for mentions.
    from .services.forum_permissions import readers_of_forum

    readers = {u.pk for u in readers_of_forum([a for a, _ in out], post.topic.board_id)}
    return [(a, q) for a, q in out if a.pk in readers]
