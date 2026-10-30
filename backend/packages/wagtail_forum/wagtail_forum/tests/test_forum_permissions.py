"""Forum permission roles and grants (todo 675; owner decision 2026-10-30).

phpBB's role matrix, grants unioned across a member's groups, and the
per-principal fallback (members Standard, guests Read only) that keeps a
forum nobody has set up open. Plus the copy rules: a new forum starts with
its category's grants, and "copy permissions" overwrites exactly.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from wagtail_forum.models import ForumGrant, ForumRole
from wagtail_forum.services.forum_permissions import (
    ATTACH,
    LIST,
    POLL,
    POST,
    READ,
    REPLY,
    copy_permissions,
    set_grant,
    user_can,
    visible_forums,
)
from wagtail_forum.tests.factories import make_category, make_forum

User = get_user_model()
pytestmark = pytest.mark.django_db

ALL = {LIST, READ, POST, REPLY, POLL, ATTACH}
# The owner's matrix, verbatim: Full and Std+Polls all six, Standard all but
# poll, Limited list/read/post/reply, Read Only list/read, No Access none.
EXPECTED = {
    ForumRole.FULL: ALL,
    ForumRole.STANDARD_POLLS: ALL,
    ForumRole.STANDARD: ALL - {POLL},
    ForumRole.LIMITED: {LIST, READ, POST, REPLY},
    ForumRole.READ_ONLY: {LIST, READ},
    ForumRole.NO_ACCESS: set(),
}


def _flags(user, forum):
    return {flag for flag in sorted(ALL) if user_can(user, forum, flag)}


def _fresh(user):
    # user_can caches per user object (one request); a fresh object per check.
    return User.objects.get(pk=user.pk) if user.is_authenticated else AnonymousUser()


@pytest.mark.parametrize("role", list(ForumRole))
def test_user_can_matches_the_role_matrix_for_members_and_guests(role):
    forum = make_forum()
    member = User.objects.create_user(username="m")

    set_grant(forum, ForumGrant.MEMBERS, role)
    set_grant(forum, ForumGrant.ANONYMOUS, role)

    assert _flags(_fresh(member), forum) == EXPECTED[role]
    assert _flags(AnonymousUser(), forum) == EXPECTED[role]
    assert _flags(None, forum) == EXPECTED[role]


@pytest.mark.parametrize("role", list(ForumRole))
def test_a_group_grant_gives_its_role_on_top_of_the_members_row(role):
    forum = make_forum()
    group = Group.objects.create(name="Experts")
    member = User.objects.create_user(username="m")
    member.groups.add(group)
    outsider = User.objects.create_user(username="o")
    set_grant(forum, ForumGrant.MEMBERS, ForumRole.NO_ACCESS)

    set_grant(forum, ForumGrant.GROUP, role, group=group)

    assert _flags(_fresh(member), forum) == EXPECTED[role]
    assert _flags(_fresh(outsider), forum) == set()


def test_grants_union_across_a_members_groups():
    forum = make_forum()
    readers = Group.objects.create(name="Readers")
    pollsters = Group.objects.create(name="Pollsters")
    member = User.objects.create_user(username="m")
    member.groups.add(readers, pollsters)
    set_grant(forum, ForumGrant.MEMBERS, ForumRole.NO_ACCESS)
    set_grant(forum, ForumGrant.GROUP, ForumRole.READ_ONLY, group=readers)
    set_grant(forum, ForumGrant.GROUP, ForumRole.STANDARD_POLLS, group=pollsters)

    assert _flags(_fresh(member), forum) == ALL


def test_a_forum_with_no_grant_is_standard_for_members_and_read_only_for_guests():
    forum = make_forum()
    member = User.objects.create_user(username="m")

    assert _flags(member, forum) == EXPECTED[ForumRole.STANDARD]
    assert _flags(AnonymousUser(), forum) == EXPECTED[ForumRole.READ_ONLY]


def test_one_group_row_never_takes_the_forum_away_from_everyone_else():
    """The fallback is per principal: the members row is still missing, so
    members keep Standard (no invisible-forum footgun)."""
    forum = make_forum()
    group = Group.objects.create(name="Experts")
    set_grant(forum, ForumGrant.GROUP, ForumRole.FULL, group=group)
    member = User.objects.create_user(username="m")

    assert _flags(member, forum) == EXPECTED[ForumRole.STANDARD]
    assert visible_forums(member).filter(pk=forum.pk).exists()
    assert visible_forums(None).filter(pk=forum.pk).exists()


def test_staff_can_do_everything_whatever_the_grants():
    forum = make_forum()
    set_grant(forum, ForumGrant.MEMBERS, ForumRole.NO_ACCESS)
    staff = User.objects.create_user(username="s", is_staff=True)

    assert _flags(staff, forum) == ALL


def test_user_can_is_cached_for_the_request():
    forum = make_forum()
    member = User.objects.create_user(username="m")
    user_can(member, forum, READ)

    with CaptureQueriesContext(connection) as ctx:
        for flag in sorted(ALL):
            user_can(member, forum, flag)

    assert len(ctx.captured_queries) == 0


def test_creating_a_forum_copies_the_categorys_grants():
    category = make_category(name="Staff", slug="staff-cat")
    group = Group.objects.create(name="Mods")
    set_grant(category, ForumGrant.MEMBERS, ForumRole.NO_ACCESS)
    set_grant(category, ForumGrant.ANONYMOUS, ForumRole.NO_ACCESS)
    set_grant(category, ForumGrant.GROUP, ForumRole.FULL, group=group)

    forum = make_forum(name="Notes", slug="notes", category=category)

    assert set(
        ForumGrant.objects.filter(forum=forum).values_list("principal", "group", "role")
    ) == {
        (ForumGrant.MEMBERS, None, ForumRole.NO_ACCESS),
        (ForumGrant.ANONYMOUS, None, ForumRole.NO_ACCESS),
        (ForumGrant.GROUP, group.pk, ForumRole.FULL),
    }


def test_a_forum_in_a_category_with_no_grants_starts_on_the_defaults():
    forum = make_forum()

    assert not ForumGrant.objects.filter(forum=forum).exists()


def test_copy_permissions_overwrites_the_targets_grants_exactly():
    source = make_forum(name="Source", slug="source")
    target = make_forum(name="Target", slug="target")
    readers = Group.objects.create(name="Readers")
    other = Group.objects.create(name="Other")
    set_grant(source, ForumGrant.MEMBERS, ForumRole.LIMITED)
    set_grant(source, ForumGrant.GROUP, ForumRole.FULL, group=readers)
    # Target rows that must all go: one the source also has, one it lacks.
    set_grant(target, ForumGrant.MEMBERS, ForumRole.FULL)
    set_grant(target, ForumGrant.ANONYMOUS, ForumRole.NO_ACCESS)
    set_grant(target, ForumGrant.GROUP, ForumRole.READ_ONLY, group=other)

    copied = copy_permissions(source, target)

    def rows(forum):
        return set(
            ForumGrant.objects.filter(forum=forum).values_list(
                "principal", "group", "role"
            )
        )

    assert copied == 2
    assert (
        rows(target)
        == rows(source)
        == {
            (ForumGrant.MEMBERS, None, ForumRole.LIMITED),
            (ForumGrant.GROUP, readers.pk, ForumRole.FULL),
        }
    )
