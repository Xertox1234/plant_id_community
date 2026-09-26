"""Management command: delete password accounts that never verified or came back.

Registration creates a usable account at once and mails a verification link
(todo 446). An account whose owner never confirms the address and never signs
in again is either abandoned or a squatter holding someone else's address,
which blocks the real owner's Google sign-in (todo 447 item 2). This command
deletes those accounts. Owner decision 2026-09-25; run nightly from the
``forum-prune-cron`` Railway service.

An account is deleted only when ALL of these hold:

- **It signs in with a password** (``account_links.has_password``: a non-empty
  hash that Django counts as usable; Firebase creates users with ``""``).
- **It never verified an address**: no verified ``EmailAddress`` row at all.
- **It is not linked to a provider**: no ``firebase_uid``, no ``SocialAccount``.
- **It is not staff or a superuser.**
- **It is older than** ``UNVERIFIED_ACCOUNT_EXPIRY_DAYS``.
- **It never signed in after registering.** ``last_login`` is empty or falls
  within ``UNVERIFIED_ACCOUNT_SIGNUP_MARGIN_SECONDS`` of ``date_joined``, and
  no refresh token was issued after that margin. The refresh view issues a
  new token on every rotation, so a user who kept the registration session
  alive counts as active although ``last_login`` never moved. Nothing runs
  ``flushexpiredtokens``; if something ever does, ``last_login`` still holds.
- **It wrote nothing in the forum**: no post, no topic, no Wagtail revision.
- **It holds nothing registration did not create.** Registration's access
  token works for 15 minutes, so a user can post, message, comment or run a
  plant ID without ever signing in again. Every relation to the user is
  counted, hidden ones included, against what registration itself leaves
  behind: one refresh token, one unverified ``EmailAddress``, the default
  plant collection and the forum members group. Anything else keeps the
  account and is logged. A model added later is covered without editing this
  file, and an unexpected row errs towards keeping the account.

Candidates are listed first. Each is then re-checked and deleted in its own
transaction under a row lock, so an account that signs in while the command
runs is kept.

``--dry-run`` reports what would go and deletes nothing. Log lines carry the
account id only, never the email or username.
"""

import logging
from datetime import timedelta

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from apps.users.account_links import has_password
from apps.users.constants import (
    UNVERIFIED_ACCOUNT_EXPIRY_DAYS,
    UNVERIFIED_ACCOUNT_SIGNUP_MARGIN_SECONDS,
)
from apps.users.signup import DEFAULT_COLLECTION_NAME, FORUM_MEMBERS_GROUP_NAME
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

logger = logging.getLogger(__name__)

# What registration itself creates, by model label: at most this many rows.
# Every other reverse relation must be empty.
SIGNUP_ROWS = {
    "token_blacklist.OutstandingToken": 1,
    "account.EmailAddress": 1,
    "users.UserPlantCollection": 1,
}


def _candidates(now):
    """Accounts that pass every rule that SQL can check."""
    from wagtail.models import Revision
    from wagtail_forum.models import Post, Topic

    User = get_user_model()
    margin = timedelta(seconds=UNVERIFIED_ACCOUNT_SIGNUP_MARGIN_SECONDS)
    later_token = OutstandingToken.objects.filter(
        user=OuterRef("pk"), created_at__gt=OuterRef("date_joined") + margin
    )
    return (
        User.objects.filter(
            date_joined__lt=now - timedelta(days=UNVERIFIED_ACCOUNT_EXPIRY_DAYS),
            is_staff=False,
            is_superuser=False,
        )
        .filter(Q(firebase_uid__isnull=True) | Q(firebase_uid=""))
        .filter(
            Q(last_login__isnull=True) | Q(last_login__lte=F("date_joined") + margin)
        )
        .exclude(password="")
        .exclude(Exists(later_token))
        .exclude(Exists(SocialAccount.objects.filter(user=OuterRef("pk"))))
        .exclude(
            Exists(EmailAddress.objects.filter(user=OuterRef("pk"), verified=True))
        )
        .exclude(Exists(Post.objects.filter(author=OuterRef("pk"))))
        .exclude(Exists(Topic.objects.filter(author=OuterRef("pk"))))
        .exclude(Exists(Revision.objects.filter(user=OuterRef("pk"))))
    )


def _extra_data(user):
    """The label of the first data ``user`` holds beyond registration's own
    rows, or ``None``. Uses base managers so no custom manager hides a row."""
    for field in user._meta.get_fields(include_hidden=True):
        if not field.is_relation:
            continue
        if field.auto_created and not field.concrete:
            model = field.related_model
            # An auto-created m2m through table repeats a forward m2m field,
            # which is checked below.
            if model._meta.auto_created:
                continue
            label = model._meta.label
            rows = model._base_manager.filter(**{field.field.name: user})
            if rows.count() > SIGNUP_ROWS.get(label, 0):
                return label
            if (
                label == "users.UserPlantCollection"
                and rows.exclude(name=DEFAULT_COLLECTION_NAME).exists()
            ):
                return label
        elif field.many_to_many or field.one_to_many:
            # Forward m2m (groups, permissions, following, tags) and generic
            # relations.
            related = getattr(user, field.name).all()
            if field.name == "groups":
                related = related.exclude(name=FORUM_MEMBERS_GROUP_NAME)
            if related.exists():
                return f"{user._meta.label}.{field.name}"
    return None


class Command(BaseCommand):
    help = (
        "Delete password accounts that never verified their email, never signed "
        "in after registering and hold no data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()
        candidate_ids = list(
            _candidates(now).order_by("pk").values_list("pk", flat=True)
        )

        deleted = 0
        kept = 0
        failed = 0
        for pk in candidate_ids:
            try:
                with transaction.atomic():
                    user = _candidates(now).select_for_update().filter(pk=pk).first()
                    if user is None:
                        logger.info("[PRUNE] account %s changed; kept", pk)
                        kept += 1
                        continue
                    if not has_password(user):
                        logger.info("[PRUNE] account %s has no password; kept", pk)
                        kept += 1
                        continue
                    extra = _extra_data(user)
                    if extra:
                        logger.info("[PRUNE] account %s has %s rows; kept", pk, extra)
                        kept += 1
                        continue
                    if dry_run:
                        logger.info("[PRUNE] would delete unverified account %s", pk)
                        deleted += 1
                        continue
                    # SET_NULL would leave the tokens behind with no user.
                    OutstandingToken.objects.filter(user=user).delete()
                    user.delete()
            except Exception:
                logger.exception("[PRUNE] could not delete account %s", pk)
                failed += 1
                continue
            logger.info("[PRUNE] deleted unverified account %s", pk)
            deleted += 1

        verb = "would delete" if dry_run else "deleted"
        self.stdout.write(
            f"[PRUNE] unverified accounts: {len(candidate_ids)} candidate(s) older "
            f"than {UNVERIFIED_ACCOUNT_EXPIRY_DAYS}d, {kept} kept, "
            f"{verb} {deleted}, {failed} failed."
        )
        if failed:
            raise CommandError(f"[PRUNE] {failed} account(s) could not be deleted")
