from django.urls import include, path

urlpatterns = [path("forum/", include("wagtail_forum.api.urls"))]
