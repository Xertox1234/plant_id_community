from django.core.management.base import BaseCommand, CommandError
from wagtail.models import Page
from wagtail_forum.collections import get_forum_image_collection
from wagtail_forum.models import ForumBoard, ForumIndex


class Command(BaseCommand):
    help = (
        "Idempotently ensure a ForumIndex + a starter ForumBoard + the forum "
        "image collection exist."
    )

    def handle(self, *args, **options):
        index = ForumIndex.objects.first()
        if index is None:
            root = Page.objects.filter(depth=1).first()
            if root is None:
                raise CommandError(
                    "No Wagtail root page found. Run migrations before seeding."
                )
            index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
            self.stdout.write(self.style.SUCCESS("Created ForumIndex 'forum'."))
        else:
            self.stdout.write("ForumIndex 'forum' already exists.")

        if not index.get_children().type(ForumBoard).exists():
            index.add_child(
                instance=ForumBoard(
                    title="General Discussion",
                    slug="general-discussion",
                    description="Talk about anything plant-related.",
                )
            )
            self.stdout.write(self.style.SUCCESS("Created board 'general-discussion'."))
        else:
            self.stdout.write("Forum already seeded; nothing to do.")

        # Seed the forum image collection here, at deploy time (single-threaded),
        # so the request-time lazy get-or-create in collections.py always finds it
        # and never races two concurrent first-ever image ops into duplicate
        # collections (todo 247). Idempotent — safe on every deploy; the lazy
        # get-or-create stays as a self-healing fallback for hosts that skip seed.
        get_forum_image_collection()
        self.stdout.write("Ensured forum image collection 'Forum Images'.")
