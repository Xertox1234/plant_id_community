"""@mention parsing and resolution (todo 253 slice 4, H4).

Server-side regex resolution against real usernames is the only viable
strategy — the write-path sanitizer (api/sanitize.py) strips all structured
markup (no span/data-* attributes survive), so any client-supplied mention id
is unusable by the time a post is stored. This module re-derives mentions
from the already-sanitized plain text instead of trusting anything the
client sent.
"""

import re

from django.contrib.auth import get_user_model
from django.utils.html import strip_tags

from .conf import get_setting

# Deliberately narrower than Django's UnicodeUsernameValidator (which also
# allows ./+/-/@): a bare \w+ stops at sentence punctuation, so "thanks
# @alice." or "cc @alice," resolve to "alice", not "alice." / "alice,".
# Usernames containing ./+/-/@ can't be @mentioned — an accepted, documented
# limitation, not a bug.
#
# The (?<!\w) lookbehind requires the "@" itself not be preceded by a word
# character, so "admin@gmail.com" (extremely common in a plant-ID forum —
# "email me at X@gmail.com") does NOT match "gmail" as a mention; a bare
# "@alice" at a word boundary (start of string, after whitespace, after
# punctuation/HTML tags) still does.
MENTION_RE = re.compile(r"(?<!\w)@(\w+)")


def _mention_scan_text(post) -> str:
    """Reader-visible text from `post`'s title + body, for @mention scanning.

    Deliberately NOT spam/base.py's extract_text() — that walker stringifies
    raw block values (including a code block's source and an <a> tag's full
    markup) for spam heuristics that need to see links and code as-is. A
    mention scan wants the opposite: only text a reader actually sees, so an
    href/title attribute (nh3 allows both on <a> — api/sanitize.py) or a code
    sample's contents can't resolve a mention nobody can see. strip_tags()
    drops attribute values along with the tag markup that carries them —
    verified: strip_tags('<a href="x/@victim" title="@evil">click</a>') ==
    'click', while a real link *label* like '<a href="...">@alice</a>' still
    yields '@alice'.

    Walks raw_data (not the resolved StreamValue) — same reason as
    plain_text_excerpt: avoids the per-post image-block N+1 that iterating
    the resolved StreamValue would trigger.
    """
    parts = []
    if getattr(post, "is_opening_post", False):
        parts.append(post.topic.title)
    for raw in post.body.raw_data:
        value = raw.get("value")
        if isinstance(value, str):
            text = strip_tags(value).strip()
            if text:
                parts.append(text)
        # Anything else (code block dict, image chooser int PK) is skipped:
        # not reader-visible prose a mention could plausibly appear in.
    return " ".join(parts)


def resolve_mentioned_users(post, *, exclude_pks=()):
    """Real Users @mentioned in `post`'s title/body text.

    Deduped (first-seen order) and capped at MENTION_MAX_PER_POST — pure
    in-memory work, no query, so a post with no "@" costs nothing extra.
    Only once a candidate name list exists do we pay for the
    visibility gate, per mentioned user (todo 676): a user who may not read
    the post's forum is never notified of it, while a member of a
    group-only forum can still be mentioned there. A password forum
    notifies nobody but its moderators (todo 680). `exclude_pks` drops the
    post's own author (no self-mention notification).
    """
    seen = []
    for name in MENTION_RE.findall(_mention_scan_text(post)):
        if name not in seen:
            seen.append(name)
    names = seen[: get_setting("MENTION_MAX_PER_POST")]
    if not names:
        return []

    from .services.forum_permissions import readers_of_forum

    User = get_user_model()
    qs = User.objects.filter(username__in=names)
    if exclude_pks:
        qs = qs.exclude(pk__in=exclude_pks)
    return readers_of_forum(list(qs), post.topic.board_id)
