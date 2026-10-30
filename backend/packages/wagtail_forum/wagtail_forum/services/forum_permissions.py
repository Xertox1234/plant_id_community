"""Per-forum permissions (todos 675, 676, 680; spec 2026-10-28 §2).

**Flags and roles.** Six flags (phpBB's ``f_*``): ``list`` (see the row),
``read`` (read its topics), ``post`` (start a topic), ``reply``, ``poll`` and
``attach``. A ``ForumGrant`` gives one principal one role on one row, and a
role is a fixed flag set (``ROLE_FLAGS``, owner decision 2026-10-30).

**Principals.** A user's principals are the *members* pseudo-group and every
Django group they belong to; a guest's only principal is the *guests*
pseudo-group. What a user may do is the **union** of their principals' roles.

**The no-grant fallback is per principal, not per forum.** A pseudo-group with
no row on a forum gets its default role: *Standard* for members, *Read only*
for guests. A real group with no row adds nothing. So a forum nobody has set
up works as it always did, and adding one row ("Experts: Full") never takes
the forum away from everyone else: the members row is still missing, so
members still get Standard. Hiding a forum is an explicit act: *No access*
for guests and members (``hide_for_everyone``), which is what the
``is_hidden`` data migration wrote. (A per-forum reading of "a forum with no
grant", where any one row switches the defaults off, is the invisible-forum
footgun the 675 spec was filed against.)

**Visibility** (``visible_forums``) is one lazy queryset, every check folded
into the SQL as ``Exists`` subqueries, so ``board__in=visible_forums(user)``
callers add no query of their own and query-count pins stay fixed. A forum or
link needs ``read`` on itself and ``list`` on its category. Staff and
superusers see every row; global moderators (``change_post``) and the
moderators of a forum see it whatever its grants (owner decision 2026-10-30,
as staff saw ``is_hidden`` forums in the admin).

**Passwords** (todo 680): a forum with a ``password_hash`` is left out until
the reader unlocks it in their session (``unlocked_forum_ids``); moderators
and staff bypass. ``include_locked=True`` keeps the row (the web index shows
it with a lock) while topic paths keep it out.

``user_can(user, forum, flag)`` answers one row in Python, cached on the user
object for the rest of the request.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.db.models import (
    CharField,
    Exists,
    ExpressionWrapper,
    F,
    OuterRef,
    Q,
    QuerySet,
)
from django.utils.crypto import constant_time_compare, salted_hmac
from wagtail.models import PageViewRestriction

from ..models import Forum, ForumGrant, ForumIndex, ForumModerator, ForumRole

LIST = "list"
READ = "read"
POST = "post"
REPLY = "reply"
POLL = "poll"
ATTACH = "attach"
FLAGS = (LIST, READ, POST, REPLY, POLL, ATTACH)

ROLE_FLAGS: dict[str, frozenset[str]] = {
    ForumRole.FULL: frozenset(FLAGS),
    ForumRole.STANDARD_POLLS: frozenset(FLAGS),
    ForumRole.STANDARD: frozenset({LIST, READ, POST, REPLY, ATTACH}),
    ForumRole.LIMITED: frozenset({LIST, READ, POST, REPLY}),
    ForumRole.READ_ONLY: frozenset({LIST, READ}),
    ForumRole.NO_ACCESS: frozenset(),
}

# The role a pseudo-group gets on a row that has no grant for it.
DEFAULT_ROLES: dict[str, str] = {
    ForumGrant.ANONYMOUS: ForumRole.READ_ONLY,
    ForumGrant.MEMBERS: ForumRole.STANDARD,
}

# The session key holding the forum ids this session unlocked (todo 680).
UNLOCKED_SESSION_KEY = "wagtail_forum_unlocked_forums"

_FLAGS_CACHE_ATTR = "_wagtail_forum_flags"
_GROUPS_CACHE_ATTR = "_wagtail_forum_group_ids"


def roles_with(flag: str) -> list[str]:
    return [str(role) for role, flags in ROLE_FLAGS.items() if flag in flags]


def _authenticated(user: Any) -> bool:
    return user is not None and bool(getattr(user, "is_authenticated", False))


def sees_everything(user: Any) -> bool:
    """Staff and superusers: every row, every flag, no password."""
    return _authenticated(user) and bool(user.is_staff or user.is_superuser)


def _pseudo_q(principal: str, flag: str, ref: str) -> Q:
    """``principal`` (guests or members) has ``flag`` on the row ``ref``."""
    rows = ForumGrant.objects.filter(forum=OuterRef(ref), principal=principal)
    q = Q(Exists(rows.filter(role__in=roles_with(flag))))
    if flag in ROLE_FLAGS[DEFAULT_ROLES[principal]]:
        q |= Q(~Exists(rows))
    return q


def _user_groups(user: Any) -> QuerySet[Group]:
    return Group.objects.filter(user=user).values("pk")  # type: ignore[return-value]


def access_q(user: Any, flag: str, ref: str = "pk") -> Q:
    """SQL for "``user`` has ``flag`` on the row ``ref``" (no bypasses)."""
    if not _authenticated(user):
        return _pseudo_q(ForumGrant.ANONYMOUS, flag, ref)
    by_group = ForumGrant.objects.filter(
        forum=OuterRef(ref),
        principal=ForumGrant.GROUP,
        group__in=_user_groups(user),
        role__in=roles_with(flag),
    )
    return _pseudo_q(ForumGrant.MEMBERS, flag, ref) | Q(Exists(by_group))


def global_moderator_q(user: Any) -> Q:
    """The user holds ``wagtail_forum.change_post`` (directly or by group),
    as SQL so the check costs no query of its own."""
    perm = Permission.objects.filter(
        content_type__app_label="wagtail_forum", codename="change_post"
    ).filter(Q(user=user) | Q(group__user=user))
    return Q(Exists(perm))


def moderated_forum_ids(user: Any) -> QuerySet[Any]:
    """Subquery of the forum ids ``user`` moderates, as a user or by group."""
    return (
        ForumModerator.objects.filter(Q(user=user) | Q(group__in=_user_groups(user)))
        .values("forum_id")
        .distinct()
    )


def _moderator_q(user: Any) -> Q:
    return global_moderator_q(user) | Q(pk__in=moderated_forum_ids(user))


def _forum_index_open_q() -> Q:
    """The ForumIndex page gate (todo 665): when ForumIndex pages exist but
    none is open (live, no Wagtail privacy restriction on itself or an
    ancestor), every forum is hidden. One open index is enough."""
    restriction_on_index_or_ancestor = PageViewRestriction.objects.annotate(
        index_path=ExpressionWrapper(OuterRef("path"), output_field=CharField())
    ).filter(index_path__startswith=F("page__path"))
    open_index = ForumIndex.objects.filter(
        ~Exists(restriction_on_index_or_ancestor), live=True
    )
    return Q(Exists(open_index)) | Q(~Exists(ForumIndex.objects.all()))


def visible_forums(
    user: Any,
    *forum_types: str,
    unlocked: Iterable[int] = (),
    include_locked: bool = False,
) -> QuerySet[Forum]:
    """The rows of ``forum_types`` (forums by default) ``user`` may see.

    ``user=None`` (or anonymous) is the guest view: what sitemaps, feeds and
    shared caches may show. ``unlocked`` are the password forums this request
    unlocked; ``include_locked`` keeps the other password forums too."""
    qs = Forum.objects.filter(
        _forum_index_open_q(), forum_type__in=forum_types or (Forum.FORUM,)
    )
    if sees_everything(user):
        return qs
    access = access_q(user, READ) & access_q(user, LIST, "parent")
    bypass = Q(pk__in=[])
    if _authenticated(user):
        bypass = _moderator_q(user)
        access |= bypass
    qs = qs.filter(access)
    if not include_locked:
        if not _authenticated(user):
            unlocked = ()
        qs = qs.filter(Q(password_hash="") | Q(pk__in=list(unlocked)) | bypass)
    return qs


def visible_categories(user: Any) -> QuerySet[Forum]:
    """The categories ``user`` may list (their rows still need a visible
    forum or link to be shown)."""
    qs = Forum.objects.filter(forum_type=Forum.CATEGORY)
    if sees_everything(user):
        return qs
    access = access_q(user, LIST)
    if _authenticated(user):
        access |= global_moderator_q(user) | Q(children__in=moderated_forum_ids(user))
    return qs.filter(access).distinct()


def _unlock_fingerprint(password_hash: str) -> str:
    """Ties a stored unlock to the password it was checked against: a new
    password (a leaked one rotated) re-locks every session that unlocked the
    old one (round-1 review). An HMAC, so the session never holds the hash."""
    return salted_hmac(
        "wagtail_forum.forum_unlock", password_hash, algorithm="sha256"
    ).hexdigest()


def unlocked_forum_ids(request: Any) -> list[int]:
    """The password forums this session unlocked (todo 680), for the user
    who unlocked them only: a later sign-in on the same browser, or a
    signed-out (edge-cacheable) request, starts locked. An unlock lasts only
    while the forum keeps the password it was made with."""
    session = getattr(request, "session", None)
    user = getattr(request, "user", None)
    if session is None or user is None or not _authenticated(user):
        return []
    stored = session.get(UNLOCKED_SESSION_KEY)
    if not isinstance(stored, dict) or stored.get("user") != user.pk:
        return []
    forums = stored.get("forums")
    if not isinstance(forums, dict) or not forums:
        return []
    current = Forum.objects.filter(
        pk__in=[int(pk) for pk in forums if str(pk).isdigit()]
    ).exclude(password_hash="")
    return [
        pk
        for pk, password_hash in current.values_list("pk", "password_hash")
        if isinstance(forums.get(str(pk)), str)
        and constant_time_compare(forums[str(pk)], _unlock_fingerprint(password_hash))
    ]


def remember_unlocked(request: Any, forum: Forum) -> None:
    stored = request.session.get(UNLOCKED_SESSION_KEY)
    forums: dict[str, str] = {}
    if isinstance(stored, dict) and stored.get("user") == request.user.pk:
        kept = stored.get("forums")
        if isinstance(kept, dict):
            forums = {str(k): v for k, v in kept.items() if isinstance(v, str)}
    forums[str(forum.pk)] = _unlock_fingerprint(forum.password_hash)
    request.session[UNLOCKED_SESSION_KEY] = {"user": request.user.pk, "forums": forums}


def readers_of_forum(users: list[Any], forum_id: int) -> list[Any]:
    """The ``users`` who may read forum ``forum_id``: the per-user rule of
    ``visible_forums`` for many users at once, in a constant number of
    queries (three) whatever their number. For mentions and quoted authors.
    A password forum is read only by those who bypass it: a notification has
    no session to have unlocked it in."""
    if not users:
        return []
    forum = (
        Forum.objects.filter(_forum_index_open_q(), pk=forum_id)
        .values("pk", "parent_id", "password_hash")
        .first()
    )
    if forum is None:
        return []
    rows = [forum["pk"]] + ([forum["parent_id"]] if forum["parent_id"] else [])
    grants = list(
        ForumGrant.objects.filter(forum_id__in=rows).values_list(
            "forum_id", "principal", "role"
        )
    )

    def members_have(row: int | None, flag: str) -> bool:
        if row is None:
            return True
        roles = [r for f, p, r in grants if f == row and p == ForumGrant.MEMBERS]
        if not roles:
            return flag in ROLE_FLAGS[DEFAULT_ROLES[ForumGrant.MEMBERS]]
        return any(flag in ROLE_FLAGS[role] for role in roles)

    def by_group(row: int, flag: str) -> Exists:
        return Exists(
            ForumGrant.objects.filter(
                forum_id=row,
                principal=ForumGrant.GROUP,
                role__in=roles_with(flag),
                group__user=OuterRef("pk"),
            )
        )

    user_ref = Q(user=OuterRef("pk")) | Q(group__user=OuterRef("pk"))
    bypass = (
        Q(is_staff=True)
        | Q(is_superuser=True)
        | Q(
            Exists(
                Permission.objects.filter(
                    user_ref,
                    content_type__app_label="wagtail_forum",
                    codename="change_post",
                )
            )
        )
        | Q(Exists(ForumModerator.objects.filter(user_ref, forum_id=forum_id)))
    )
    parent = forum["parent_id"]
    members_read = members_have(forum_id, READ)
    members_list = members_have(parent, LIST)
    if forum["password_hash"]:
        allowed = bypass
    elif members_read and members_list:
        allowed = Q()  # every member (an empty Q matches every row)
    else:
        conditions = []
        if not members_read:
            conditions.append(Q(by_group(forum_id, READ)))
        if not members_list and parent is not None:
            conditions.append(Q(by_group(parent, LIST)))
        granted = conditions[0]
        for condition in conditions[1:]:
            granted &= condition
        allowed = bypass | granted
    ids = [user.pk for user in users if _authenticated(user)]
    model = type(users[0])
    readable = set(
        model._default_manager.filter(allowed, pk__in=ids).values_list("pk", flat=True)
    )
    return [user for user in users if user.pk in readable]


def is_forum_moderator(user: Any, forum: Forum) -> bool:
    """``user`` moderates ``forum`` (globally or as one of its moderators)."""
    if not _authenticated(user):
        return False
    if user.is_superuser or user.has_perm("wagtail_forum.change_post"):
        return True
    return moderated_forum_ids(user).filter(forum_id=forum.pk).exists()


def _group_ids(user: Any) -> frozenset[int]:
    cached = getattr(user, _GROUPS_CACHE_ATTR, None)
    if cached is None:
        cached = frozenset(user.groups.values_list("pk", flat=True))
        setattr(user, _GROUPS_CACHE_ATTR, cached)
    return cached


def effective_flags(user: Any, forum: Forum) -> frozenset[str]:
    """The union of ``user``'s principals' flags on ``forum`` (grants only;
    the category's ``list`` and the bypasses are ``visible_forums``')."""
    grants = list(
        ForumGrant.objects.filter(forum=forum).values_list(
            "principal", "group_id", "role"
        )
    )
    authenticated = _authenticated(user)
    pseudo = ForumGrant.MEMBERS if authenticated else ForumGrant.ANONYMOUS
    groups = _group_ids(user) if authenticated else frozenset()
    flags: set[str] = set()
    pseudo_seen = False
    for principal, group_id, role in grants:
        if principal == pseudo:
            pseudo_seen = True
            flags |= ROLE_FLAGS[role]
        elif principal == ForumGrant.GROUP and group_id in groups:
            flags |= ROLE_FLAGS[role]
    if not pseudo_seen:
        flags |= ROLE_FLAGS[DEFAULT_ROLES[pseudo]]
    return frozenset(flags)


def user_can(user: Any, forum: Forum, flag: str) -> bool:
    """Whether ``user`` has ``flag`` on ``forum``, cached on the user object
    (one request) per forum. Staff and superusers can do everything."""
    if flag not in FLAGS:
        raise ValueError(f"unknown forum permission flag {flag!r}")
    if sees_everything(user):
        return True
    cache: dict[int, frozenset[str]] | None = None
    if user is not None:
        cache = getattr(user, _FLAGS_CACHE_ATTR, None)
        if cache is None:
            cache = {}
            try:
                setattr(user, _FLAGS_CACHE_ATTR, cache)
            except AttributeError:  # pragma: no cover - a slotted user object
                cache = None
    if cache is not None and forum.pk in cache:
        return flag in cache[forum.pk]
    flags = effective_flags(user, forum)
    if cache is not None:
        cache[forum.pk] = flags
    return flag in flags


def copy_permissions(source: Forum, target: Forum) -> int:
    """Replace ``target``'s grants with exact copies of ``source``'s.
    Returns the number of grants written."""
    with transaction.atomic():
        ForumGrant.objects.filter(forum=target).delete()
        copies = [
            ForumGrant(
                forum=target,
                principal=grant.principal,
                group_id=grant.group_id,
                role=grant.role,
            )
            for grant in ForumGrant.objects.filter(forum=source)
        ]
        ForumGrant.objects.bulk_create(copies)
    return len(copies)


def set_grant(
    forum: Forum, principal: str, role: str | None, group: Any = None
) -> None:
    """Set one principal's role on ``forum``; ``role=None`` removes the row
    (the pseudo-groups then fall back to their default role)."""
    lookup: dict[str, Any] = {"forum": forum, "principal": principal}
    if principal == ForumGrant.GROUP:
        lookup["group"] = group
    if role is None:
        ForumGrant.objects.filter(**lookup).delete()
    else:
        ForumGrant.objects.update_or_create(defaults={"role": role}, **lookup)


def hide_for_everyone(forum: Forum) -> None:
    """*No access* for guests and members (what ``is_hidden`` meant)."""
    for principal in (ForumGrant.ANONYMOUS, ForumGrant.MEMBERS):
        set_grant(forum, principal, ForumRole.NO_ACCESS)


def _category_lists(category: Forum, principal: str, group_id: int | None) -> bool:
    """Whether ``principal`` (a group counts with all members, whose grants it
    adds to) may list ``category``."""
    rows = {(g.principal, g.group_id): g.role for g in category.grants.all()}

    def lists(pseudo: str) -> bool:
        return LIST in ROLE_FLAGS[rows.get((pseudo, None), DEFAULT_ROLES[pseudo])]

    if principal == ForumGrant.ANONYMOUS:
        return lists(ForumGrant.ANONYMOUS)
    if lists(ForumGrant.MEMBERS):
        return True
    role = (
        rows.get((ForumGrant.GROUP, group_id))
        if principal == ForumGrant.GROUP
        else None
    )
    return role is not None and LIST in ROLE_FLAGS[role]


def keep_out_whoever_the_category_kept_out(forum: Forum, old_category: Forum) -> None:
    """Before ``forum`` leaves ``old_category``: every principal that could
    not list the category gets *No access* on the forum (round-1 review).
    Grants union, so afterwards the forum is read only through a principal
    that could list the old category: a move never shows a forum to anyone
    who could not see it before, whatever the new category allows. The old
    rule covered only a category hidden from guests and members alike."""
    principals: list[tuple[str, int | None]] = [
        (ForumGrant.ANONYMOUS, None),
        (ForumGrant.MEMBERS, None),
    ]
    principals += [
        (ForumGrant.GROUP, group_id)
        for group_id in forum.grants.filter(principal=ForumGrant.GROUP).values_list(
            "group_id", flat=True
        )
    ]
    members_role = (
        forum.grants.filter(principal=ForumGrant.MEMBERS)
        .values_list("role", flat=True)
        .first()
        or DEFAULT_ROLES[ForumGrant.MEMBERS]
    )
    for principal, group_id in principals:
        if not _category_lists(old_category, principal, group_id):
            # A pseudo-group's row has no group (the model's constraint).
            lookup: dict[str, Any] = {"forum": forum, "principal": principal}
            if group_id is not None:
                lookup["group_id"] = group_id
            ForumGrant.objects.update_or_create(
                defaults={"role": ForumRole.NO_ACCESS}, **lookup
            )
            if principal == ForumGrant.MEMBERS:
                # A group the category let in read the forum through the
                # members' role: it keeps that role as a row of its own.
                for grant in old_category.grants.filter(principal=ForumGrant.GROUP):
                    if LIST in ROLE_FLAGS[grant.role]:
                        carried: dict[str, Any] = {
                            "forum": forum,
                            "principal": ForumGrant.GROUP,
                            "group_id": grant.group_id,
                        }
                        ForumGrant.objects.get_or_create(
                            defaults={"role": members_role}, **carried
                        )


def hidden_q(ref: str = "pk") -> Q:
    """SQL for "neither guests nor members can list the row ``ref``": the
    structure tree's *Hidden* badge."""
    return ~_pseudo_q(ForumGrant.ANONYMOUS, LIST, ref) & ~_pseudo_q(
        ForumGrant.MEMBERS, LIST, ref
    )


def is_hidden_for_everyone(forum: Forum | None) -> bool:
    if forum is None:
        return False
    return Forum.objects.filter(hidden_q(), pk=forum.pk).exists()
