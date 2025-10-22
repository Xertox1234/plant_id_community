from django.test import TestCase
from rest_framework import serializers
from wagtail.models import Page, Site

from machina.apps.forum.models import Forum
from machina.apps.forum_conversation.models import Topic, Post

from apps.plant_identification.models import PlantSpeciesPage
from apps.forum_integration.serializers import (
    CreateTopicSerializer,
    PostSerializer,
)
from apps.forum_integration.models import RichPost


class PlantMentionSerializationTests(TestCase):
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

        # Create a plant species page to reference
        cls.plant_page = PlantSpeciesPage(
            title="Test Plant Species",
            introduction="<p>Intro</p>",
        )
        cls.root.add_child(instance=cls.plant_page)
        cls.plant_page.save_revision().publish()

        # Minimal forum/topic/post to support read-side enrichment test
        cls.forum = Forum.objects.create(name="Test Forum", type=Forum.FORUM_POST)
        cls.topic = Topic.objects.create(
            forum=cls.forum,
            subject="Test Topic",
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )
        cls.post = Post.objects.create(
            topic=cls.topic,
            approved=True,
            content="plain content",
        )

    def test_normalize_valid_plant_mention(self):
        serializer = CreateTopicSerializer()
        content = [
            {
                "type": "plant_mention",
                "value": {
                    "plant_page": {"id": self.plant_page.id},
                    "display_text": "Optional label",
                },
            }
        ]
        normalized = serializer._normalize_rich_content(content)
        self.assertEqual(normalized[0]["type"], "plant_mention")
        self.assertEqual(normalized[0]["value"]["plant_page"], self.plant_page.id)
        self.assertEqual(normalized[0]["value"]["display_text"], "Optional label")

    def test_normalize_invalid_plant_id_raises(self):
        serializer = CreateTopicSerializer()
        bad_content = [
            {
                "type": "plant_mention",
                "value": {"plant_page": 999999, "display_text": "Bad"},
            }
        ]
        with self.assertRaises(serializers.ValidationError):
            serializer._normalize_rich_content(bad_content)

    def test_read_side_enrichment_includes_page_meta(self):
        # Prepare a RichPost linked to our Post with a plant_mention block
        rich_blocks = [
            {
                "type": "plant_mention",
                "value": {"plant_page": self.plant_page.id, "display_text": ""},
            }
        ]
        RichPost.objects.create(
            post=self.post,
            rich_content=rich_blocks,
            content_format="draftail",
            ai_assisted=False,
        )

        data = PostSerializer(instance=self.post).data
        blocks = data.get("rich_content")
        self.assertIsInstance(blocks, list)
        self.assertIn("value", blocks[0])
        value = blocks[0]["value"]
        # plant_page remains an ID for backward compatibility
        self.assertEqual(value.get("plant_page"), self.plant_page.id)
        # page metadata is attached for client convenience
        page_meta = value.get("page")
        self.assertIsNotNone(page_meta)
        self.assertEqual(page_meta.get("id"), self.plant_page.id)
        self.assertEqual(page_meta.get("title"), self.plant_page.title)
        self.assertEqual(page_meta.get("slug"), self.plant_page.slug)
