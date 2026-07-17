from django.core.management.base import BaseCommand, CommandError
from wagtail.models import Site
from wagtail_forum.collections import get_forum_image_collection
from wagtail_forum.models import ForumBoard, ForumIndex


class Command(BaseCommand):
    help = (
        "Idempotently ensure a ForumIndex + a starter ForumBoard + the forum "
        "image collection exist."
    )

    def handle(self, *args, **options):
        # The forum must live under the Site's root_page (the routable tree),
        # NOT the depth-1 treebeard root — a page attached there is a sibling
        # of Home: page.url is None and serve()/route() never reaches it
        # (audit 2026-07-17 H1).
        try:
            site_root = Site.objects.get(is_default_site=True).root_page
        except Site.DoesNotExist:
            raise CommandError(
                "No default Wagtail Site found. Run migrations before seeding."
            )
        except Site.MultipleObjectsReturned:
            raise CommandError(
                "Multiple default Wagtail Sites found; fix is_default_site "
                "flags before seeding."
            )

        index = ForumIndex.objects.first()
        if index is None:
            index = site_root.add_child(
                instance=ForumIndex(title="Forum", slug="forum")
            )
            # Bare add_child leaves live=True with zero revisions and no
            # first_published_at; publish a revision for parity with
            # admin-created pages (audit 2026-07-17 L1). These page types
            # carry no moderation workflow, so publishing directly is safe.
            index.save_revision().publish()
            self.stdout.write(self.style.SUCCESS("Created ForumIndex 'forum'."))
        elif not index.is_descendant_of(site_root):
            # Repair a pre-audit seed that attached the forum outside the
            # routable tree; move() also fixes descendant url_paths.
            index.move(site_root, pos="last-child")
            index = ForumIndex.objects.get(pk=index.pk)
            # A pre-audit seed also never published a revision — repair that
            # too, for the index and any boards it already contains.
            for page in [index, *index.get_children().type(ForumBoard).specific()]:
                if not page.revisions.exists():
                    page.save_revision().publish()
            self.stdout.write(
                self.style.SUCCESS("Moved ForumIndex under the site root page.")
            )
        else:
            self.stdout.write("ForumIndex 'forum' already exists.")

        if not index.get_children().type(ForumBoard).exists():
            board = index.add_child(
                instance=ForumBoard(
                    title="General Discussion",
                    slug="general-discussion",
                    description="Talk about anything plant-related.",
                )
            )
            board.save_revision().publish()
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
