"""Self-service management of a forum member's own uploaded images.

Wagtail's own ``CollectionOwnershipPermissionPolicy`` (the policy
``wagtail.images`` uses — see ``wagtail.permission_policies.collections``)
already encodes "add implies edit/delete of what you personally uploaded"
and treats "choose" as its own, separately-granted permission.
``apps.forum_host.bootstrap._ensure_forum_image_permissions`` grants both
``add_image`` and ``choose_image`` on the forum's own collection to every
member (the "Forum Members" group) and ``change_image`` to moderators — see
that function's docstring for why.

These two views are the API surface for that policy: list the images it says
the caller may reuse (further scoped to their OWN uploads — Wagtail's stock
"choose" is collection-wide; a personal library, not a shared browse of
everyone's photos, is this forum's product decision, not a Wagtail
limitation), and delete one it says they may remove.

Both delegate the actual authorization check to ``permission_policy`` rather
than re-deriving ``uploaded_by_user == request.user`` by hand, so a
moderator's ``change_image`` grant composes for free through the exact same
mechanism instead of needing a second, parallel check.
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework import status as http_status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from wagtail.images import get_image_model
from wagtail.images import permissions as image_permissions

from ..collections import get_forum_image_collection
from .pagination import ForumImageCursorPagination
from .serializers import serialize_image_for_api
from .versioning import UnversionedForumAPIMixin
from .views import PrivateForumReadCacheMixin


class MyForumImagesView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, generics.ListAPIView
):
    """The caller's own previously-uploaded forum images, newest first.

    Powers "reuse a photo you've already posted" in the composer instead of
    forcing a fresh upload every time. Deliberately scoped to the caller's
    OWN uploads (``uploaded_by_user=request.user``) even though Wagtail's
    ``choose`` permission is granted collection-wide.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = ForumImageCursorPagination
    filter_backends = []  # host filter-backend opt-out — see api/views.py BoardListView

    def get_queryset(self):
        # Schema generation instantiates the view with no authenticated
        # request; degrade to an empty queryset instead of raising, as
        # TopicBookmarkListView does.
        if getattr(self, "swagger_fake_view", False):
            return get_image_model().objects.none()
        # Checked explicitly (not just IsAuthenticated) so a user removed
        # from Forum Members gets a 403, not a silently-empty list that
        # reads as "you have no images". Accessed via the module, not a
        # bound name, so a test overriding WAGTAILIMAGES_IMAGE_MODEL (which
        # resets this at runtime — see wagtail.images.permissions) is
        # honored rather than working from a stale import-time reference.
        # Scoped to the FORUM collection. `user_has_permission(user, "choose")`
        # passes no collection, so it answers "may this user choose images
        # anywhere?" — a blog editor with choose_image on another collection
        # would clear a gate whose whole job is "is this a forum member?".
        allowed = (
            image_permissions.permission_policy.collections_user_has_permission_for(
                self.request.user, "choose"
            )
        )
        if not allowed.filter(pk=get_forum_image_collection().pk).exists():
            raise PermissionDenied("You do not have permission to browse forum images.")
        return (
            get_image_model()
            .objects.filter(
                collection=get_forum_image_collection(),
                uploaded_by_user=self.request.user,
            )
            .prefetch_renditions("max-1200x1200")
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        images = page if page is not None else queryset
        # alt/decorative omitted: serialize_image_for_api falls back to
        # Image.description (the alt captured at upload time) when neither
        # is given — there is no per-usage alt here, this is the image
        # itself, not a specific post's use of it.
        data = [serialize_image_for_api(image, request) for image in images]
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)


class ForumImageDetailView(UnversionedForumAPIMixin, APIView):
    """Delete one of the caller's own forum images — or, for a moderator,
    any forum image, both routed through the same Wagtail permission check.

    Deleting the row does not corrupt anything that referenced it: an
    ``image`` StreamField block resolves a now-missing id to ``None`` at
    read time (``serialize_forum_body``), and
    ``ForumIdentificationAttachment.image`` is ``on_delete=SET_NULL`` — both
    already render a no-photo fallback. No cascade, no post rewrite, no new
    revision.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, image_id):
        image = get_object_or_404(
            get_image_model(),
            pk=image_id,
            collection=get_forum_image_collection(),
        )
        if not image_permissions.permission_policy.user_has_permission_for_instance(
            request.user, "delete", image
        ):
            raise PermissionDenied("You do not have permission to delete this image.")
        image.delete()
        return Response(status=http_status.HTTP_204_NO_CONTENT)
