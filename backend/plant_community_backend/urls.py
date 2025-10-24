"""
URL configuration for plant_community_backend project.

Plant Community Web App - A comprehensive platform for plant enthusiasts
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls
from wagtail.api.v2.router import WagtailAPIRouter
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.images.api.v2.views import ImagesAPIViewSet
from wagtail.documents.api.v2.views import DocumentsAPIViewSet

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

# Import blog API viewsets
from apps.blog.api.viewsets import (
    BlogPostPageViewSet,
    BlogIndexPageViewSet,
    BlogCategoryPageViewSet,
    BlogAuthorPageViewSet,
    BlogFeedViewSet
)
from apps.blog.api.endpoints import (
    BlogCategoryAPIViewSet,
    BlogSeriesAPIViewSet
)
from apps.plant_identification.api.endpoints import (
    PlantSpeciesAPIViewSet,
    PlantCategoryAPIViewSet,
    PlantCareGuideAPIViewSet,
    PlantSpeciesPageViewSet,
    PlantCategoryIndexPageViewSet
)

# Create the Wagtail API router
api_router = WagtailAPIRouter('wagtailapi')

# Core Wagtail endpoints
api_router.register_endpoint('pages', PagesAPIViewSet)
api_router.register_endpoint('images', ImagesAPIViewSet)
api_router.register_endpoint('documents', DocumentsAPIViewSet)

# Blog-specific endpoints
api_router.register_endpoint('blog-posts', BlogPostPageViewSet)
api_router.register_endpoint('blog-index', BlogIndexPageViewSet)
api_router.register_endpoint('blog-categories', BlogCategoryPageViewSet)
api_router.register_endpoint('blog-authors', BlogAuthorPageViewSet)
api_router.register_endpoint('blog-feeds', BlogFeedViewSet)

# Blog snippets endpoints  
api_router.register_endpoint('categories', BlogCategoryAPIViewSet)
api_router.register_endpoint('series', BlogSeriesAPIViewSet)

# Plant identification endpoints
api_router.register_endpoint('plant-species', PlantSpeciesAPIViewSet)
api_router.register_endpoint('plant-categories', PlantCategoryAPIViewSet)
api_router.register_endpoint('care-guides', PlantCareGuideAPIViewSet)
api_router.register_endpoint('plants', PlantSpeciesPageViewSet)
api_router.register_endpoint('plant-index', PlantCategoryIndexPageViewSet)

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),
    
    # Wagtail CMS Admin
    path('cms/', include(wagtailadmin_urls)),
    
    # Wagtail Documents
    path('documents/', include(wagtaildocs_urls)),
    
    # API Authentication
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # OAuth Authentication
    path('api/auth/oauth/<str:provider>/', include('apps.users.oauth_urls')),
    
    # OAuth Authentication (allauth)
    path('accounts/', include('allauth.urls')),
    
    # Wagtail CMS API (v2)
    path('api/v2/', api_router.urls),

    # Custom blog endpoints (DRF @action decorators not supported by Wagtail router)
    path('api/v2/blog-posts/popular/', BlogPostPageViewSet.as_view({'get': 'popular'}), name='blog-posts-popular'),

    # Django REST Framework API - Versioned (v1)
    path('api/v1/', include(([
        path('auth/', include('apps.users.urls')),
        path('plant-identification/', include('apps.plant_identification.urls')),
        path('blog/', include('apps.blog.urls')),
        path('blog-api/', include('apps.blog.api_urls')),
        path('search/', include('apps.search.urls')),
        path('calendar/', include('apps.garden_calendar.urls')),
        *([path('forum/', include('apps.forum_integration.api_urls'))] if getattr(settings, 'ENABLE_FORUM', False) else []),
    ], 'v1'))),

    # Legacy Unversioned API (Deprecated - redirects to v1)
    # TODO: Remove after 2025-07-01 (6 months deprecation period)
    path('api/', include([
        path('auth/', include('apps.users.urls')),
        path('plant-identification/', include('apps.plant_identification.urls')),
        path('blog/', include('apps.blog.urls')),
        path('blog-api/', include('apps.blog.api_urls')),
        path('search/', include('apps.search.urls')),
        path('calendar/', include('apps.garden_calendar.urls')),
        *([path('forum/', include('apps.forum_integration.api_urls'))] if getattr(settings, 'ENABLE_FORUM', False) else []),
    ])),
    
    # Blog Administration Interface
    path('blog-admin/', include('apps.blog.admin_urls')),
    
    # Forum Integration (optional)
    # Only include when ENABLE_FORUM=True to avoid migration issues during smoke tests
    *([path('forum/', include('apps.forum_integration.urls'))] if getattr(settings, 'ENABLE_FORUM', False) else []),
    *([path('machina/', include('machina.urls'))] if getattr(settings, 'ENABLE_FORUM', False) else []),
    
    # Default redirect to Wagtail admin for development
    path('', RedirectView.as_view(url='/cms/', permanent=False)),
    
    # Wagtail Frontend URLs (should be last)
    re_path(r'', include(wagtail_urls)),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Debug toolbar
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns