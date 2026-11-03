"""Management command: give accounts whose username came from their email a
random one.

Until PR #1252 every signup the member did not name (Firebase, the OAuth
callback, allauth social signup) minted ``username`` from the email's local
part, and the forum serves ``username`` to anonymous readers. Owner decision
2026-11-03: rename those accounts with ``signup.generate_username``.

An account is renamed when its username is its email's local part, compared
lowercased with everything but letters and digits removed, optionally followed
by the clash suffix a minting path appended (digits, or ``_`` plus hex). An
account that signs in with a password (``account_links.has_password``) chose
its username at registration, so it is only reported unless
``--include-password-accounts`` is passed.

The old handle also lives in content, as ``@old`` mention text. In the same
transaction the command rewrites ``@old`` to ``@new`` in forum post bodies,
topic titles and the Wagtail revisions of both, then reindexes what changed.
Direct messages are private to people who already know the sender and are not
edited. The old names are deliberately not stored anywhere (no reservation
list): a local part is short enough that even a hash of it gives it back.

Without ``--apply`` nothing is written. Output names accounts by id and new
handle only, never the old username or the email, because it lands in
deployment logs.
"""

import re

from apps.users.account_links import has_password
from apps.users.constants import GENERATED_USERNAME_PREFIX
from apps.users.signup import generate_username
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.models import Revision
from wagtail.search import index

_NON_ALNUM = re.compile(r"[^a-z0-9]")
# What a minting path appended on a clash, after normalising: Firebase added
# "_" + 8 hex, the OAuth callback and allauth added digits.
_CLASH_SUFFIX = re.compile(r"[0-9a-f]*")


def _normalise(text: str) -> str:
    return _NON_ALNUM.sub("", text.lower())


def is_email_derived(username: str, email: str) -> bool:
    """True if ``username`` is ``email``'s local part, maybe plus a clash suffix."""
    if not email or "@" not in email or username.startswith(GENERATED_USERNAME_PREFIX):
        return False
    local = _normalise(email.split("@", 1)[0])
    name = _normalise(username)
    if not local or not name.startswith(local):
        return False
    return bool(_CLASH_SUFFIX.fullmatch(name[len(local) :]))


def _rewrite(value, pattern: re.Pattern, renames: dict[str, str]):
    """``value`` with every ``@old`` mention in its strings replaced, and the
    number of replacements. Walks the nested lists and dicts of stream data
    and revision content."""
    if isinstance(value, str):
        return pattern.subn(lambda m: "@" + renames[m.group(1)], value)
    if isinstance(value, list):
        total = 0
        out = []
        for item in value:
            new, count = _rewrite(item, pattern, renames)
            out.append(new)
            total += count
        return out, total
    if isinstance(value, dict):
        total = 0
        out_dict = {}
        for key, item in value.items():
            new, count = _rewrite(item, pattern, renames)
            out_dict[key] = new
            total += count
        return out_dict, total
    return value, 0


def _mention_pattern(old_names) -> re.Pattern:
    # Longest first, so one name that is a prefix of another cannot win; the
    # (?!\w) end matches MENTION_RE in wagtail_forum.mentions.
    names = sorted(old_names, key=len, reverse=True)
    return re.compile(r"(?<!\w)@(" + "|".join(map(re.escape, names)) + r")(?!\w)")


class Command(BaseCommand):
    help = (
        "Rename accounts whose username was minted from their email and "
        "rewrite their @mentions. Dry run unless --apply."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the renames and mention rewrites (default: report only).",
        )
        parser.add_argument(
            "--include-password-accounts",
            action="store_true",
            help="Also rename accounts that sign in with a password.",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        include_password = options["include_password_accounts"]
        User = get_user_model()

        targets = []
        skipped = []
        for user in User.objects.exclude(email="").order_by("pk").iterator():
            if not is_email_derived(user.username, user.email):
                continue
            if has_password(user) and not include_password:
                skipped.append(user.pk)
            else:
                targets.append(user)

        for pk in skipped:
            self.stdout.write(
                f"skip id={pk}: signs in with a password "
                "(--include-password-accounts to rename)"
            )
        if not targets:
            self.stdout.write("Nothing to rename.")
            return
        if not apply:
            for user in targets:
                self.stdout.write(f"would rename id={user.pk}")
            self.stdout.write(
                f"Dry run: {len(targets)} account(s) would be renamed. "
                "Re-run with --apply."
            )
            return

        with transaction.atomic():
            renames = {}
            for user in targets:
                new = generate_username()
                renames[user.username] = new
                User.objects.filter(pk=user.pk).update(username=new)
                self.stdout.write(f"renamed id={user.pk} -> {new}")
            changed, mentions = self._rewrite_mentions(renames)

        for obj in changed:
            index.insert_or_update_object(obj)
        self.stdout.write(
            f"Renamed {len(targets)} account(s); rewrote {mentions} mention(s) "
            f"in {len(changed)} post(s)/topic(s)."
        )

    def _rewrite_mentions(self, renames: dict[str, str]):
        Post = apps.get_model("wagtail_forum", "Post")
        Topic = apps.get_model("wagtail_forum", "Topic")
        pattern = _mention_pattern(renames)
        changed = []
        total = 0

        body_field = Post._meta.get_field("body")
        for post in Post.objects.only("pk", "body").iterator():
            raw, count = _rewrite(list(post.body.raw_data), pattern, renames)
            if count:
                Post.objects.filter(pk=post.pk).update(body=body_field.to_python(raw))
                changed.append(post.pk)
                total += count

        changed_topics = []
        for topic in Topic.objects.only("pk", "title").iterator():
            title, count = _rewrite(topic.title, pattern, renames)
            if count:
                Topic.objects.filter(pk=topic.pk).update(title=title)
                changed_topics.append(topic.pk)
                total += count

        content_types = ContentType.objects.get_for_models(Post, Topic).values()
        revisions = Revision.objects.filter(base_content_type__in=content_types)
        for revision in revisions.only("pk", "content").iterator():
            content, count = _rewrite(revision.content, pattern, renames)
            if count:
                Revision.objects.filter(pk=revision.pk).update(content=content)
                total += count

        objects = list(Post.objects.filter(pk__in=changed)) + list(
            Topic.objects.filter(pk__in=changed_topics)
        )
        return objects, total
