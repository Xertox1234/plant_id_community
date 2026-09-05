"""
Django REST API views for blog functionality.

Provides API endpoints for blog posts, categories, comments, and other blog-related data.
Following the existing pattern from plant identification and forum APIs.
"""

import logging

from django.contrib.auth import get_user_model
from django.db.models import Count, F, Prefetch, Q
from django.utils.decorators import method_decorator
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .comments import (
    comment_ratelimit,
    decide_approval,
    models_q_visible_to,
    resolve_parent,
)
from .constants import COMMENT_AUTO_FLAG_THRESHOLD, COMMENT_FLAG_DEDUP_SECONDS
from .models import (
    BlogAuthorPage,
    BlogCategory,
    BlogComment,
    BlogNewsletter,
    BlogPostPage,
    BlogSeries,
)
from .serializers import (
    BlogAuthorSerializer,
    BlogCategorySerializer,
    BlogCommentSerializer,
    BlogNewsletterSerializer,
    BlogPostListSerializer,
    BlogPostPageSerializer,
    BlogSeriesSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class BlogPagination(PageNumberPagination):
    """Custom pagination for blog endpoints."""

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100


class BlogPostPageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for blog posts with search, filtering, and categories.
    """

    serializer_class = BlogPostPageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = BlogPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["categories", "author", "is_featured", "difficulty_level"]
    search_fields = ["title", "introduction", "content_blocks"]
    ordering_fields = ["first_published_at", "title", "reading_time"]
    ordering = ["-first_published_at"]

    def get_queryset(self):
        """Get published blog posts with related data."""
        # Nested categories/series carry a `_post_count` annotation so their
        # serializers read it instead of issuing a COUNT per nested object.
        # `_comment_count` is annotated on the post itself for the same reason.
        queryset = (
            BlogPostPage.objects.live()
            .public()
            .select_related("author")
            .prefetch_related(
                Prefetch(
                    "categories",
                    queryset=BlogCategory.objects.annotate(
                        _post_count=Count(
                            "blogpostpage",
                            filter=Q(blogpostpage__live=True),
                            distinct=True,
                        )
                    ),
                ),
                "tags",
                Prefetch(
                    "series",
                    queryset=BlogSeries.objects.annotate(
                        _post_count=Count(
                            "blogpostpage",
                            filter=Q(blogpostpage__live=True),
                            distinct=True,
                        )
                    ),
                ),
                "related_plant_species",
            )
            .annotate(
                _comment_count=Count(
                    "comments", filter=Q(comments__is_approved=True), distinct=True
                )
            )
        )

        # Filter by category slug if provided
        category_slug = self.request.query_params.get("category")
        if category_slug:
            queryset = queryset.filter(categories__slug=category_slug)

        # Filter by tag if provided
        tag = self.request.query_params.get("tag")
        if tag:
            queryset = queryset.filter(tags__name__icontains=tag)

        # Filter by author username if provided
        author_username = self.request.query_params.get("author")
        if author_username:
            queryset = queryset.filter(author__username=author_username)

        # Filter by series slug if provided
        series_slug = self.request.query_params.get("series")
        if series_slug:
            queryset = queryset.filter(series__slug=series_slug)

        return queryset.distinct()

    def get_serializer_class(self):
        """Use lighter serializer for list view."""
        if self.action == "list":
            return BlogPostListSerializer
        return BlogPostPageSerializer

    @action(detail=False, methods=["get"])
    def featured(self, request):
        """Get featured blog posts."""
        featured_posts = self.get_queryset().filter(is_featured=True)[:6]
        serializer = BlogPostListSerializer(
            featured_posts, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def recent(self, request):
        """Get recent blog posts."""
        recent_posts = self.get_queryset()[:6]
        serializer = BlogPostListSerializer(
            recent_posts, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def related(self, request, pk=None):
        """Get posts related to the current post."""
        post = self.get_object()

        # Find posts with similar categories or tags
        related_posts = (
            self.get_queryset()
            .exclude(id=post.id)
            .filter(
                Q(categories__in=post.categories.all()) | Q(tags__in=post.tags.all())
            )
            .distinct()[:3]
        )

        serializer = BlogPostListSerializer(
            related_posts, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def comments(self, request, pk=None):
        """Top-level comments for a blog post with their replies: approved
        ones, plus the caller's OWN pending ones so an author sees their
        "awaiting moderation" comment after a reload (todo 352)."""
        post = self.get_object()

        if not post.allow_comments:
            return Response(
                {"detail": "Comments are disabled for this post."},
                status=status.HTTP_403_FORBIDDEN,
            )

        visible = models_q_visible_to(request.user)
        comments = (
            BlogComment.objects.filter(visible, post=post, parent=None)
            .select_related("author")
            .prefetch_related(
                Prefetch(
                    "replies",
                    queryset=BlogComment.objects.filter(visible)
                    .select_related("author")
                    .order_by("created_at"),
                    to_attr="visible_replies",
                )
            )
            .order_by("created_at")
        )

        serializer = BlogCommentSerializer(
            comments, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        request={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "parent": {"type": "integer"},
            },
        },
        responses={
            201: BlogCommentSerializer,
            400: dict,
            401: dict,
            403: dict,
            404: dict,
            429: dict,
        },
        description=(
            "Add a comment or a one-level reply. Rate-limited per user (429); "
            "spam screening and the author's forum trust level decide "
            "is_approved (false = awaiting moderation, visible to the author "
            "only); 403 when the post has comments disabled."
        ),
    )
    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    @method_decorator(comment_ratelimit("comment_create"))
    def add_comment(self, request, pk=None):
        """Add a comment (or a one-level reply) to a blog post.

        Protected since todo 352: per-user rate limit (429), the forum spam
        backend screens the text, and the author's forum trust level decides
        `is_approved` — anything held shows as pending to its author only and
        waits in the admin moderation queue. `parent` must be an approved
        top-level comment on THIS post.
        """
        post = self.get_object()

        if not post.allow_comments:
            return Response(
                {"detail": "Comments are disabled for this post."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BlogCommentSerializer(
            data={"content": request.data.get("content", "")},
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        parent = resolve_parent(request.data.get("parent"), post, request.user)
        is_approved, _reason = decide_approval(
            request.user, serializer.validated_data["content"]
        )
        comment = serializer.save(
            author=request.user, post=post, parent=parent, is_approved=is_approved
        )
        return Response(
            BlogCommentSerializer(comment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class BlogCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for blog categories.
    """

    queryset = BlogCategory.objects.annotate(
        _post_count=Count(
            "blogpostpage", filter=Q(blogpostpage__live=True), distinct=True
        )
    )
    serializer_class = BlogCategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = "slug"

    @action(detail=False, methods=["get"])
    def featured(self, request):
        """Get featured categories."""
        featured_categories = self.queryset.filter(is_featured=True)
        serializer = self.get_serializer(featured_categories, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def posts(self, request, slug=None):
        """Get posts in a specific category."""
        category = self.get_object()

        posts = (
            BlogPostPage.objects.live()
            .public()
            .filter(categories=category)
            .select_related("author")
            .order_by("-first_published_at")
        )

        # Apply pagination
        paginator = BlogPagination()
        page = paginator.paginate_queryset(posts, request)

        if page is not None:
            serializer = BlogPostListSerializer(
                page, many=True, context={"request": request}
            )
            return paginator.get_paginated_response(serializer.data)

        serializer = BlogPostListSerializer(
            posts, many=True, context={"request": request}
        )
        return Response(serializer.data)


class BlogSeriesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for blog series.
    """

    queryset = BlogSeries.objects.annotate(
        _post_count=Count(
            "blogpostpage", filter=Q(blogpostpage__live=True), distinct=True
        )
    )
    serializer_class = BlogSeriesSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = "slug"

    @action(detail=True, methods=["get"])
    def posts(self, request, slug=None):
        """Get posts in a specific series."""
        series = self.get_object()

        posts = (
            BlogPostPage.objects.live()
            .public()
            .filter(series=series)
            .select_related("author")
            .order_by("series_order", "first_published_at")
        )

        serializer = BlogPostListSerializer(
            posts, many=True, context={"request": request}
        )
        return Response(serializer.data)


class BlogAuthorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for blog authors.
    """

    serializer_class = BlogAuthorSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = "author__username"

    def get_queryset(self):
        """Get authors who have published posts."""
        return (
            BlogAuthorPage.objects.filter(author__blogpostpage__live=True)
            .select_related("author")
            .prefetch_related("expertise_areas")
            .annotate(
                _post_count=Count(
                    "author__blogpostpage",
                    filter=Q(author__blogpostpage__live=True),
                    distinct=True,
                )
            )
            .distinct()
        )

    @action(detail=True, methods=["get"])
    def posts(self, request, author__username=None):
        """Get posts by a specific author."""
        author_page = self.get_object()

        posts = (
            BlogPostPage.objects.live()
            .public()
            .filter(author=author_page.author)
            .select_related("author")
            .prefetch_related("categories")
            .order_by("-first_published_at")
        )

        # Apply pagination
        paginator = BlogPagination()
        page = paginator.paginate_queryset(posts, request)

        if page is not None:
            serializer = BlogPostListSerializer(
                page, many=True, context={"request": request}
            )
            return paginator.get_paginated_response(serializer.data)

        serializer = BlogPostListSerializer(
            posts, many=True, context={"request": request}
        )
        return Response(serializer.data)


class BlogCommentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read comments + flag one. READ-ONLY since todo 352: creation goes through
    `BlogPostPageViewSet.add_comment` only — the generic POST/PUT/DELETE this
    ModelViewSet used to expose bypassed `allow_comments`, spam screening,
    trust gating and rate limiting, and let a caller create a comment on any
    post. Editing/deleting is an admin-queue concern for now.
    """

    serializer_class = BlogCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        """Comments visible to the current user — staff see everything, others
        approved only — with their replies prefetched under the same
        visibility so the serializer's `replies` never costs a query per row
        (review finding, todo 352)."""
        if self.request.user.is_staff:
            base = BlogComment.objects.all()
            reply_visibility = Q()
        else:
            base = BlogComment.objects.filter(is_approved=True)
            reply_visibility = Q(is_approved=True)
        return base.select_related("author", "post").prefetch_related(
            Prefetch(
                "replies",
                queryset=BlogComment.objects.filter(reply_visibility)
                .select_related("author")
                .order_by("created_at"),
                to_attr="visible_replies",
            )
        )

    @extend_schema(
        responses={200: dict, 400: dict, 401: dict, 404: dict, 429: dict},
        description=(
            "Flag a comment for moderation. Rate-limited per user (429); one "
            "user's repeat flags on the same comment count once; you cannot "
            "flag your own comment (400)."
        ),
    )
    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    @method_decorator(comment_ratelimit("comment_flag"))
    def flag(self, request, pk=None):
        """Flag a comment for moderation. Rate-limited per user (429) and
        deduplicated: one user's repeat flags on the same comment count once
        (todo 352)."""
        from django.core.cache import cache

        comment = self.get_object()
        if comment.author_id == request.user.pk:
            return Response(
                {"detail": "You cannot flag your own comment."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dedup_key = f"blog:comment-flag:{comment.pk}:{request.user.pk}"
        if not cache.add(dedup_key, True, COMMENT_FLAG_DEDUP_SECONDS):
            return Response({"detail": "Comment has been flagged for review."})

        BlogComment.objects.filter(pk=comment.pk).update(flag_count=F("flag_count") + 1)
        comment.refresh_from_db(fields=["flag_count"])
        if comment.flag_count >= COMMENT_AUTO_FLAG_THRESHOLD and not comment.is_flagged:
            # Enough distinct members flagged it: pull it from public view into
            # the existing "pending approval" admin queue, where a moderator
            # can approve (restore) or reject it. Without this the flag had no
            # observable outcome (review finding, todo 352).
            BlogComment.objects.filter(pk=comment.pk).update(
                is_flagged=True, is_approved=False, approved_at=None
            )

        return Response({"detail": "Comment has been flagged for review."})


class BlogNewsletterViewSet(viewsets.ModelViewSet):
    """
    ViewSet for newsletter subscriptions.
    """

    queryset = BlogNewsletter.objects.all()
    serializer_class = BlogNewsletterSerializer
    permission_classes = [permissions.AllowAny]  # Allow anonymous subscriptions
    http_method_names = ["get", "post", "delete"]  # No PUT/PATCH

    def get_queryset(self):
        """Staff can see all subscriptions, users see only their own."""
        if self.request.user.is_staff:
            return self.queryset
        elif self.request.user.is_authenticated:
            return self.queryset.filter(email=self.request.user.email)
        else:
            return self.queryset.none()

    def create(self, request):
        """Subscribe to newsletter."""
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Check if already subscribed
            email = serializer.validated_data["email"]
            if BlogNewsletter.objects.filter(email=email).exists():
                return Response(
                    {"detail": "This email is already subscribed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get IP address for tracking
            ip_address = request.META.get("REMOTE_ADDR")
            serializer.save(ip_address=ip_address)

            return Response(
                {"detail": "Successfully subscribed to newsletter."},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def unsubscribe(self, request):
        """Unsubscribe from newsletter."""
        email = request.data.get("email")

        if not email:
            return Response(
                {"detail": "Email address is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            subscription = BlogNewsletter.objects.get(email=email)
            subscription.unsubscribe()
            return Response({"detail": "Successfully unsubscribed."})
        except BlogNewsletter.DoesNotExist:
            return Response(
                {"detail": "Email address not found."}, status=status.HTTP_404_NOT_FOUND
            )


# Additional API views for blog statistics and search


@api_view(["GET"])
def blog_stats(request):
    """Get blog statistics."""
    stats = {
        "total_posts": BlogPostPage.objects.live().public().count(),
        "total_categories": BlogCategory.objects.count(),
        "total_authors": User.objects.filter(blogpostpage__live=True)
        .distinct()
        .count(),
        "total_comments": BlogComment.objects.filter(is_approved=True).count(),
        "featured_posts": BlogPostPage.objects.live()
        .public()
        .filter(is_featured=True)
        .count(),
    }

    # Recent activity
    recent_posts = (
        BlogPostPage.objects.live().public().order_by("-first_published_at")[:5]
    )
    stats["recent_posts"] = BlogPostListSerializer(
        recent_posts, many=True, context={"request": request}
    ).data

    # Popular categories (by post count)
    popular_categories = (
        BlogCategory.objects.annotate(post_count=Count("blogpostpage"))
        .filter(post_count__gt=0)
        .order_by("-post_count")[:5]
    )
    stats["popular_categories"] = BlogCategorySerializer(
        popular_categories, many=True, context={"request": request}
    ).data

    return Response(stats)


@api_view(["GET"])
def blog_search(request):
    """Search blog content."""
    query = request.GET.get("q", "")

    if not query:
        return Response(
            {"detail": "Search query is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    # Search blog posts
    posts = (
        BlogPostPage.objects.live()
        .public()
        .filter(
            Q(title__icontains=query)
            | Q(introduction__icontains=query)
            | Q(content_blocks__icontains=query)
            | Q(tags__name__icontains=query)
        )
        .distinct()
        .select_related("author")
        .prefetch_related("categories")[:20]
    )

    # Search categories
    categories = BlogCategory.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query)
    )[:10]

    results = {
        "posts": BlogPostListSerializer(
            posts, many=True, context={"request": request}
        ).data,
        "categories": BlogCategorySerializer(
            categories, many=True, context={"request": request}
        ).data,
        "query": query,
        "total_results": len(posts) + len(categories),
    }

    return Response(results)
