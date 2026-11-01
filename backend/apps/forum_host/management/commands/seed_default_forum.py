from django.core.management.base import BaseCommand, CommandError
from wagtail.models import Site
from wagtail_forum.collections import get_forum_image_collection
from wagtail_forum.models import Forum, ForumIndex

# The pre-Canopy starter board this command creates. Exported so other seed
# commands (seed_demo_content) and their tests can reference the same literal
# instead of each carrying their own copy (round-2 review: third-copy dedupe).
DEFAULT_BOARD_SLUG = "general-discussion"
# The category every forum sits under (todo 665: no forum lives at the root).
# The same slug the 0041 migration gives the category it creates, so a seed
# after that migration finds it instead of adding a second "General".
DEFAULT_CATEGORY_SLUG = "general"


def ensure_default_category():
    """The default category, created on first call. Shared with
    seed_demo_content so both commands parent their forums the same way."""
    category = (
        Forum.objects.filter(forum_type=Forum.CATEGORY)
        .order_by("position", "id")
        .first()
    )
    if category is None:
        category = Forum.objects.create(
            forum_type=Forum.CATEGORY, name="General", slug=DEFAULT_CATEGORY_SLUG
        )
    return category


class Command(BaseCommand):
    help = (
        "Idempotently ensure a ForumIndex + a category with a starter forum + "
        "the forum image collection exist."
    )

    def handle(self, *args, **options):
        # The forum must live under the Site's root_page (the routable tree),
        # NOT the depth-1 treebeard root — a page attached there is a sibling
        # of Home: page.url is None and serve()/route() never reaches it
        # (audit 2026-07-17 H1).
        try:
            site_root = Site.objects.get(is_default_site=True).root_page
        except Site.DoesNotExist as exc:
            raise CommandError(
                "No default Wagtail Site found. Run migrations before seeding."
            ) from exc
        except Site.MultipleObjectsReturned as exc:
            raise CommandError(
                "Multiple default Wagtail Sites found; fix is_default_site "
                "flags before seeding."
            ) from exc

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
            # too. (Boards are Forum rows since todo 665, not child pages.)
            if not index.revisions.exists():
                index.save_revision().publish()
            self.stdout.write(
                self.style.SUCCESS("Moved ForumIndex under the site root page.")
            )
        else:
            self.stdout.write("ForumIndex 'forum' already exists.")

        category = ensure_default_category()
        if not Forum.objects.filter(forum_type=Forum.FORUM).exists():
            Forum.objects.create(
                forum_type=Forum.FORUM,
                parent=category,
                name="General Discussion",
                slug=DEFAULT_BOARD_SLUG,
                description="Talk about anything plant-related.",
            )
            self.stdout.write(
                self.style.SUCCESS(f"Created board '{DEFAULT_BOARD_SLUG}'.")
            )
        else:
            self.stdout.write("Forum already seeded; nothing to do.")

        # Seed the forum image collection here, at deploy time (single-threaded),
        # so the request-time lazy get-or-create in collections.py always finds it
        # and never races two concurrent first-ever image ops into duplicate
        # collections (todo 247). Idempotent — safe on every deploy; the lazy
        # get-or-create stays as a self-healing fallback for hosts that skip seed.
        get_forum_image_collection()
        self.stdout.write("Ensured forum image collection 'Forum Images'.")
