"""
Wagtail hooks for blog application.

This module provides AI-enhanced rich text features, admin interface customizations,
and plant-specific content suggestions for the blog system.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.html import format_html
from wagtail import hooks
from wagtail.admin import widgets as wagtailadmin_widgets
from wagtail.admin.menu import MenuItem
from wagtail.admin.search import SearchArea
from wagtail.admin.site_summary import SummaryItem

from .models import BlogComment, BlogPostPage

User = get_user_model()

# Admin URLs are resolved via the blog_admin namespace (apps/blog/admin_urls.py),
# never hardcoded to the /blog-admin/ mount (audit 2026-07-17 M2). All reverse()
# calls stay inside hook functions — hooks fire per-request, after URLconf load.


@hooks.register("register_rich_text_features")
def register_blog_rich_text_features(features):
    """
    Add AI assistance and plant-specific rich text features for blog content.
    """
    # Add AI assistance feature for blog content creation
    features.default_features.append("ai")


@hooks.register("register_admin_menu_item")
def register_blog_menu():
    """
    Add blog management menu items to Wagtail admin.
    """
    return MenuItem(
        "Blog Management",
        reverse("blog_admin:dashboard"),
        icon_name="doc-full-inverse",
        order=200,
    )


@hooks.register("construct_homepage_panels")
def add_blog_stats_panel(request, panels):
    """
    Add blog statistics to the Wagtail admin homepage (Phase 6.2: Analytics).
    """
    try:
        from django.db.models import Sum

        total_posts = BlogPostPage.objects.live().count()
        published_posts = BlogPostPage.objects.live().public().count()
        draft_posts = BlogPostPage.objects.filter(live=False).count()
        featured_posts = (
            BlogPostPage.objects.live().public().filter(is_featured=True).count()
        )
        pending_comments = BlogComment.objects.filter(is_approved=False).count()

        # Phase 6.2: Analytics data
        total_views = (
            BlogPostPage.objects.aggregate(Sum("view_count"))["view_count__sum"] or 0
        )
        most_popular = (
            BlogPostPage.objects.live().public().order_by("-view_count").first()
        )

        panel_content = format_html(
            """
            <div class="panel summary nice-padding">
                <h3><a href="{blog_url}">Blog Statistics</a></h3>
                <ul class="stats">
                    <li><strong>{total}</strong> Total Posts</li>
                    <li><strong>{published}</strong> Published Posts</li>
                    <li><strong>{featured}</strong> Featured Posts</li>
                    {drafts_html}
                    {analytics_html}
                    {popular_html}
                    {comments_html}
                </ul>
                <div class="panel-actions">
                    <a href="/cms/pages/" class="button">New Blog Post</a>
                    <a href="/cms/pages/" class="button">Manage Blog</a>
                    {moderate_html}
                </div>
            </div>
            """,
            blog_url="/cms/pages/",
            total=total_posts,
            published=published_posts,
            featured=featured_posts,
            drafts_html=(
                format_html(
                    '<li class="warning"><strong>{}</strong> Draft Posts</li>',
                    draft_posts,
                )
                if draft_posts > 0
                else ""
            ),
            analytics_html=(
                format_html(
                    '<li style="color: #007d7e;"><strong>{:,}</strong> Total Views</li>',
                    total_views,
                )
                if total_views > 0
                else ""
            ),
            popular_html=(
                format_html(
                    '<li style="color: #007d7e;">Most Popular: <strong>{}</strong> ({} views)</li>',
                    (
                        most_popular.title[:30] + "..."
                        if len(most_popular.title) > 30
                        else most_popular.title
                    ),
                    most_popular.view_count,
                )
                if most_popular and most_popular.view_count > 0
                else ""
            ),
            comments_html=(
                format_html(
                    '<li class="error"><strong>{}</strong> Comments Pending Approval</li>',
                    pending_comments,
                )
                if pending_comments > 0
                else ""
            ),
            moderate_html=(
                format_html(
                    '<a href="{}" class="button warning">Moderate Comments</a>',
                    reverse("blog_admin:moderate_comments"),
                )
                if pending_comments > 0
                else ""
            ),
        )

        from wagtail.admin.panels import Panel

        class BlogStatsPanel(Panel):
            def __init__(self, html_content):
                self.html_content = html_content
                self.order = 200

            def render(self):
                return self.html_content

            @property
            def media(self):
                from django import forms

                return forms.Media()

        panels.append(BlogStatsPanel(panel_content))

    except Exception:
        # Graceful degradation if blog models aren't ready
        pass


class BlogSummaryItem(SummaryItem):
    """SummaryItem is a Component: __init__ only takes request, and rendering
    is template-driven (get_context_data + template_name), NOT the
    positional-args constructor this replaces — that older API doesn't exist
    on this installed Wagtail version (confirmed via
    wagtail.images.wagtail_hooks.ImagesSummaryItem, the in-tree precedent
    this mirrors; see also
    wagtail_forum.wagtail_hooks.ForumModerationSummaryItem, todo 264)."""

    template_name = "wagtailadmin/home/site_summary_blog.html"

    def __init__(self, request, *, label, count, url_label, url, icon_name, order):
        super().__init__(request)
        self.label = label
        self.count = count
        self.url_label = url_label
        self.url = url
        self.icon_name = icon_name
        self.order = order

    def get_context_data(self, parent_context):
        return {
            "label": self.label,
            "count": self.count,
            "url_label": self.url_label,
            "url": self.url,
            "icon_name": self.icon_name,
        }


@hooks.register("construct_homepage_summary_items")
def add_blog_summary_items(request, items):
    """
    Add blog summary items to Wagtail homepage.
    """
    try:
        post_count = BlogPostPage.objects.live().public().count()
        featured_count = (
            BlogPostPage.objects.live().public().filter(is_featured=True).count()
        )
        pending_comments = BlogComment.objects.filter(is_approved=False).count()
    except Exception:
        return  # graceful degradation if blog models aren't ready

    items.append(
        BlogSummaryItem(
            request,
            label="Blog Posts",
            count=post_count,
            url_label="View All Posts",
            url=reverse("blog_admin:dashboard"),
            icon_name="doc-full",
            order=200,
        )
    )

    if featured_count > 0:
        items.append(
            BlogSummaryItem(
                request,
                label="Featured Posts",
                count=featured_count,
                url_label="Manage Featured",
                url=reverse("blog_admin:featured_posts"),
                icon_name="pick",
                order=201,
            )
        )

    if pending_comments > 0:
        items.append(
            BlogSummaryItem(
                request,
                label="Pending Comments",
                count=pending_comments,
                url_label="Moderate",
                url=reverse("blog_admin:moderate_comments"),
                icon_name="warning",
                order=202,
            )
        )


@hooks.register("register_page_listing_buttons")
def blog_page_listing_buttons(
    page, page_perms=None, user=None, is_parent=False, next_url=None, **kwargs
):
    """
    Add custom buttons to blog page listings in Wagtail admin (Phase 6.2: Analytics).
    """
    if isinstance(page, BlogPostPage):
        # View live blog post button
        if page.live:
            yield wagtailadmin_widgets.ListingButton(
                "View Live", page.get_url(), icon_name="view", priority=10
            )

        # Phase 6.2: View count button
        if page.view_count > 0:
            yield wagtailadmin_widgets.ListingButton(
                f"{page.view_count:,} views",
                "#",  # Could link to detailed analytics
                icon_name="view",
                priority=15,
                attrs={"title": f"{page.view_count:,} total views"},
            )

        # Comments button
        comment_count = page.comments.filter(is_approved=True).count()
        if comment_count > 0:
            yield wagtailadmin_widgets.ListingButton(
                f"Comments ({comment_count})",
                reverse("blog_admin:post_comments", args=(page.id,)),
                icon_name="comment",
                priority=20,
            )

        # AI content suggestions button (if content is short)
        if page.reading_time and page.reading_time < 3:
            yield wagtailadmin_widgets.ListingButton(
                "AI Suggestions",
                reverse("blog_admin:post_ai_suggestions", args=(page.id,)),
                icon_name="help",
                priority=30,
            )


@hooks.register("register_page_listing_more_buttons")
def blog_page_listing_more_buttons(
    page, page_perms=None, user=None, is_parent=False, next_url=None, **kwargs
):
    """
    Add more buttons to blog page listings.
    """
    if isinstance(page, BlogPostPage):
        # Featured toggle
        if page.is_featured:
            yield wagtailadmin_widgets.Button(
                "Unfeature",
                reverse("blog_admin:unfeature_post", args=(page.id,)),
                icon_name="cross",
                priority=10,
            )
        else:
            yield wagtailadmin_widgets.Button(
                "Feature",
                reverse("blog_admin:feature_post", args=(page.id,)),
                icon_name="pick",
                priority=10,
            )

        # Plant species tagging
        yield wagtailadmin_widgets.Button(
            "Tag Plants",
            reverse("blog_admin:tag_plants", args=(page.id,)),
            icon_name="tag",
            priority=20,
        )


@hooks.register("before_serve_page")
def check_blog_page_permissions(page, request, serve_args, serve_kwargs):
    """
    Check permissions and add context before serving blog pages.
    """
    if isinstance(page, BlogPostPage):
        # Add reading analytics
        # This could track page views, reading time, etc.
        pass


@hooks.register("construct_main_menu")
def customize_blog_menu(request, menu_items):
    """
    Customize the main admin menu for blog editors.
    """
    # Blog editors get quick access to their posts
    if request.user.is_authenticated and hasattr(request.user, "blog_posts"):
        user_posts_count = request.user.blog_posts.filter(live=True).count()
        if user_posts_count > 0:
            # Could add custom menu items for blog authors
            pass


@hooks.register("register_settings_menu_item")
def register_blog_settings_menu_item():
    """
    Add blog settings to the Wagtail admin settings menu.
    """
    return MenuItem(
        "Blog Settings", reverse("blog_admin:settings"), icon_name="cog", order=400
    )


@hooks.register("register_admin_search_area")
def register_blog_search():
    """
    Add blog content to Wagtail admin search.
    """
    return SearchArea(
        "Blog Content",
        reverse("blog_admin:search"),
        name="blog",
        icon_name="doc-full",
        order=300,
    )


# AI-enhanced content suggestions hook
@hooks.register("register_rich_text_features")
def register_plant_content_features(features):
    """
    Add plant-specific AI content suggestions for rich text blocks.
    """
    # This would integrate with Wagtail AI to provide plant-specific prompts
    # Examples:
    # - "Suggest care instructions for [plant name]"
    # - "Generate plant identification tips"
    # - "Create seasonal gardening advice"
    pass


# Custom admin views registration
@hooks.register("register_admin_urls")
def register_blog_admin_urls():
    """
    Register custom admin URLs for blog management.
    """
    # These would be implemented in a separate views module
    return [
        # path('blog-admin/', blog_admin_dashboard, name='blog_admin_dashboard'),
        # path('blog-admin/comments/', moderate_comments, name='moderate_comments'),
        # path('blog-admin/ai-suggestions/', ai_content_suggestions, name='ai_suggestions'),
    ]


# Blog-specific permission hooks
@hooks.register("register_permissions")
def register_blog_permissions():
    """
    Register custom permissions for blog functionality.
    """
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    try:
        blog_ct = ContentType.objects.get_for_model(BlogPostPage)
        return Permission.objects.filter(
            content_type=blog_ct,
            codename__in=[
                "add_blogpostpage",
                "change_blogpostpage",
                "delete_blogpostpage",
            ],
        )
    except Exception:
        return []


# Content moderation hooks
@hooks.register("after_create_page")
def after_create_blog_post(request, page):
    """
    Actions to perform after creating a blog post.
    """
    if isinstance(page, BlogPostPage):
        # Could trigger AI content analysis
        # Could send notifications to subscribers
        # Could update author statistics
        pass


@hooks.register("after_edit_page")
def after_edit_blog_post(request, page):
    """
    Actions to perform after editing a blog post.
    """
    if isinstance(page, BlogPostPage):
        # Recalculate reading time
        if not page.reading_time:
            page.reading_time = page.calculate_reading_time()
            page.save(update_fields=["reading_time"])
