"""Blog admin hooks resolve their URLs via the blog_admin namespace.

Audit 2026-07-17 M2: every /blog-admin/... URL in wagtail_hooks.py was
hardcoded; now they all go through reverse("blog_admin:<name>"). These tests
render the real admin pages, so a NoReverseMatch (renamed/removed route) or a
regression to a dead hardcoded path fails loudly instead of 404ing silently.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_admin_home_renders_blog_menu_and_summary_with_resolved_urls(client):
    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/")

    assert resp.status_code == 200
    # Menu item + "Blog Posts" summary item both carry the dashboard URL.
    assert reverse("blog_admin:dashboard").encode() in resp.content


@pytest.mark.django_db
def test_admin_search_page_renders_blog_search_area_with_resolved_url(client):
    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)

    resp = client.get(reverse("wagtailadmin_pages:search"), {"q": "anything"})

    assert resp.status_code == 200
    assert reverse("blog_admin:search").encode() in resp.content
