"""Management command: (re-)evaluate badge awards (todo 348).

Awards are normally granted at the moment a member qualifies (signal
pipeline) and lazily when they open ``GET me/stats/``. This is the bulk
path for the other cases: a badge seeded or re-tuned AFTER members already
qualified, or the one-time backfill when the engine first ships. Idempotent
— evaluation never double-awards and never revokes.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Award every badge each member now qualifies for (idempotent; never revokes)."
    )

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--all", action="store_true", help="Every member with a forum profile."
        )
        group.add_argument("--username", help="One member, by username.")

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        from wagtail_forum.badges import award_badges_for_user
        from wagtail_forum.models import ForumProfile

        if options["username"]:
            User = get_user_model()
            user = User._base_manager.filter(username=options["username"]).first()
            if user is None:
                self.stderr.write(self.style.ERROR(f"No user {options['username']!r}."))
                return
            user_ids = [user.pk]
        else:
            # Members without a ForumProfile have never written in the forum,
            # so every metric is zero for them — nothing to evaluate.
            # .iterator(): a bulk backfill over every profile must not hold
            # the whole id list in memory (docs/rules/database.md).
            user_ids = (
                ForumProfile.objects.order_by("user_id")
                .values_list("user_id", flat=True)
                .iterator(chunk_size=500)
            )

        evaluated = awarded = 0
        for user_id in user_ids:
            evaluated += 1
            awarded += len(award_badges_for_user(user_id))
        self.stdout.write(
            self.style.SUCCESS(
                f"Evaluated {evaluated} member(s); awarded {awarded} new badge(s)."
            )
        )
