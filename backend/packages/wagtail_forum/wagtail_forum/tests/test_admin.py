import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_topic_snippet_list_is_reachable_in_admin(client):
    admin = User.objects.create_superuser(username="root", password="x", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/topic/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_post_snippet_list_is_reachable_in_admin(client):
    admin = User.objects.create_superuser(username="root", password="x", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/post/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_profile_snippet_list_is_reachable_in_admin(client):
    # ForumProfileViewSet is registered but its __str__ touches user.get_username();
    # guard the profile list against a silent 500 on a field/relation regression.
    admin = User.objects.create_superuser(username="root", password="x", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/forumprofile/")
    assert resp.status_code == 200
