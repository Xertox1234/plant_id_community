from django.test import override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from wagtail.models import Page, Site

from machina.apps.forum.models import Forum

from apps.plant_identification.models import PlantSpeciesPage


@override_settings(ENABLE_FORUM=True)
class ForumPlantMentionAPIRoundtripTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Ensure a default root and site exist
        cls.root = Page.get_first_root_node()
        if not Site.objects.filter(is_default_site=True).exists():
            Site.objects.create(
                hostname="localhost",
                root_page=cls.root,
                is_default_site=True,
                site_name="Test Site",
            )

        # Create a plant species page to reference in rich_content
        cls.plant_page = PlantSpeciesPage(
            title="API Test Plant Species",
            introduction="<p>Intro</p>",
        )
        cls.root.add_child(instance=cls.plant_page)
        cls.plant_page.save_revision().publish()

        # Create a forum category
        cls.forum = Forum.objects.create(name="API Test Forum", type=Forum.FORUM_POST)

        # Create a user
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="api_tester",
            email="api_tester@example.com",
            password="password123!",
        )

    def setUp(self):
        self.client: APIClient = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_topic_with_plant_mention_and_fetch_enriched(self):
        # Prepare payload with plant_mention in rich_content
        payload = {
            "subject": "Identify this plant",
            "content": "<p>Looking for an ID</p>",
            "content_format": "draftail",
            "rich_content": [
                {
                    "type": "plant_mention",
                    "value": {
                        "plant_page": {"id": self.plant_page.id},
                        "display_text": "",
                    },
                }
            ],
        }

        # POST create topic
        create_url = f"/api/forum/categories/{self.forum.id}/topics/create/"
        resp = self.client.post(create_url, data=payload, format="json")
        self.assertEqual(resp.status_code, 201, msg=resp.content)
        self.assertIn("topic", resp.data)
        topic_id = resp.data["topic"]["id"]

        # GET topic detail to fetch posts
        detail_url = f"/api/forum/topics/{topic_id}/"
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200, msg=detail.content)

        posts_block = detail.data.get("posts")
        self.assertIsNotNone(posts_block)
        results = posts_block.get("results", [])
        self.assertGreaterEqual(len(results), 1)
        first_post = results[0]

        # Verify rich_content enrichment
        rich_content = first_post.get("rich_content")
        self.assertIsInstance(rich_content, list)
        first_block = rich_content[0]
        self.assertEqual(first_block.get("type") or first_block.get("block"), "plant_mention")
        value = first_block.get("value", {})

        # plant_page remains an ID for backward compatibility
        self.assertEqual(value.get("plant_page"), self.plant_page.id)
        # page metadata is attached
        page_meta = value.get("page")
        self.assertIsNotNone(page_meta)
        self.assertEqual(page_meta.get("id"), self.plant_page.id)
        self.assertEqual(page_meta.get("title"), self.plant_page.title)
        self.assertEqual(page_meta.get("slug"), self.plant_page.slug)

    def test_reply_with_plant_mention_and_fetch_enriched(self):
        # First create a base topic to reply to
        create_payload = {
            "subject": "Base topic",
            "content": "<p>First post</p>",
        }
        create_url = f"/api/forum/categories/{self.forum.id}/topics/create/"
        create_resp = self.client.post(create_url, data=create_payload, format="json")
        self.assertEqual(create_resp.status_code, 201, msg=create_resp.content)
        topic_id = create_resp.data["topic"]["id"]

        # Prepare reply with plant_mention rich_content
        reply_payload = {
            "content": "<p>Reply with plant mention</p>",
            "content_format": "draftail",
            "rich_content": [
                {
                    "type": "plant_mention",
                    "value": {
                        "plant_page": self.plant_page.id,
                        "display_text": "",
                    },
                }
            ],
        }
        reply_url = f"/api/forum/topics/{topic_id}/posts/create/"
        reply_resp = self.client.post(reply_url, data=reply_payload, format="json")
        self.assertEqual(reply_resp.status_code, 201, msg=reply_resp.content)

        # Fetch topic detail and verify last post contains enriched rich_content
        detail_url = f"/api/forum/topics/{topic_id}/"
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200, msg=detail.content)

        results = detail.data.get("posts", {}).get("results", [])
        self.assertGreaterEqual(len(results), 2)
        last_post = results[-1]
        rich_content = last_post.get("rich_content")
        self.assertIsInstance(rich_content, list)
        first_block = rich_content[0]
        self.assertEqual(first_block.get("type") or first_block.get("block"), "plant_mention")
        value = first_block.get("value", {})
        self.assertEqual(value.get("plant_page"), self.plant_page.id)
        page_meta = value.get("page")
        self.assertIsNotNone(page_meta)
        self.assertEqual(page_meta.get("id"), self.plant_page.id)

    def test_create_topic_with_invalid_plant_page_returns_400(self):
        invalid_id = 99999999
        payload = {
            "subject": "Invalid plant mention",
            "content": "<p>content</p>",
            "content_format": "draftail",
            "rich_content": [
                {
                    "type": "plant_mention",
                    "value": {
                        "plant_page": invalid_id,
                        "display_text": "",
                    },
                }
            ],
        }

        create_url = f"/api/forum/categories/{self.forum.id}/topics/create/"
        resp = self.client.post(create_url, data=payload, format="json")
        self.assertEqual(resp.status_code, 400)
        # Expect validation error referencing rich_content / invalid id
        self.assertIn("rich_content", str(resp.data).lower())
