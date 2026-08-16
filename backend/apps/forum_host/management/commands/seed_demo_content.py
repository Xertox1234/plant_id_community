from datetime import timedelta
from pathlib import Path

from apps.forum_host.management.commands.seed_default_forum import (
    DEFAULT_BOARD_SLUG as LEGACY_STARTER_SLUG,
)
from apps.forum_host.seed_content import (
    BOARDS,
    TOPICS,
    USERS,
    ensure_demo_user,
    real_users_queryset,
)
from django.core.files.images import ImageFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from wagtail.images import get_image_model
from wagtail.rich_text import RichText
from wagtail_forum.collections import get_forum_image_collection
from wagtail_forum.models import (
    ForumBoard,
    ForumIdentificationAttachment,
    ForumIndex,
    Post,
    Reaction,
    Topic,
)

ASSET_DIR = Path(__file__).resolve().parent.parent.parent / "seed_assets"
# LEGACY_STARTER_SLUG re-exports seed_default_forum's DEFAULT_BOARD_SLUG under
# this module's own name (the pre-Canopy starter board it creates; removed
# only if empty) so callers/tests keep importing a locally-meaningful name
# without a third copy of the literal (round-2 review dedupe).


class Command(BaseCommand):
    help = (
        "Idempotently seed the Canopy demo world: 5 boards, 8 demo users, "
        "16 topics with replies/solutions/reactions/images. Skip-not-overwrite: "
        "existing rows are never modified. Safe to re-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Required when DEBUG=False (production).",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        # Guard layer 1: production requires an explicit flag.
        if not settings.DEBUG and not options["confirm"]:
            raise CommandError(
                "DEBUG is False. Re-run with --confirm to seed demo content "
                "into this environment."
            )
        # Guard layer 2 (cannot be overridden): any real user = abort. Census
        # semantics live in seed_content.real_users_queryset — shared with
        # apps.blog's seed_demo_blog so the two guards cannot drift.
        real_users = real_users_queryset()
        if real_users.exists():
            raise CommandError(
                f"{real_users.count()} real user account(s) exist — refusing to "
                "seed demo content into a live community. This guard has no "
                "override flag by design (spec §5)."
            )

        # Prerequisites: ForumIndex + image collection (idempotent, tested).
        call_command("seed_default_forum")
        index = ForumIndex.objects.first()

        users = self._seed_users()
        boards = self._seed_boards(index)
        self._remove_empty_starter_board()
        created = [spec for spec in TOPICS if self._seed_topic(spec, boards, users)]
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {len(created)} topic(s) created, "
                f"{len(TOPICS) - len(created)} already present."
            )
        )
        if created:
            # Content changed under the search index's feet (timestamps moved
            # post-publish); refresh so search reflects the seeded world.
            call_command("update_index", verbosity=0)
        # Blog half of the demo world (spec 2026-08-16 §5): one prod entry
        # point. --confirm MUST forward — in production the blog command's
        # own layer-1 guard would otherwise abort this single-entry runbook.
        call_command("seed_demo_blog", confirm=options["confirm"])

    # -- users ---------------------------------------------------------------

    def _seed_users(self):
        users = {}
        # Atomic across the whole spec list: a mid-loop adoption refusal must
        # roll back any demo users this same call already created, not leave a
        # partially-seeded user set behind (spec-consistent with the "seed
        # aborts with no content created" contract for guard failures).
        with transaction.atomic():
            for spec in USERS:
                users[spec["username"]] = ensure_demo_user(spec, self.stdout)
        return users

    # -- boards --------------------------------------------------------------

    def _seed_boards(self, index):
        boards = {}
        for spec in BOARDS:
            board = ForumBoard.objects.filter(slug=spec["slug"]).first()
            if board is None:
                board = index.add_child(
                    instance=ForumBoard(
                        title=spec["title"],
                        slug=spec["slug"],
                        description=spec["description"],
                    )
                )
                board.save_revision().publish()
                self.stdout.write(f"Created board {spec['slug']}.")
            boards[spec["slug"]] = board
        return boards

    def _remove_empty_starter_board(self):
        starter = ForumBoard.objects.filter(slug=LEGACY_STARTER_SLUG).first()
        if starter is None:
            return
        if starter.topics.exists():
            self.stdout.write(
                f"Board '{LEGACY_STARTER_SLUG}' has topics — keeping it "
                "(spec §3: never delete content)."
            )
            return
        starter.delete()
        self.stdout.write(f"Removed empty starter board '{LEGACY_STARTER_SLUG}'.")

    # -- topics --------------------------------------------------------------

    def _seed_topic(self, spec, boards, users):
        """Create one topic + its world. Topic-granular idempotency: if the
        slug already exists on its board, skip ENTIRELY (spec §5 — manual
        edits always win). Returns True when created."""
        board = boards[spec["board"]]
        if Topic.objects.filter(board=board, slug=spec["slug"]).exists():
            return False

        now = timezone.now()
        with transaction.atomic():
            topic = Topic.objects.create(
                board=board,
                title=spec["title"],
                slug=spec["slug"],
                author=users[spec["author"]],
                is_pinned=spec["pinned"],
            )
            post_times = []

            def publish_post(author, paragraphs, image_name, opening, age_hours):
                body = [("paragraph", RichText(f"<p>{p}</p>")) for p in paragraphs]
                if image_name:
                    body.append(("image", self._get_image(image_name)))
                post = Post.objects.create(
                    topic=topic,
                    author=author,
                    body=body,
                    is_opening_post=opening,
                )
                post.save_revision().publish()
                post_times.append((post.pk, now - timedelta(hours=age_hours)))
                return post

            opening_age = spec["age_days"] * 24
            publish_post(
                users[spec["author"]],
                spec["opening"]["paragraphs"],
                spec["opening"].get("image"),
                True,
                opening_age,
            )
            solution_post = None
            for reply in spec["replies"]:
                post = publish_post(
                    users[reply["author"]],
                    reply["paragraphs"],
                    reply.get("image"),
                    False,
                    reply["age_hours"],
                )
                if reply.get("solution"):
                    solution_post = post
                for rtype, names in reply.get("reactions", {}).items():
                    for name in names:
                        Reaction.objects.get_or_create(
                            post=post, user=users[name], reaction_type=rtype
                        )
                    Reaction.recount(post)

            if spec.get("identification"):
                ForumIdentificationAttachment.objects.create(
                    topic=topic,
                    provider=spec["identification"]["provider"],
                    candidates=spec["identification"]["candidates"],
                )

            post_times_by_pk = dict(post_times)
            newest = max(ts for _, ts in post_times)
            if solution_post is not None:
                topic.solved_post = solution_post
                # The ACCEPTED POST's own timestamp, not the thread's newest —
                # a solution is frequently not the last reply (later replies
                # can be follow-up chatter after the answer landed).
                topic.solved_at = post_times_by_pk[solution_post.pk]
                topic.save(update_fields=["solved_post", "solved_at"])

            # Timestamp pass — LAST, via .update() so auto_now/auto_now_add and
            # signals don't overwrite the spread (spec §5). first_published_at/
            # last_published_at are back-dated too, not just created_at/
            # updated_at: signals._refresh_topic_counters recomputes
            # topic.last_post_at from live posts' first_published_at on ANY
            # later recount (unpublish, delete, report-hide, ...), so leaving
            # those columns at the real seed-run wall-clock would snap a
            # topic's curated age back to "now" the moment anything triggers
            # a recount.
            topic_ts = now - timedelta(hours=opening_age)
            for pk, ts in post_times:
                Post.objects.filter(pk=pk).update(
                    created_at=ts,
                    updated_at=ts,
                    first_published_at=ts,
                    last_published_at=ts,
                )
            Topic.objects.filter(pk=topic.pk).update(
                created_at=topic_ts,
                updated_at=newest,
                last_post_at=newest,
                first_published_at=topic_ts,
                last_published_at=topic_ts,
            )
        self.stdout.write(f"Created topic {spec['slug']} on {spec['board']}.")
        return True

    # -- images --------------------------------------------------------------

    def _get_image(self, asset_name):
        Image = get_image_model()
        title = f"Seed: {asset_name}"
        existing = Image.objects.filter(title=title).first()
        if existing:
            return existing
        path = ASSET_DIR / asset_name
        if not path.exists():
            raise CommandError(f"Missing seed asset: {path}")
        with path.open("rb") as fh:
            return Image.objects.create(
                title=title,
                file=ImageFile(fh, name=asset_name),
                collection=get_forum_image_collection(),
            )
