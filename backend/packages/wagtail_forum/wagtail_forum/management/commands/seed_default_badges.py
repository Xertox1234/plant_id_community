"""Management command: seed the default badge set (todo 348).

The package ships NO badge rows — the engine is inert until a host seeds
some — so this is the host's opt-in, wired into the deploy's
``preDeployCommand`` beside ``seed_default_forum``. Idempotent on ``slug``:
an existing badge is left exactly as the CMS editor last saved it (name,
description, rules and all), so re-running on every deploy never undoes
curation; only MISSING badges are created.

The Botanist badge is the pre-engine hardcoded badge migrated onto the
engine: same name and threshold settings (``BADGE_BOTANIST_NAME`` /
``BADGE_BOTANIST_THRESHOLD``) read at seed time. Once seeded, the badge's
``BadgeRule`` is the single source of truth — ``GET me/stats/`` reads its
threshold and the row's name for the progress bar, and the settings only
serve an unseeded host (``wagtail_forum.badges.botanist_badge_rule``), so
retune the badge in Snippets → Badges, not the setting.
"""

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.db.models import Q


class Command(BaseCommand):
    help = "Create any missing default forum badges (idempotent; never edits existing ones)."

    def handle(self, *args, **options):
        from wagtail_forum.conf import get_setting
        from wagtail_forum.models.badges import Badge, BadgeMetric, BadgeRule

        defaults = [
            (
                "first-post",
                "First post",
                "Published a first post.",
                10,
                BadgeMetric.POSTS,
                1,
            ),
            (
                "first-solution",
                "First solution",
                "Had an answer accepted for the first time.",
                20,
                BadgeMetric.SOLUTIONS_ACCEPTED,
                1,
            ),
            (
                "botanist",
                get_setting("BADGE_BOTANIST_NAME"),
                "Shared plant identifications with the community.",
                30,
                BadgeMetric.IDENTIFICATIONS_SHARED,
                get_setting("BADGE_BOTANIST_THRESHOLD"),
            ),
            (
                "streak-7",
                "Week streak",
                "Posted seven days in a row.",
                40,
                BadgeMetric.STREAK_DAYS,
                7,
            ),
            (
                "streak-30",
                "Month streak",
                "Posted thirty days in a row.",
                50,
                BadgeMetric.STREAK_DAYS,
                30,
            ),
        ]
        created = 0
        skipped = []
        for slug, name, description, order, metric, threshold in defaults:
            # `name` is unique and CMS-editable too (review): an editor who
            # renamed a custom badge "First post" must not turn this
            # pre-deploy step into an IntegrityError that blocks every
            # later deploy. Skip on EITHER key, and keep the create in its
            # own savepoint so a concurrent/racing insert degrades to
            # "not seeded" rather than a failed command.
            if Badge.objects.filter(Q(slug=slug) | Q(name=name)).exists():
                skipped.append(slug)
                continue
            try:
                with transaction.atomic():
                    badge = Badge.objects.create(
                        slug=slug, name=name, description=description, order=order
                    )
                    BadgeRule.objects.create(
                        badge=badge, metric=metric, threshold=threshold
                    )
            except IntegrityError:
                skipped.append(slug)
                continue
            created += 1
        if skipped:
            self.stdout.write(
                self.style.WARNING(
                    "Left as-is (slug or name already taken): " + ", ".join(skipped)
                )
            )
        self.stdout.write(
            self.style.SUCCESS(f"Seeded {created} missing badge(s) of {len(defaults)}.")
        )
