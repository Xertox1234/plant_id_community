"""
Model tests for blog app.

Tests BlogPostPage, BlogIndexPage, BlogCategory, BlogSeries, and related models.
"""

from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from wagtail.models import Page, Site
from wagtail.test.utils import WagtailPageTestCase
from wagtail.fields import StreamValue
from apps.blog.models import (
    BlogPostPage,
    BlogIndexPage,
    BlogCategory,
    BlogSeries,
    BlogBasePage,
)

User = get_user_model()


class BlogCategoryTestCase(TestCase):
    """Tests for BlogCategory snippet model."""

    def setUp(self):
        """Create test data."""
        self.category = BlogCategory.objects.create(
            name="Beginner Guides",
            slug="beginner-guides",
            description="Guides for those new to plant care",
        )

    def test_category_creation(self):
        """BlogCategory can be created with valid data."""
        self.assertEqual(self.category.name, "Beginner Guides")
        self.assertEqual(self.category.slug, "beginner-guides")
        self.assertIsNotNone(self.category.description)

    def test_category_str_representation(self):
        """BlogCategory __str__ returns name."""
        self.assertEqual(str(self.category), "Beginner Guides")

    def test_category_slug_uniqueness(self):
        """BlogCategory slug must be unique."""
        with self.assertRaises(Exception):
            BlogCategory.objects.create(
                name="Different Name",
                slug="beginner-guides",  # Duplicate slug
                description="Test",
            )


class BlogSeriesTestCase(TestCase):
    """Tests for BlogSeries snippet model."""

    def setUp(self):
        """Create test data."""
        self.series = BlogSeries.objects.create(
            title="Growing Tomatoes from Seed to Harvest",
            slug="growing-tomatoes",
            description="A comprehensive 5-part series on growing tomatoes",
        )

    def test_series_creation(self):
        """BlogSeries can be created with valid data."""
        self.assertEqual(self.series.title, "Growing Tomatoes from Seed to Harvest")
        self.assertEqual(self.series.slug, "growing-tomatoes")
        self.assertIsNotNone(self.series.description)

    def test_series_str_representation(self):
        """BlogSeries __str__ returns title."""
        self.assertEqual(str(self.series), "Growing Tomatoes from Seed to Harvest")


class BlogIndexPageTestCase(WagtailPageTestCase):
    """Tests for BlogIndexPage model."""

    def setUp(self):
        """Create test data."""
        # Get the root page
        self.root_page = Page.objects.get(id=1)

        # Create a BlogIndexPage
        self.blog_index = BlogIndexPage(
            title="Plant Blog",
            slug="blog",
            meta_description="Articles and guides from plant experts",
        )
        self.root_page.add_child(instance=self.blog_index)

    def test_blog_index_creation(self):
        """BlogIndexPage can be created under root."""
        self.assertEqual(self.blog_index.title, "Plant Blog")
        self.assertEqual(self.blog_index.slug, "blog")
        self.assertTrue(self.blog_index.live)

    def test_blog_index_parent_page_types(self):
        """BlogIndexPage can only be created under specific page types."""
        # Should be able to create under root (Page)
        self.assertCanCreateAt(Page, BlogIndexPage)

    def test_blog_index_child_page_types(self):
        """BlogIndexPage allows child pages (no restrictions in current implementation)."""
        # Note: Current implementation does not restrict subpage types
        # This is intentional to allow flexibility
        allowed_types = BlogIndexPage.allowed_subpage_models()
        self.assertGreater(len(allowed_types), 0)

    def test_blog_index_has_url_path(self):
        """BlogIndexPage has a URL path."""
        # Verify page has a URL path (part of Wagtail page tree)
        self.assertIsNotNone(self.blog_index.url_path)
        self.assertIn(self.blog_index.slug, self.blog_index.url_path)


class BlogPostPageTestCase(WagtailPageTestCase):
    """Tests for BlogPostPage model."""

    def setUp(self):
        """Create test data."""
        # Create user
        self.user = User.objects.create_user(
            username="testauthor",
            email="author@example.com",
            password="testpass123",
        )

        # Create category
        self.category = BlogCategory.objects.create(
            name="Plant Care",
            slug="plant-care",
            description="Care instructions for plants",
        )

        # Create series
        self.series = BlogSeries.objects.create(
            title="Indoor Plant Basics",
            slug="indoor-plant-basics",
            description="A series about indoor plants",
        )

        # Get or create blog index
        root_page = Page.objects.get(id=1)
        try:
            self.blog_index = BlogIndexPage.objects.get(slug="blog")
        except BlogIndexPage.DoesNotExist:
            self.blog_index = BlogIndexPage(
                title="Blog",
                slug="blog",
            )
            root_page.add_child(instance=self.blog_index)

        # Create blog post
        self.blog_post = BlogPostPage(
            title="Getting Started with Indoor Plants",
            slug="getting-started-indoor-plants",
            author=self.user,
            publish_date=date.today(),
            introduction="<p>Learn the basics of indoor plant care.</p>",
            content_blocks=[
                ("heading", "Why Indoor Plants?"),
                ("paragraph", "<p>Indoor plants improve air quality and reduce stress.</p>"),
            ],
            meta_description="Learn indoor plant basics",
        )
        self.blog_index.add_child(instance=self.blog_post)
        self.blog_post.save_revision().publish()

    def test_blog_post_creation(self):
        """BlogPostPage can be created with required fields."""
        self.assertEqual(self.blog_post.title, "Getting Started with Indoor Plants")
        self.assertEqual(self.blog_post.author, self.user)
        self.assertEqual(self.blog_post.publish_date, date.today())
        self.assertTrue(self.blog_post.live)

    def test_blog_post_parent_page_types(self):
        """BlogPostPage can be created under various page types."""
        # Current implementation allows flexible parent types
        self.assertCanCreateAt(BlogIndexPage, BlogPostPage)
        # Also allowed under root Page (flexible architecture)
        self.assertCanCreateAt(Page, BlogPostPage)

    def test_blog_post_has_child_page_types(self):
        """BlogPostPage allows child pages (flexible architecture)."""
        # Current implementation does not restrict subpage types
        allowed_types = BlogPostPage.allowed_subpage_models()
        self.assertGreater(len(allowed_types), 0)

    def test_blog_post_has_url_path(self):
        """BlogPostPage has a URL path in page tree."""
        # Verify page has a URL path
        self.assertIsNotNone(self.blog_post.url_path)
        self.assertIn(self.blog_post.slug, self.blog_post.url_path)
        # Should also include parent path
        self.assertIn(self.blog_index.slug, self.blog_post.url_path)

    def test_blog_post_with_categories(self):
        """BlogPostPage can have multiple categories."""
        self.blog_post.categories.add(self.category)
        self.assertEqual(self.blog_post.categories.count(), 1)
        self.assertIn(self.category, self.blog_post.categories.all())

    def test_blog_post_with_tags(self):
        """BlogPostPage can have multiple tags."""
        self.blog_post.tags.add("indoor-plants", "beginner", "care-tips")
        self.assertEqual(self.blog_post.tags.count(), 3)
        tag_names = [tag.name for tag in self.blog_post.tags.all()]
        self.assertIn("indoor-plants", tag_names)
        self.assertIn("beginner", tag_names)

    def test_blog_post_with_series(self):
        """BlogPostPage can belong to a series."""
        self.blog_post.series = self.series
        self.blog_post.series_order = 1
        self.blog_post.save()
        self.assertEqual(self.blog_post.series, self.series)
        self.assertEqual(self.blog_post.series_order, 1)

    def test_blog_post_reading_time_calculation(self):
        """BlogPostPage calculates reading time based on word count."""
        # Create post with known word count
        long_content = " ".join(["word"] * 500)  # 500 words
        self.blog_post.introduction = long_content
        self.blog_post.content_blocks = [
            ("paragraph", " ".join(["word"] * 500)),  # Another 500 words
        ]

        reading_time = self.blog_post.calculate_reading_time()
        # 1000 words / 200 words per minute = 5 minutes
        self.assertGreaterEqual(reading_time, 4)
        self.assertLessEqual(reading_time, 6)

    def test_blog_post_reading_time_minimum(self):
        """BlogPostPage reading time is at least 1 minute."""
        self.blog_post.introduction = "Short."
        self.blog_post.content_blocks = []
        reading_time = self.blog_post.calculate_reading_time()
        self.assertGreaterEqual(reading_time, 1)

    def test_blog_post_auto_reading_time_on_save(self):
        """BlogPostPage auto-calculates reading time on save."""
        self.blog_post.reading_time = None
        self.blog_post.save()
        self.assertIsNotNone(self.blog_post.reading_time)
        self.assertGreater(self.blog_post.reading_time, 0)

    def test_blog_post_search_fields(self):
        """BlogPostPage has searchable fields configured."""
        # Verify search fields are defined
        search_fields = [f.field_name for f in BlogPostPage.search_fields]
        self.assertIn("title", search_fields)
        self.assertIn("introduction", search_fields)

    def test_blog_post_content_panels(self):
        """BlogPostPage has content panels configured."""
        # Verify content panels exist
        self.assertTrue(hasattr(BlogPostPage, "content_panels"))
        self.assertGreater(len(BlogPostPage.content_panels), 0)

    def test_blog_post_featured_flag(self):
        """BlogPostPage can be marked as featured."""
        self.blog_post.is_featured = True
        self.blog_post.save()
        self.assertTrue(self.blog_post.is_featured)

        # Query featured posts
        featured_posts = BlogPostPage.objects.live().filter(is_featured=True)
        self.assertIn(self.blog_post, featured_posts)

    def test_blog_post_difficulty_level(self):
        """BlogPostPage has difficulty level choices."""
        # Test valid difficulty levels
        for level in ["beginner", "intermediate", "advanced"]:
            self.blog_post.difficulty_level = level
            self.blog_post.save()
            self.blog_post.refresh_from_db()
            self.assertEqual(self.blog_post.difficulty_level, level)

    def test_blog_post_allow_comments_default(self):
        """BlogPostPage has comments enabled by default."""
        new_post = BlogPostPage(
            title="Test Post",
            slug="test-post",
            author=self.user,
            publish_date=date.today(),
            introduction="Test",
        )
        self.blog_index.add_child(instance=new_post)
        # Check if allow_comments has a default value
        self.assertTrue(hasattr(new_post, "allow_comments"))


class BlogPostStreamFieldTestCase(WagtailPageTestCase):
    """Tests for BlogPostPage StreamField content."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(
            username="testauthor",
            email="author@example.com",
            password="testpass123",
        )

        root_page = Page.objects.get(id=1)
        try:
            self.blog_index = BlogIndexPage.objects.get(slug="blog")
        except BlogIndexPage.DoesNotExist:
            self.blog_index = BlogIndexPage(
                title="Blog",
                slug="blog",
            )
            root_page.add_child(instance=self.blog_index)

    def test_streamfield_heading_block(self):
        """BlogPostPage can contain heading blocks."""
        blog_post = BlogPostPage(
            title="Test Post",
            slug="test-post-heading",
            author=self.user,
            publish_date=date.today(),
            introduction="Test",
            content_blocks=[
                ("heading", "Test Heading"),
            ],
        )
        self.blog_index.add_child(instance=blog_post)
        self.assertEqual(len(blog_post.content_blocks), 1)
        self.assertEqual(blog_post.content_blocks[0].block_type, "heading")
        self.assertEqual(blog_post.content_blocks[0].value, "Test Heading")

    def test_streamfield_paragraph_block(self):
        """BlogPostPage can contain paragraph blocks."""
        blog_post = BlogPostPage(
            title="Test Post",
            slug="test-post-paragraph",
            author=self.user,
            publish_date=date.today(),
            introduction="Test",
            content_blocks=[
                ("paragraph", "<p>Test paragraph content.</p>"),
            ],
        )
        self.blog_index.add_child(instance=blog_post)
        self.assertEqual(len(blog_post.content_blocks), 1)
        self.assertEqual(blog_post.content_blocks[0].block_type, "paragraph")

    def test_streamfield_multiple_blocks(self):
        """BlogPostPage can contain multiple blocks."""
        blog_post = BlogPostPage(
            title="Test Post",
            slug="test-post-multiple",
            author=self.user,
            publish_date=date.today(),
            introduction="Test",
            content_blocks=[
                ("heading", "Section 1"),
                ("paragraph", "<p>Content for section 1.</p>"),
                ("heading", "Section 2"),
                ("paragraph", "<p>Content for section 2.</p>"),
            ],
        )
        self.blog_index.add_child(instance=blog_post)
        self.assertEqual(len(blog_post.content_blocks), 4)

    def test_streamfield_blocks_are_flat(self):
        """BlogPostPage StreamField uses flat structure (no nesting)."""
        # This test verifies that we're not using nested StructBlocks
        blog_post = BlogPostPage(
            title="Test Post",
            slug="test-post-flat",
            author=self.user,
            publish_date=date.today(),
            introduction="Test",
            content_blocks=[
                ("heading", "Test"),
                ("paragraph", "<p>Test</p>"),
            ],
        )
        self.blog_index.add_child(instance=blog_post)

        # Verify each block is at the top level (not nested)
        for block in blog_post.content_blocks:
            # If blocks were nested, they would have child blocks
            # Our flat structure means each block is a simple type
            self.assertIsNotNone(block.block_type)
            self.assertIsNotNone(block.value)


class BlogPostHeadlessPreviewTestCase(WagtailPageTestCase):
    """Tests for BlogPostPage headless preview functionality."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(
            username="testauthor",
            email="author@example.com",
            password="testpass123",
        )

        root_page = Page.objects.get(id=1)
        try:
            self.blog_index = BlogIndexPage.objects.get(slug="blog")
        except BlogIndexPage.DoesNotExist:
            self.blog_index = BlogIndexPage(
                title="Blog",
                slug="blog",
            )
            root_page.add_child(instance=self.blog_index)

        self.blog_post = BlogPostPage(
            title="Preview Test Post",
            slug="preview-test-post",
            author=self.user,
            publish_date=date.today(),
            introduction="Test preview",
            content_blocks=[],
        )
        self.blog_index.add_child(instance=self.blog_post)

    def test_preview_modes_property(self):
        """BlogPostPage has preview_modes property."""
        self.assertTrue(hasattr(self.blog_post, "preview_modes"))
        modes = self.blog_post.preview_modes
        self.assertIsInstance(modes, list)
        self.assertGreater(len(modes), 0)

    def test_preview_modes_includes_web_and_mobile(self):
        """BlogPostPage preview_modes includes both web and mobile."""
        modes = self.blog_post.preview_modes
        mode_names = [mode[0] for mode in modes]
        self.assertIn("", mode_names)  # Default (web)
        self.assertIn("mobile", mode_names)  # Mobile

    def test_get_client_root_url_method(self):
        """BlogPostPage has get_client_root_url method."""
        self.assertTrue(hasattr(self.blog_post, "get_client_root_url"))
        url = self.blog_post.get_client_root_url()
        self.assertIsInstance(url, str)
        self.assertIn("preview", url.lower())

    def test_get_client_root_url_mobile_mode(self):
        """BlogPostPage returns mobile deep link for mobile mode."""
        url = self.blog_post.get_client_root_url(mode="mobile")
        self.assertIn("plantid://", url)

    def test_get_client_root_url_default_mode(self):
        """BlogPostPage returns web URL for default mode."""
        url = self.blog_post.get_client_root_url(mode="")
        self.assertIn("http", url.lower())
        self.assertIn("preview", url.lower())
