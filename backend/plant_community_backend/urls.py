"""
URL configuration for plant_community_backend project.

Plant Community Web App - A comprehensive platform for plant enthusiasts
"""

from apps.blog.api.endpoints import BlogCategoryAPIViewSet, BlogSeriesAPIViewSet

# Import blog API viewsets
from apps.blog.api.viewsets import (
    BlogAuthorPageViewSet,
    BlogCategoryPageViewSet,
    BlogFeedViewSet,
    BlogIndexPageViewSet,
    BlogPostPageViewSet,
)

# Import core views
from apps.core.views import ReactAppView, csp_report_view, csrf_token_view
from apps.plant_identification.api.endpoints import (
    PlantCareGuideAPIViewSet,
    PlantCategoryAPIViewSet,
    PlantCategoryIndexPageViewSet,
    PlantSpeciesAPIViewSet,
    PlantSpeciesPageViewSet,
)
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

# Import drf-spectacular views for API documentation
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenVerifyView
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.api.v2.router import WagtailAPIRouter
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.documents import urls as wagtaildocs_urls
from wagtail.documents.api.v2.views import DocumentsAPIViewSet
from wagtail.images.api.v2.views import ImagesAPIViewSet

# Create the Wagtail API router
api_router = WagtailAPIRouter("wagtailapi")

# Core Wagtail endpoints
api_router.register_endpoint("pages", PagesAPIViewSet)
api_router.register_endpoint("images", ImagesAPIViewSet)
api_router.register_endpoint("documents", DocumentsAPIViewSet)

# Blog-specific endpoints
api_router.register_endpoint("blog-posts", BlogPostPageViewSet)
api_router.register_endpoint("blog-index", BlogIndexPageViewSet)
api_router.register_endpoint("blog-categories", BlogCategoryPageViewSet)
api_router.register_endpoint("blog-authors", BlogAuthorPageViewSet)
api_router.register_endpoint("blog-feeds", BlogFeedViewSet)

# Blog snippets endpoints
api_router.register_endpoint("categories", BlogCategoryAPIViewSet)
api_router.register_endpoint("series", BlogSeriesAPIViewSet)

# Plant identification endpoints
api_router.register_endpoint("plant-species", PlantSpeciesAPIViewSet)
api_router.register_endpoint("plant-categories", PlantCategoryAPIViewSet)
api_router.register_endpoint("care-guides", PlantCareGuideAPIViewSet)
api_router.register_endpoint("plants", PlantSpeciesPageViewSet)
api_router.register_endpoint("plant-index", PlantCategoryIndexPageViewSet)

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),
    # Wagtail CMS Admin
    path("cms/", include(wagtailadmin_urls)),
    # Wagtail Documents
    path("documents/", include(wagtaildocs_urls)),
    # API Authentication
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # CSRF Token endpoint for SPA (Issue #144 fix)
    path("api/csrf/", csrf_token_view, name="csrf-token"),
    # CSP Violation Report endpoint (Issue #014)
    path("api/v1/security/csp-report/", csp_report_view, name="csp-report"),
    # API Documentation (OpenAPI 3.0)
    # SECURITY (todo 248): these three views are staff-gated via
    # SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = [IsAdminUser] (see settings.py).
    # Anonymous requests get 401/403; do not add AllowAny here.
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs-swagger",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="api-schema"),
        name="api-docs-redoc",
    ),
    # OAuth Authentication
    path("api/auth/oauth/<str:provider>/", include("apps.users.oauth_urls")),
    # OAuth Authentication (allauth)
    path("accounts/", include("allauth.urls")),
    # Wagtail CMS API (v2)
    path("api/v2/", api_router.urls),
    # Custom blog endpoints (DRF @action decorators not supported by Wagtail router)
    path(
        "api/v2/blog-posts/popular/",
        BlogPostPageViewSet.as_view({"get": "popular"}),
        name="blog-posts-popular",
    ),
    # Django REST Framework API - Versioned (v1)
    path(
        "api/v1/",
        include(
            (
                [
                    path("auth/", include("apps.users.urls")),
                    path(
                        "plant-identification/",
                        include("apps.plant_identification.urls"),
                    ),
                    path("blog/", include("apps.blog.urls")),
                    path("blog-api/", include("apps.blog.api_urls")),
                    # Host wrapper adds rate limiting around the package views.
                    path("forum/", include("apps.forum_host.api_urls")),
                    path("calendar/", include("apps.garden_calendar.urls")),
                    path("garden/", include("apps.garden.urls")),  # Garden Planner API
                ],
                "v1",
            )
        ),
    ),
    # Legacy Unversioned API (Deprecated - redirects to v1)
    # TODO: Remove after 2025-07-01 (6 months deprecation period)
    path(
        "api/",
        include(
            [
                path("auth/", include("apps.users.urls")),
                path(
                    "plant-identification/", include("apps.plant_identification.urls")
                ),
                path("blog/", include("apps.blog.urls")),
                path("blog-api/", include("apps.blog.api_urls")),
                path("calendar/", include("apps.garden_calendar.urls")),
                path("garden/", include("apps.garden.urls")),  # Garden Planner API
            ]
        ),
    ),
    # Blog Administration Interface
    path("blog-admin/", include("apps.blog.admin_urls")),
    # React SPA routes (Issue #013 - Meta tag pattern for CSRF)
    # These routes serve the React app with CSRF token in meta tag
    # Allows CSRF_COOKIE_HTTPONLY = True for XSS protection
    path("app/", ReactAppView.as_view(), name="react-app-root"),
    path("app/blog/", ReactAppView.as_view(), name="react-app-blog"),
    path("app/forum/", ReactAppView.as_view(), name="react-app-forum"),
    path("app/identify/", ReactAppView.as_view(), name="react-app-identify"),
    path("app/login/", ReactAppView.as_view(), name="react-app-login"),
    path("app/register/", ReactAppView.as_view(), name="react-app-register"),
    # Default redirect to Wagtail admin for development
    path("", RedirectView.as_view(url="/cms/", permanent=False)),
    # Wagtail Frontend URLs (should be last)
    re_path(r"", include(wagtail_urls)),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Debug toolbar
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
