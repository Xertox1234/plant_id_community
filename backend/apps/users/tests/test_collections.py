"""DELETE /api/v1/auth/me/collections/<id>/ (todo 599 item 5).

The schema documents ``204`` with no body. The view used to send
``{"message": ...}`` with that 204, so the docs and the wire disagreed, and a
204 has no content (RFC 9110 15.3.5). It now sends none.
"""

from apps.users.models import UserPlantCollection
from django.contrib.auth import get_user_model
from django.test import TestCase
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

User = get_user_model()


class CollectionDeleteTests(TestCase):
    client: APIClient  # DRF test client; TestCase declares Django's Client

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="fern", password="TestPass123!"  # pragma: allowlist secret
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _url(self, collection_id: int) -> str:
        return f"/api/v1/auth/me/collections/{collection_id}/"

    def test_delete_is_a_204_with_no_body(self) -> None:
        collection = UserPlantCollection.objects.create(user=self.user, name="Herbs")

        resp = self.client.delete(self._url(collection.pk))

        self.assertEqual(resp.status_code, 204)
        # The test client strips a 204's content itself, so ``content`` would
        # be empty either way: assert on what the view handed DRF.
        self.assertIsNone(resp.data)
        self.assertFalse(UserPlantCollection.objects.filter(pk=collection.pk).exists())

    def test_another_users_collection_is_a_404(self) -> None:
        other = User.objects.create_user(
            username="moss", password="TestPass123!"  # pragma: allowlist secret
        )
        collection = UserPlantCollection.objects.create(user=other, name="Moss")

        resp = self.client.delete(self._url(collection.pk))

        self.assertEqual(resp.status_code, 404)
        self.assertTrue(UserPlantCollection.objects.filter(pk=collection.pk).exists())

    def test_the_schema_documents_the_same_empty_204(self) -> None:
        schema = SchemaGenerator().get_schema(request=None, public=True)
        delete = schema["paths"]["/auth/me/collections/{collection_id}/"]["delete"]

        self.assertNotIn("content", delete["responses"]["204"])
