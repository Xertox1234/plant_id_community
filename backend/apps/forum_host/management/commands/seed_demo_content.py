from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
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
    ForumProfile,
    Post,
    Reaction,
    Topic,
)

from apps.forum_host.seed_content import BOARDS, DEMO_EMAIL_DOMAIN, TOPICS, USERS

ASSET_DIR = Path(__file__).resolve().parent.parent.parent / "seed_assets"
# The pre-Canopy starter board seed_default_forum creates; removed only if empty.
LEGACY_STARTER_SLUG = "general-discussion"


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
        # Guard layer 2 (cannot be overridden): any real user = abort.
        User = get_user_model()
        demo_usernames = {u["username"] for u in USERS}
        real_users = User.objects.exclude(username__in=demo_usernames).exclude(
            is_superuser=True
        )
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
        created = [
            spec for spec in TOPICS if self._seed_topic(spec, boards, users)
        ]
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

    # -- users ---------------------------------------------------------------

    def _seed_users(self):
        User = get_user_model()
        users = {}
        for spec in USERS:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={"email": f"{spec['username']}@{DEMO_EMAIL_DOMAIN}"},
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
                profile = ForumProfile.for_user(user)
                profile.display_name = spec["display_name"]
                profile.title = spec["title"]
                profile.bio = spec["bio"]
                # Appointed trust: survives signal recounts (signals.py takes
                # max(current, earned) when current exceeds earned).
                profile.trust_level = spec["trust_level"]
                profile.save(
                    update_fields=["display_name", "title", "bio", "trust_level"]
                )
                self.stdout.write(f"Created demo user {spec['username']}.")
            users[spec["username"]] = user
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
                body = [
                    ("paragraph", RichText(f"<p>{p}</p>")) for p in paragraphs
                ]
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

            newest = max(ts for _, ts in post_times)
            if solution_post is not None:
                topic.solved_post = solution_post
                topic.solved_at = newest
                topic.save(update_fields=["solved_post", "solved_at"])

            # Timestamp pass — LAST, via .update() so auto_now/auto_now_add and
            # signals don't overwrite the spread (spec §5).
            for pk, ts in post_times:
                Post.objects.filter(pk=pk).update(created_at=ts, updated_at=ts)
            Topic.objects.filter(pk=topic.pk).update(
                created_at=now - timedelta(hours=opening_age),
                updated_at=newest,
                last_post_at=newest,
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
