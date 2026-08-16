from datetime import timedelta
from pathlib import Path

from apps.blog.models import BlogCategory, BlogIndexPage, BlogPostPage
from apps.blog.seed_content import AUTHOR_NAMES, CATEGORIES, POSTS
from apps.forum_host.seed_content import USERS, ensure_demo_user, real_users_queryset
from django.core.files.images import ImageFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from wagtail.images import get_image_model
from wagtail.models import Collection, Page, Site

ASSET_DIR = Path(__file__).resolve().parent.parent.parent / "seed_assets"
IMAGE_COLLECTION_NAME = "Blog images"


class Command(BaseCommand):
    help = (
        "Idempotently seed the Canopy demo blog: BlogIndexPage, 4 categories, "
        "6 posts with committed cover images. Skip-not-overwrite: existing "
        "rows are never modified. Safe to re-run."
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
        # Census semantics are shared with seed_demo_content via
        # forum_host.seed_content.real_users_queryset (spec §5 — one source).
        real_users = real_users_queryset()
        if real_users.exists():
            raise CommandError(
                f"{real_users.count()} real user account(s) exist — refusing to "
                "seed demo content into a live community. This guard has no "
                "override flag by design (spec §5)."
            )

        index = self._ensure_index()
        categories = self._seed_categories()
        authors = self._ensure_authors()
        created = [
            spec for spec in POSTS if self._seed_post(spec, index, categories, authors)
        ]
        self.stdout.write(
            self.style.SUCCESS(
                f"Blog seed complete: {len(created)} post(s) created, "
                f"{len(POSTS) - len(created)} already present."
            )
        )
        if created:
            # The forum half may have skipped (and not refreshed) — refresh
            # here so search reflects the seeded posts.
            call_command("update_index", verbosity=0)

    # -- page tree ----------------------------------------------------------

    def _ensure_index(self):
        # Must live under the Site's root_page (the routable tree), NOT the
        # depth-1 treebeard root — same audit-H1 constraint seed_default_forum
        # documents: a page attached there has url None and is never served.
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

        index = BlogIndexPage.objects.first()
        if index is None:
            index = site_root.add_child(
                instance=BlogIndexPage(title="Blog", slug="blog")
            )
            index.save_revision().publish()
            self.stdout.write(self.style.SUCCESS("Created BlogIndexPage 'blog'."))
        elif not index.is_descendant_of(site_root):
            index.move(site_root, pos="last-child")
            index = BlogIndexPage.objects.get(pk=index.pk)
            if not index.revisions.exists():
                index.save_revision().publish()
            self.stdout.write(
                self.style.SUCCESS("Moved BlogIndexPage under the site root page.")
            )
        return index

    # -- categories / authors ----------------------------------------------

    def _seed_categories(self):
        categories = {}
        for spec in CATEGORIES:
            category, created = BlogCategory.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "description": spec["description"],
                },
            )
            if created:
                self.stdout.write(f"Created category {spec['slug']}.")
            categories[spec["slug"]] = category
        return categories

    def _ensure_authors(self):
        specs = {u["username"]: u for u in USERS}
        authors = {}
        # Atomic like the forum seed's user pass: an adoption refusal must
        # roll back any demo users this call created.
        with transaction.atomic():
            for username, (first, last) in AUTHOR_NAMES.items():
                user = ensure_demo_user(specs[username], self.stdout)
                # Fill-if-blank ONLY (spec §5): the blog author line reads
                # User.get_full_name(); a manually customised name wins.
                if not user.first_name and not user.last_name:
                    user.first_name = first
                    user.last_name = last
                    user.save(update_fields=["first_name", "last_name"])
                authors[username] = user
        return authors

    # -- posts ---------------------------------------------------------------

    def _seed_post(self, spec, index, categories, authors):
        """Create one post. Post-granular idempotency: if the slug exists
        anywhere, skip ENTIRELY (manual edits always win). Returns True when
        created."""
        if BlogPostPage.objects.filter(slug=spec["slug"]).exists():
            return False

        published_at = timezone.now() - timedelta(days=spec["age_days"])
        with transaction.atomic():
            post = index.add_child(
                instance=BlogPostPage(
                    title=spec["title"],
                    slug=spec["slug"],
                    author=authors[spec["author"]],
                    publish_date=published_at.date(),
                    introduction=spec["introduction"],
                    content_blocks=spec["blocks"],
                    featured_image=self._get_image(spec["cover"]),
                    view_count=spec["view_count"],
                )
            )
            post.categories.add(categories[spec["category"]])
            # reading_time auto-computes in BlogPostPage.save() when unset —
            # the stored value derives from the real body (spec §9).
            post.save_revision().publish()
            # Back-date LAST (publish-fields lesson): first/last_published_at
            # live on the wagtailcore.Page PARENT table — MTI means a
            # BlogPostPage-queryset .update() cannot touch them (spec §12).
            Page.objects.filter(pk=post.pk).update(
                first_published_at=published_at,
                last_published_at=published_at,
            )
        self.stdout.write(f"Created blog post {spec['slug']}.")
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
                collection=self._get_collection(),
            )

    def _get_collection(self):
        # Management-command context: single caller, no concurrent first-use
        # race — the forum's select_for_update dance (wagtail_forum/
        # collections.py) is unnecessary here.
        root = Collection.get_first_root_node()
        existing = root.get_children().filter(name=IMAGE_COLLECTION_NAME).first()
        if existing is not None:
            return existing
        return root.add_child(name=IMAGE_COLLECTION_NAME)
