"""
URL configuration for blog API endpoints.

Following the existing pattern from plant identification and forum APIs.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import newsletter_views, views

# Create router for ViewSets
router = DefaultRouter()
router.register(r"posts", views.BlogPostPageViewSet, basename="blog-posts")
router.register(r"categories", views.BlogCategoryViewSet, basename="blog-categories")
router.register(r"series", views.BlogSeriesViewSet, basename="blog-series")
router.register(r"authors", views.BlogAuthorViewSet, basename="blog-authors")
router.register(r"comments", views.BlogCommentViewSet, basename="blog-comments")

app_name = "blog"

urlpatterns = [
    # Admin interface
    path("admin/", include("apps.blog.admin_urls")),
    # API endpoints via router
    path("", include(router.urls)),
    # Additional API endpoints
    path("stats/", views.blog_stats, name="blog-stats"),
    path("search/", views.blog_search, name="blog-search"),
    # Newsletter double opt-in (todo 409)
    path(
        "newsletter/",
        newsletter_views.newsletter_subscribe,
        name="newsletter-subscribe",
    ),
    path(
        "newsletter/confirm/",
        newsletter_views.newsletter_confirm,
        name="newsletter-confirm",
    ),
    path(
        "newsletter/unsubscribe/",
        newsletter_views.newsletter_unsubscribe,
        name="newsletter-unsubscribe",
    ),
    path(
        "newsletter/unsubscribe/one-click/",
        newsletter_views.newsletter_unsubscribe_one_click,
        name="newsletter-unsubscribe-one-click",
    ),
]
