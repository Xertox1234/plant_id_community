"""Self-service forum image management: personal reuse list + delete.

Both views delegate authorization to Wagtail's own
`CollectionOwnershipPermissionPolicy` (via apps.forum_host.bootstrap's
"Forum Members" / "Forum Moderators" GroupCollectionPermission grants) rather
than a hand-rolled `uploaded_by_user == request.user` check — see
api/image_management.py's module docstring for why. post_migrate runs during
test-DB setup (same as test_bootstrap.py), so both groups and their
GroupCollectionPermission rows already exist; these tests only need to
control which group each test user belongs to.
"""

import io

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image as PILImage
from rest_framework.test import APIClient
from wagtail.images import get_image_model
from wagtail_forum.collections import get_forum_image_collection

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")

LIST_URL = "/forum/images/mine/"


def _jpeg(width=10, height=10):
    buf = io.BytesIO()
    PILImage.new("RGB", (width, height), color="blue").save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


def _upload(name="ok.jpg", content=None, content_type="image/jpeg"):
    return SimpleUploadedFile(
        name, content if content is not None else _jpeg(), content_type=content_type
    )


def _member(username):
    """A user in "Forum Members" — the group apps.users.signup.
    join_forum_members_group adds every new signup to."""
    user = User.objects.create_user(username=username)
    user.groups.add(Group.objects.get(name="Forum Members"))
    return user


def _moderator(username):
    user = User.objects.create_user(username=username)
    user.groups.add(Group.objects.get(name="Forum Moderators"))
    return user


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _create_image(owner, collection=None):
    return get_image_model().objects.create(
        title="mine.jpg",
        file=_upload(),
        collection=collection or get_forum_image_collection(),
        uploaded_by_user=owner,
    )


@pytest.mark.django_db
class TestMyForumImagesView:
    def test_requires_authentication(self):
        resp = APIClient().get(LIST_URL)
        assert resp.status_code == 401

    def test_authenticated_but_not_a_forum_member_is_forbidden(self):
        # Not in Forum Members: authenticated is not the same as permitted —
        # this is the whole point of checking the real Wagtail policy instead
        # of stopping at IsAuthenticated.
        outsider = User.objects.create_user(username="outsider")
        resp = _client_for(outsider).get(LIST_URL)
        assert resp.status_code == 403

    def test_returns_only_the_caller_own_uploads(self):
        me = _member("me")
        someone_else = _member("someone-else")
        mine = _create_image(me)
        _create_image(someone_else)  # must not appear in my list

        resp = _client_for(me).get(LIST_URL)
        assert resp.status_code == 200
        ids = {row["id"] for row in resp.data["results"]}
        assert ids == {mine.id}

    def test_ignores_images_outside_the_forum_collection(self):
        from wagtail.models import Collection

        me = _member("me")
        other_collection = Collection.get_first_root_node().add_child(
            name="Somewhere Else"
        )
        _create_image(me, collection=other_collection)

        resp = _client_for(me).get(LIST_URL)
        assert resp.status_code == 200
        assert resp.data["results"] == []


@pytest.mark.django_db
class TestForumImageDetailView:
    def _url(self, image_id):
        return f"/forum/images/{image_id}/"

    def test_requires_authentication(self):
        image = _create_image(_member("owner"))
        resp = APIClient().delete(self._url(image.id))
        assert resp.status_code == 401

    def test_owner_can_delete_their_own_image(self):
        owner = _member("owner")
        image = _create_image(owner)

        resp = _client_for(owner).delete(self._url(image.id))

        assert resp.status_code == 204
        assert not get_image_model().objects.filter(pk=image.id).exists()

    def test_non_owner_member_cannot_delete_someone_elses_image(self):
        owner = _member("owner")
        other_member = _member("other-member")
        image = _create_image(owner)

        resp = _client_for(other_member).delete(self._url(image.id))

        assert resp.status_code == 403
        assert get_image_model().objects.filter(pk=image.id).exists()

    def test_moderator_can_delete_any_forum_image(self):
        """change_image on the forum collection (granted to Forum Moderators
        by apps.forum_host.bootstrap) covers deleting images the moderator
        never uploaded — CollectionOwnershipPermissionPolicy treats delete as
        equivalent to change, not ownership."""
        owner = _member("owner")
        moderator = _moderator("mod")
        image = _create_image(owner)

        resp = _client_for(moderator).delete(self._url(image.id))

        assert resp.status_code == 204
        assert not get_image_model().objects.filter(pk=image.id).exists()

    def test_deleting_a_nonexistent_image_is_404(self):
        member = _member("me")
        resp = _client_for(member).delete(self._url(999999))
        assert resp.status_code == 404

    def test_deleted_image_leaves_a_post_that_referenced_it_rendering_gracefully(self):
        """The other half of the "share to the forum" trade-off discussed
        with the product owner: deleting an image must not corrupt a post
        that already referenced it — serialize_forum_body already resolves a
        missing image id to None (no rewrite, no new revision needed)."""
        from wagtail.models import Page
        from wagtail_forum.api.serializers import (
            build_forum_image_map,
            serialize_forum_body,
        )
        from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic
        from wagtail_forum.workflow import ensure_default_workflow

        ensure_default_workflow()
        owner = _member("owner")
        image = _create_image(owner)

        root = Page.objects.get(id=1)
        index = root.add_child(instance=ForumIndex(title="Forum", slug="forum-imgdel"))
        board = index.add_child(
            instance=ForumBoard(title="General", slug="general-imgdel")
        )
        topic = Topic.objects.create(
            board=board, title="T", slug="t-imgdel", author=owner, live=True
        )
        post = Post.objects.create(
            topic=topic,
            author=owner,
            is_opening_post=True,
            live=True,
            body=[{"type": "image", "value": image.id}],
        )

        _client_for(owner).delete(self._url(image.id))

        post.refresh_from_db()
        blocks = serialize_forum_body(
            post.body, image_map=build_forum_image_map([post])
        )
        assert blocks == [{"type": "image", "value": None, "id": blocks[0]["id"]}]

    def test_deleted_image_degrades_for_the_imageblock_dict_shape_too(self):
        """The shape production actually writes (todo 357).

        The legacy test above stores a bare PK, which is the PRE-0037 shape
        and takes a different branch in ``image_block_pk``. A guarantee proven
        only for the legacy shape would not cover a single post written since
        the ImageBlock migration.
        """
        from wagtail.models import Page
        from wagtail_forum.api.serializers import (
            build_forum_image_map,
            serialize_forum_body,
        )
        from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic
        from wagtail_forum.workflow import ensure_default_workflow

        ensure_default_workflow()
        owner = _member("owner2")
        image = _create_image(owner)

        root = Page.objects.get(id=1)
        index = root.add_child(
            instance=ForumIndex(title="Forum", slug="forum-imgdel-dict")
        )
        board = index.add_child(
            instance=ForumBoard(title="General", slug="general-imgdel-dict")
        )
        topic = Topic.objects.create(
            board=board, title="T", slug="t-imgdel-dict", author=owner, live=True
        )
        post = Post.objects.create(
            topic=topic,
            author=owner,
            is_opening_post=True,
            live=True,
            body=[
                {
                    "type": "image",
                    "value": {
                        "image": image.id,
                        "alt_text": "a plant",
                        "decorative": False,
                    },
                }
            ],
        )

        _client_for(owner).delete(self._url(image.id))

        post.refresh_from_db()
        blocks = serialize_forum_body(
            post.body, image_map=build_forum_image_map([post])
        )
        assert blocks == [{"type": "image", "value": None, "id": blocks[0]["id"]}]
