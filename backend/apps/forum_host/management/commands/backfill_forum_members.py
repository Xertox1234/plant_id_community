"""One-off backfill: add every existing user to the "Forum Members" group.

New signups join this group automatically (apps.users.signup.
join_forum_members_group, called from every signup path). Users created
before that change shipped need a one-time catch-up so they get the same
Wagtail image permissions (add_image/choose_image on the forum collection —
see apps.forum_host.bootstrap._ensure_forum_image_permissions) without
having to sign up again. Safe to run more than once: group membership is a
plain M2M, adding an existing member is a no-op.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    # One INSERT per batch. Sized like REDIRECT_BULK_CREATE_BATCH_SIZE in
    # forum_host/constants.py — well under Postgres's 65,535 bind-parameter
    # cap with one parameter per row.
    BATCH_SIZE = 1000

    help = (
        'Add every existing user to the "Forum Members" group, so they get '
        "the same forum image permissions new signups get automatically."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many users would be added without changing anything.",
        )

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name="Forum Members")
        if created:
            self.stdout.write(
                'Created the "Forum Members" group (normally created by the '
                "forum_host post_migrate bootstrap — run migrations first if "
                "you did not expect this)."
            )

        already_in = User.objects.filter(groups=group)
        to_add = User.objects.exclude(pk__in=already_in.values("pk"))
        count = to_add.count()

        if options["dry_run"]:
            self.stdout.write(f"Would add {count} user(s) to Forum Members.")
            return

        # Chunked, not `add(*to_add)`: on the first production run EVERY user
        # is in `to_add`, and unpacking the whole queryset materializes every
        # instance in memory and builds one enormous INSERT. Values-only +
        # `iterator()` keeps both bounded regardless of table size.
        added = 0
        batch = []
        for pk in to_add.values_list("pk", flat=True).iterator(
            chunk_size=self.BATCH_SIZE
        ):
            batch.append(pk)
            if len(batch) >= self.BATCH_SIZE:
                group.user_set.add(*batch)
                added += len(batch)
                batch = []
        if batch:
            group.user_set.add(*batch)
            added += len(batch)
        self.stdout.write(
            self.style.SUCCESS(f"Added {added} user(s) to Forum Members.")
        )
