"""
Custom Wagtail API serializers for blog models.

Provides headless CMS functionality with StreamField rendering,
filtering capabilities, and plant-specific content integration.
"""

import logging

from django.db.models import Count, Prefetch, Q
from django.utils.text import Truncator
from rest_framework import serializers
from wagtail.api.v2.serializers import BaseSerializer, PageSerializer
from wagtail.api.v2.serializers import StreamField as StreamFieldAPIField
from wagtail.images.api.fields import ImageRenditionField
from wagtail.images.models import Image, SourceImageIOError
from wagtail.rich_text import get_text_for_indexing

from ..models import (
    BlogAuthorPage,
    BlogCategory,
    BlogCategoryPage,
    BlogIndexPage,
    BlogPostPage,
    BlogSeries,
)

logger = logging.getLogger(__name__)


def _absolute_page_url(request, page):
    """A page's absolute URL, derived from the request's own host (todo 308).

    `Page.get_url()` decides whether to return a relative or an
    already-absolute URL by counting Wagtail `Site` rows, and prepends the
    *Site's* `root_url` (not the request's host) when it picks "absolute" —
    exactly the mechanism that resolved every URL in this API to
    `http://localhost/...` in production (no Site row was ever configured
    for the real domain). `request.build_absolute_uri()` passes an
    already-absolute string through unchanged, so calling it on
    `get_url()`'s output wouldn't fix that.

    `get_url_parts()` instead returns the page's path relative to its own
    site root directly — never Site-rooted-absolute — so building the
    absolute URL from `request` here always reflects the actual incoming
    host, regardless of how many `Site` rows exist. Returns None if the
    page isn't routable, or the bare relative path if called with no
    request (matching the pre-fix behavior of a request-less URL lookup).

    KNOWN GAP, not fixed here (see todo 328): if a page ever belongs to
    more than one Wagtail `Site` (e.g. one nested under another's root),
    Wagtail's own disambiguation inside `get_url_parts()` — matching the
    *actual* request against `Site.find_for_request()` — only runs when
    `isinstance(request, HttpRequest)` is true, and DRF's `Request` wrapper
    (what `self.context["request"]` actually is here) does not subclass
    it, so that branch never fires and Wagtail falls back to an arbitrary
    candidate site's root when slicing `page_path`. Unwrapping to the
    underlying `HttpRequest` (`request._request`) makes the check pass,
    but was tested and found to make Wagtail's own
    `Site.find_for_request()` reachable in a new place — introducing rare,
    unreproduced-root-cause test flakiness (apps.blog's suite failed
    Site.DoesNotExist in an unrelated admin-dashboard test on 1 of 7
    full-suite runs with the unwrap, 0 of 5 without it). Not worth the
    risk for a topology this project doesn't use today (a single flat
    Site tree, confirmed zero nested-Site configuration) — deliberately
    left as-is; see todo 328 if this project ever adopts nested Sites.
    """
    url_parts = page.get_url_parts(request=request)
    page_path = url_parts[2] if url_parts else None
    if not page_path:
        return None
    return request.build_absolute_uri(page_path) if request else page_path


class RequestAwareImageRenditionField(ImageRenditionField):
    """`ImageRenditionField` with a `full_url` built via `request.build_absolute_uri()`.

    `Rendition.full_url` (the stock field's source) prefixes with the
    single global `settings.WAGTAILADMIN_BASE_URL`, which is unrelated to
    and independent from the request that's actually serving this
    response — that's two separate, disagreeing mechanisms for the same
    job (todo 306 AC4); this collapses image URLs onto the one every other
    URL built by this file's own serializers now uses (todo 308). Building
    from `request` means the host is always correct regardless of Wagtail
    `Site` configuration. (Wagtail's own stock `meta.html_url`/
    `detail_url` fields are a separate mechanism this doesn't touch — see
    todo 327.)
    """

    def to_representation(self, image):
        data = super().to_representation(image)
        if "error" in data:
            return data
        request = self.context.get("request")
        # Explicit None without a request, not a silent fall-through to the
        # superclass's Rendition.full_url (the settings-based mechanism this
        # field exists to replace) — matches _get_post_image's contract
        # (same file) so both degrade the same way with no request in
        # context (code review, todo 306).
        data["full_url"] = request.build_absolute_uri(data["url"]) if request else None
        return data


class BlogCategorySerializer(BaseSerializer):
    """Serializer for blog categories as snippets."""

    post_count = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    # Wagtail API expects meta_fields attribute (fields shown in 'meta' section)
    meta_fields = ["type", "detail_url"]

    class Meta:
        model = BlogCategory
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "color",
            "is_featured",
            "post_count",
            "url",
            "created_at",
        ]

    def get_post_count(self, obj):
        """Get number of live published posts in this category."""
        if hasattr(obj, "annotated_post_count"):
            return obj.annotated_post_count
        return obj.blogpostpage_set.live().public().count()

    def get_url(self, obj):
        """Get category page URL if it exists."""
        request = self.context.get("request")
        # Cache per request to avoid N+1 when serializing many categories
        url_cache = self.context.setdefault("_category_page_url_cache", {})
        if obj.id not in url_cache:
            category_page = BlogCategoryPage.objects.filter(category=obj).live().first()
            if category_page and request:
                url_cache[obj.id] = _absolute_page_url(request, category_page)
            else:
                url_cache[obj.id] = None
        return url_cache[obj.id]


class BlogSeriesSerializer(BaseSerializer):
    """Serializer for blog series as snippets."""

    post_count = serializers.SerializerMethodField()
    cover_image = RequestAwareImageRenditionField(
        "fill-300x200", source="image", read_only=True
    )
    posts_url = serializers.SerializerMethodField()

    # Wagtail API expects meta_fields attribute (fields shown in 'meta' section)
    meta_fields = ["type", "detail_url"]

    class Meta:
        model = BlogSeries
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "cover_image",
            "is_completed",
            "post_count",
            "posts_url",
            "created_at",
        ]

    def get_post_count(self, obj):
        """Get number of posts in this series."""
        if hasattr(obj, "annotated_post_count"):
            return obj.annotated_post_count
        return obj.blogpostpage_set.live().public().count()

    def get_posts_url(self, obj):
        """Get URL to fetch posts in this series."""
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(
                f"/api/v2/pages/?type=blog.BlogPostPage&series={obj.id}"
            )
        return None


class BlogAuthorPageSerializer(PageSerializer):
    """Serializer for blog author pages."""

    # Wagtail's `BaseSerializer.to_representation()` unconditionally reads
    # `self.meta_fields` to split meta fields (type/detail_url/etc.) from
    # core fields. Normally that's injected by Wagtail's own dynamic
    # `get_serializer_class()` factory — bypassed here since
    # `BlogAuthorPageViewSet.get_serializer_class()` returns this class
    # directly (todo 324) — so it must be set explicitly, same as
    # `BlogCategorySerializer`/`BlogSeriesSerializer` above.
    meta_fields = ["type", "detail_url"]

    # Must be declared explicitly: `Page` has its own `url` property, so
    # without this DRF's auto field-building wins over `get_url()` below
    # and silently reintroduces the todo-308 bug (confirmed empirically —
    # matches the working `BlogCategorySerializer.url` pattern above).
    url = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    expertise_areas = serializers.SerializerMethodField()
    post_count = serializers.SerializerMethodField()
    recent_posts = serializers.SerializerMethodField()

    class Meta:
        model = BlogAuthorPage
        fields = ["id", "title", "slug", "url"] + [
            "author",
            "bio",
            "expertise_areas",
            "social_links",
            "post_count",
            "recent_posts",
        ]

    def get_url(self, obj):
        """Request-derived URL (todo 308's fix), not `Page.get_url(request=None)`.

        Without this override, DRF auto-builds `url` as a bare
        `ReadOnlyField()` reading the model's `url` property directly — the
        same Site-based host bug todo 308 fixed on every other serializer
        in this file (todo 324).
        """
        return _absolute_page_url(self.context.get("request"), obj)

    def get_author(self, obj):
        """Get author user data."""
        if obj.author:
            return {
                "id": obj.author.id,
                "username": obj.author.username,
                "first_name": obj.author.first_name,
                "last_name": obj.author.last_name,
                "display_name": obj.author.get_full_name() or obj.author.username,
            }
        return None

    def get_expertise_areas(self, obj):
        """Get expertise area tags."""
        return [tag.name for tag in obj.expertise_areas.all()]

    def get_post_count(self, obj):
        """Get number of published posts by this author."""
        if not obj.author:
            return 0
        if hasattr(obj, "annotated_post_count"):
            return obj.annotated_post_count
        return BlogPostPage.objects.live().public().filter(author=obj.author).count()

    def get_recent_posts(self, obj):
        """Get recent posts by this author."""
        if not obj.author:
            return []

        recent_posts = (
            BlogPostPage.objects.live()
            .public()
            .filter(author=obj.author)
            .select_related("author", "series")
            .prefetch_related("categories", "tags")
            .order_by("-first_published_at")[:3]
        )

        return [
            {
                "id": post.id,
                "title": post.title,
                "slug": post.slug,
                "url": _absolute_page_url(self.context.get("request"), post),
                "published_date": post.first_published_at,
                "excerpt": self._get_excerpt(post),
            }
            for post in recent_posts
        ]

    def _get_excerpt(self, post):
        """Extract excerpt from post introduction."""
        if post.introduction:
            text = get_text_for_indexing(post.introduction)
            return Truncator(text).words(30)
        return ""


class BlogPostPageSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for blog posts with full content."""

    author = serializers.SerializerMethodField()
    categories = BlogCategorySerializer(many=True, read_only=True)
    tags = serializers.SerializerMethodField()
    series = BlogSeriesSerializer(read_only=True)
    # Structured blocks (heading/paragraph/quote/code/plant_spotlight/...),
    # not a stringified JSON blob — Wagtail's own API v2 StreamField field
    # (todo 306 AC3). plant_spotlight's image resolves to a full rendition
    # dict via APIImageChooserBlock (apps/blog/blocks.py), not a bare PK.
    content_blocks = StreamFieldAPIField(read_only=True)
    featured_image = RequestAwareImageRenditionField("fill-800x400", read_only=True)
    featured_image_thumb = RequestAwareImageRenditionField(
        "fill-300x200", source="featured_image", read_only=True
    )
    reading_time = serializers.ReadOnlyField()
    excerpt = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    related_posts = serializers.SerializerMethodField()
    related_plant_species = serializers.SerializerMethodField()
    social_image = RequestAwareImageRenditionField("fill-1200x630", read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = BlogPostPage
        fields = [
            "id",
            "title",
            "slug",
            "url",
            "author",
            "publish_date",
            "introduction",
            "content_blocks",
            "categories",
            "tags",
            "series",
            "series_order",
            "featured_image",
            "featured_image_thumb",
            "is_featured",
            "reading_time",
            "difficulty_level",
            "allow_comments",
            "excerpt",
            "comment_count",
            "related_posts",
            "related_plant_species",
            "social_image",
        ]

    def get_url(self, obj):
        """Get page URL."""
        try:
            return _absolute_page_url(self.context.get("request"), obj)
        except Exception:
            # Handle cases where get_url_parts() fails (e.g., no site root)
            return None

    def get_author(self, obj):
        """Get author information."""
        if obj.author:
            return {
                "id": obj.author.id,
                "username": obj.author.username,
                "first_name": obj.author.first_name,
                "last_name": obj.author.last_name,
                "display_name": obj.author.get_full_name() or obj.author.username,
                "author_page_url": self._get_author_page_url(obj.author),
            }
        return None

    def get_tags(self, obj):
        """Get tag names."""
        return [tag.name for tag in obj.tags.all()]

    def get_excerpt(self, obj):
        """Get excerpt from introduction."""
        if obj.introduction:
            text = get_text_for_indexing(obj.introduction)
            return Truncator(text).words(50)
        return ""

    def get_comment_count(self, obj):
        """
        Get approved comment count.

        Performance (Issue #182):
        - Uses annotated _comment_count from viewset if available
        - Falls back to query if annotation not present (e.g., in tests)
        """
        if not obj.allow_comments:
            return 0

        # Check if viewset added annotation (list/retrieve actions)
        if hasattr(obj, "_comment_count"):
            return obj._comment_count

        # Fallback: direct query (only in edge cases without optimization)
        return obj.comments.filter(is_approved=True).count()

    def get_related_posts(self, obj):
        """
        Get related posts based on categories and tags.

        Performance (Issue #182):
        - Uses prefetched categories with related posts from viewset if available
        - Falls back to query if prefetch not present (e.g., in tests or list view)
        """
        request = self.context.get("request")

        # Check if viewset prefetched related posts through categories
        if hasattr(obj, "_prefetched_categories_with_posts"):
            # Use prefetched data (retrieve action)
            related_posts_set = set()
            for category in obj._prefetched_categories_with_posts:
                if hasattr(category, "_prefetched_related_posts"):
                    for post in category._prefetched_related_posts:
                        if post.id != obj.id:  # Exclude current post
                            related_posts_set.add(post)
                            if len(related_posts_set) >= 3:
                                break
                if len(related_posts_set) >= 3:
                    break

            related_posts = sorted(
                list(related_posts_set),
                key=lambda p: p.first_published_at,
                reverse=True,
            )[:3]
        else:
            # Fallback: direct query (list action or tests)
            related_posts = (
                BlogPostPage.objects.live()
                .public()
                .exclude(id=obj.id)
                .filter(categories__in=obj.categories.all())
                .distinct()
                .order_by("-first_published_at")[:3]
            )

        return [
            {
                "id": post.id,
                "title": post.title,
                "slug": post.slug,
                "url": self._get_post_url(post, request),
                "published_date": post.first_published_at,
                "excerpt": self._get_post_excerpt(post),
                "featured_image": self._get_post_image(post, request),
            }
            for post in related_posts
        ]

    def get_related_plant_species(self, obj):
        """Get related plant species."""
        return [
            {
                "id": species.id,
                "common_name": species.common_name,
                "scientific_name": species.scientific_name,
            }
            for species in obj.related_plant_species.all()
        ]

    def _get_post_url(self, post, request):
        """Get a related post's URL, tolerating an unroutable page.

        `_absolute_page_url` returns None for an unroutable page (no Site
        covers this part of the page tree) rather than raising — this call
        site used to lack that guard (a bare `post.get_url()` with no
        None-check), so one unroutable related post 500'd the whole detail
        endpoint (todo 306).
        """
        return _absolute_page_url(request, post)

    def _get_author_page_url(self, author):
        """Get author page URL if exists."""
        request = self.context.get("request")
        # Cache per request to avoid N+1 when serializing a list of posts
        url_cache = self.context.setdefault("_author_page_url_cache", {})
        if author.id not in url_cache:
            author_page = BlogAuthorPage.objects.filter(author=author).live().first()
            if author_page and request:
                url_cache[author.id] = _absolute_page_url(request, author_page)
            else:
                url_cache[author.id] = None
        return url_cache[author.id]

    def _get_post_excerpt(self, post):
        """Get excerpt from post."""
        if post.introduction:
            text = get_text_for_indexing(post.introduction)
            return Truncator(text).words(20)
        return ""

    def _get_post_image(self, post, request):
        """Get post featured image, in the same rendition-dict shape every
        other image field in this API uses (todo 306 AC4) — was previously
        a bare URL string here, inconsistent with `featured_image`/
        `social_image` elsewhere on this same payload.
        """
        if not post.featured_image:
            return None
        try:
            rendition = post.featured_image.get_rendition("fill-300x200")
        except (SourceImageIOError, OSError) as e:
            # Media file missing on disk while the Image row survives (e.g.
            # wiped on redeploy) — degrade to null, don't 500 the endpoint.
            logger.error(f"[ERROR] related_posts featured_image rendition failed: {e}")
            return None
        return {
            "url": rendition.url,
            "full_url": (
                request.build_absolute_uri(rendition.url) if request else None
            ),
            "width": rendition.width,
            "height": rendition.height,
            "alt": rendition.alt,
        }


class BlogPostPageListSerializer(serializers.ModelSerializer):
    """Lighter serializer for blog post lists and feeds."""

    author = serializers.SerializerMethodField()
    categories = BlogCategorySerializer(many=True, read_only=True)
    tags = serializers.SerializerMethodField()
    # Grid cards (BlogCard's non-compact variant) render an 800x400 cover —
    # without this, they fell back to featured_image_thumb (300x200) and
    # rendered it upscaled/blurry (PR #540 review finding #1).
    featured_image = RequestAwareImageRenditionField("fill-800x400", read_only=True)
    featured_image_thumb = RequestAwareImageRenditionField(
        "fill-300x200", source="featured_image", read_only=True
    )
    reading_time = serializers.ReadOnlyField()
    excerpt = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = BlogPostPage
        fields = [
            "id",
            "title",
            "slug",
            "url",
            "author",
            "publish_date",
            "categories",
            "tags",
            "featured_image",
            "featured_image_thumb",
            "is_featured",
            "reading_time",
            "difficulty_level",
            "excerpt",
            "comment_count",
        ]

    def get_url(self, obj):
        """Get page URL."""
        try:
            return _absolute_page_url(self.context.get("request"), obj)
        except Exception:
            # Handle cases where get_url_parts() fails (e.g., no site root)
            return None

    def get_author(self, obj):
        """Get basic author information."""
        if obj.author:
            return {
                "id": obj.author.id,
                "username": obj.author.username,
                "display_name": obj.author.get_full_name() or obj.author.username,
            }
        return None

    def get_tags(self, obj):
        """Get tag names."""
        return [tag.name for tag in obj.tags.all()]

    def get_excerpt(self, obj):
        """Get short excerpt."""
        if obj.introduction:
            text = get_text_for_indexing(obj.introduction)
            return Truncator(text).words(30)
        return ""

    def get_comment_count(self, obj):
        """
        Get approved comment count.

        Performance (Issue #182):
        - Uses annotated _comment_count from viewset if available
        - Falls back to query if annotation not present (e.g., in tests)
        """
        if not obj.allow_comments:
            return 0

        # Check if viewset added annotation (list/retrieve actions)
        if hasattr(obj, "_comment_count"):
            return obj._comment_count

        # Fallback: direct query (only in edge cases without optimization)
        return obj.comments.filter(is_approved=True).count()


class BlogIndexPageSerializer(PageSerializer):
    """Serializer for blog index pages."""

    # See `BlogAuthorPageSerializer.meta_fields`'s comment (todo 324).
    meta_fields = ["type", "detail_url"]

    # See `BlogAuthorPageSerializer.url`'s comment (todo 324) — must be
    # declared explicitly or DRF's auto field-building wins over `get_url()`.
    url = serializers.SerializerMethodField()
    featured_posts = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    recent_posts = serializers.SerializerMethodField()

    class Meta:
        model = BlogIndexPage
        fields = ["id", "title", "slug", "url"] + [
            "introduction",
            "posts_per_page",
            "show_featured_posts",
            "show_categories",
            "featured_posts_title",
            "featured_posts",
            "categories",
            "recent_posts",
        ]

    def get_url(self, obj):
        """Request-derived URL (todo 324, same fix as `BlogAuthorPageSerializer.get_url`)."""
        return _absolute_page_url(self.context.get("request"), obj)

    def get_featured_posts(self, obj):
        """Get featured posts if enabled."""
        if not obj.show_featured_posts:
            return []

        featured_posts = (
            BlogPostPage.objects.live()
            .public()
            .filter(is_featured=True)
            .select_related("author", "series")
            .prefetch_related(
                "categories",
                "tags",
                Prefetch(
                    "featured_image",
                    # BlogPostPageListSerializer exposes featured_image
                    # (fill-800x400) alongside featured_image_thumb — both
                    # renditions must be prefetched or it's a per-post query.
                    queryset=Image.objects.prefetch_renditions(
                        "fill-800x400", "fill-300x200"
                    ),
                ),
            )
            .annotate(
                _comment_count=Count("comments", filter=Q(comments__is_approved=True))
            )
            .order_by("-first_published_at")[:3]
        )

        return BlogPostPageListSerializer(
            featured_posts, many=True, context=self.context
        ).data

    def get_categories(self, obj):
        """Get featured categories if enabled."""
        if not obj.show_categories:
            return []

        featured_categories = BlogCategory.objects.filter(is_featured=True).annotate(
            annotated_post_count=Count(
                "blogpostpage", filter=Q(blogpostpage__live=True), distinct=True
            )
        )
        return BlogCategorySerializer(
            featured_categories, many=True, context=self.context
        ).data

    def get_recent_posts(self, obj):
        """Get recent posts for the index."""
        recent_posts = (
            BlogPostPage.objects.live()
            .public()
            .select_related("author", "series")
            .prefetch_related(
                "categories",
                "tags",
                Prefetch(
                    "featured_image",
                    # BlogPostPageListSerializer exposes featured_image
                    # (fill-800x400) alongside featured_image_thumb — both
                    # renditions must be prefetched or it's a per-post query.
                    queryset=Image.objects.prefetch_renditions(
                        "fill-800x400", "fill-300x200"
                    ),
                ),
            )
            .annotate(
                _comment_count=Count("comments", filter=Q(comments__is_approved=True))
            )
            .order_by("-first_published_at")[: obj.posts_per_page]
        )

        return BlogPostPageListSerializer(
            recent_posts, many=True, context=self.context
        ).data


class BlogCategoryPageSerializer(PageSerializer):
    """Serializer for blog category pages."""

    # See `BlogAuthorPageSerializer.meta_fields`'s comment (todo 324).
    meta_fields = ["type", "detail_url"]

    # See `BlogAuthorPageSerializer.url`'s comment (todo 324) — must be
    # declared explicitly or DRF's auto field-building wins over `get_url()`.
    url = serializers.SerializerMethodField()
    category = BlogCategorySerializer(read_only=True)
    posts = serializers.SerializerMethodField()

    class Meta:
        model = BlogCategoryPage
        fields = ["id", "title", "slug", "url"] + [
            "category",
            "posts_per_page",
            "posts",
        ]

    def get_url(self, obj):
        """Request-derived URL (todo 324, same fix as `BlogAuthorPageSerializer.get_url`)."""
        return _absolute_page_url(self.context.get("request"), obj)

    def get_posts(self, obj):
        """Get posts in this category."""
        posts = (
            BlogPostPage.objects.live()
            .public()
            .filter(categories=obj.category)
            .select_related("author", "series")
            .prefetch_related(
                "categories",
                "tags",
                Prefetch(
                    "featured_image",
                    # BlogPostPageListSerializer exposes featured_image
                    # (fill-800x400) alongside featured_image_thumb — both
                    # renditions must be prefetched or it's a per-post query.
                    queryset=Image.objects.prefetch_renditions(
                        "fill-800x400", "fill-300x200"
                    ),
                ),
            )
            .annotate(
                _comment_count=Count("comments", filter=Q(comments__is_approved=True))
            )
            .order_by("-first_published_at")[: obj.posts_per_page]
        )

        return BlogPostPageListSerializer(posts, many=True, context=self.context).data
