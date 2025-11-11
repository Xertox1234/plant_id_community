"""
Wagtail hooks for blog application.

This module provides AI-enhanced rich text features, admin interface customizations,
and plant-specific content suggestions for the blog system.
"""

from django.urls import path, reverse
from django.utils.html import format_html
from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from wagtail import hooks
from wagtail.admin.menu import AdminOnlyMenuItem, MenuItem
from wagtail.admin.search import SearchArea
from wagtail.admin.site_summary import SummaryItem
from wagtail.admin import widgets as wagtailadmin_widgets
from wagtail.snippets.models import register_snippet

from .models import BlogPostPage, BlogCategory, BlogComment, BlogSeries

User = get_user_model()


@hooks.register('register_rich_text_features')
def register_blog_rich_text_features(features):
    """
    Add AI assistance and plant-specific rich text features for blog content.
    """
    # Add AI assistance feature for blog content creation
    features.default_features.append('ai')


@hooks.register('register_admin_menu_item')
def register_blog_menu():
    """
    Add blog management menu items to Wagtail admin.
    """
    return MenuItem(
        'Blog Management',
        '/blog-admin/',
        icon_name='doc-full-inverse',
        order=200
    )


@hooks.register('construct_homepage_panels')
def add_blog_stats_panel(request, panels):
    """
    Add blog statistics to the Wagtail admin homepage (Phase 6.2: Analytics).
    """
    try:
        from django.db.models import Sum

        total_posts = BlogPostPage.objects.live().count()
        published_posts = BlogPostPage.objects.live().public().count()
        draft_posts = BlogPostPage.objects.filter(live=False).count()
        featured_posts = BlogPostPage.objects.live().public().filter(is_featured=True).count()
        pending_comments = BlogComment.objects.filter(is_approved=False).count()

        # Phase 6.2: Analytics data
        total_views = BlogPostPage.objects.aggregate(Sum('view_count'))['view_count__sum'] or 0
        most_popular = BlogPostPage.objects.live().public().order_by('-view_count').first()

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
            blog_url='/cms/pages/',
            total=total_posts,
            published=published_posts,
            featured=featured_posts,
            drafts_html=format_html(
                '<li class="warning"><strong>{}</strong> Draft Posts</li>',
                draft_posts
            ) if draft_posts > 0 else '',
            analytics_html=format_html(
                '<li style="color: #007d7e;"><strong>{:,}</strong> Total Views</li>',
                total_views
            ) if total_views > 0 else '',
            popular_html=format_html(
                '<li style="color: #007d7e;">Most Popular: <strong>{}</strong> ({} views)</li>',
                most_popular.title[:30] + '...' if len(most_popular.title) > 30 else most_popular.title,
                most_popular.view_count
            ) if most_popular and most_popular.view_count > 0 else '',
            comments_html=format_html(
                '<li class="error"><strong>{}</strong> Comments Pending Approval</li>',
                pending_comments
            ) if pending_comments > 0 else '',
            moderate_html=format_html(
                '<a href="/blog-admin/comments/" class="button warning">Moderate Comments</a>'
            ) if pending_comments > 0 else ''
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


@hooks.register('construct_homepage_summary_items')
def add_blog_summary_items(request, items):
    """
    Add blog summary items to Wagtail homepage.
    """
    try:
        items.append(SummaryItem(
            'Blog Posts',
            BlogPostPage.objects.live().public().count(),
            'View All Posts',
            '/blog-admin/',
            icon_name='doc-full',
            order=200
        ))
        
        featured_count = BlogPostPage.objects.live().public().filter(is_featured=True).count()
        if featured_count > 0:
            items.append(SummaryItem(
                'Featured Posts',
                featured_count,
                'Manage Featured',
                '/blog-admin/featured/',
                icon_name='pick',
                order=201
            ))
        
        pending_comments = BlogComment.objects.filter(is_approved=False).count()
        if pending_comments > 0:
            items.append(SummaryItem(
                'Pending Comments',
                pending_comments,
                'Moderate',
                '/blog-admin/comments/',
                icon_name='warning',
                order=202
            ))
            
    except Exception:
        pass


@hooks.register('register_page_listing_buttons')
def blog_page_listing_buttons(page, page_perms=None, user=None, is_parent=False, next_url=None, **kwargs):
    """
    Add custom buttons to blog page listings in Wagtail admin (Phase 6.2: Analytics).
    """
    if isinstance(page, BlogPostPage):
        # View live blog post button
        if page.live:
            yield wagtailadmin_widgets.ListingButton(
                'View Live',
                page.get_url(),
                icon_name='view',
                priority=10
            )

        # Phase 6.2: View count button
        if page.view_count > 0:
            yield wagtailadmin_widgets.ListingButton(
                f'{page.view_count:,} views',
                f'#',  # Could link to detailed analytics
                icon_name='view',
                priority=15,
                attrs={'title': f'{page.view_count:,} total views'}
            )

        # Comments button
        comment_count = page.comments.filter(is_approved=True).count()
        if comment_count > 0:
            yield wagtailadmin_widgets.ListingButton(
                f'Comments ({comment_count})',
                f'/blog-admin/posts/{page.id}/comments/',
                icon_name='comment',
                priority=20
            )

        # AI content suggestions button (if content is short)
        if page.reading_time and page.reading_time < 3:
            yield wagtailadmin_widgets.ListingButton(
                'AI Suggestions',
                f'/blog-admin/posts/{page.id}/ai-suggestions/',
                icon_name='help',
                priority=30
            )


@hooks.register('register_page_listing_more_buttons')
def blog_page_listing_more_buttons(page, page_perms=None, user=None, is_parent=False, next_url=None, **kwargs):
    """
    Add more buttons to blog page listings.
    """
    if isinstance(page, BlogPostPage):
        # Featured toggle
        if page.is_featured:
            yield wagtailadmin_widgets.Button(
                'Unfeature',
                f'/blog-admin/posts/{page.id}/unfeature/',
                icon_name='cross',
                priority=10
            )
        else:
            yield wagtailadmin_widgets.Button(
                'Feature',
                f'/blog-admin/posts/{page.id}/feature/',
                icon_name='pick',
                priority=10
            )
        
        # Plant species tagging
        yield wagtailadmin_widgets.Button(
            'Tag Plants',
            f'/blog-admin/posts/{page.id}/tag-plants/',
            icon_name='tag',
            priority=20
        )


@hooks.register('before_serve_page')
def check_blog_page_permissions(page, request, serve_args, serve_kwargs):
    """
    Check permissions and add context before serving blog pages.
    """
    if isinstance(page, BlogPostPage):
        # Add reading analytics
        # This could track page views, reading time, etc.
        pass


@hooks.register('construct_main_menu')
def customize_blog_menu(request, menu_items):
    """
    Customize the main admin menu for blog editors.
    """
    # Blog editors get quick access to their posts
    if request.user.is_authenticated and hasattr(request.user, 'blog_posts'):
        user_posts_count = request.user.blog_posts.filter(live=True).count()
        if user_posts_count > 0:
            # Could add custom menu items for blog authors
            pass


@hooks.register('register_settings_menu_item')
def register_blog_settings_menu_item():
    """
    Add blog settings to the Wagtail admin settings menu.
    """
    return MenuItem(
        'Blog Settings',
        '/blog-admin/settings/',
        icon_name='cog',
        order=400
    )


@hooks.register('insert_global_admin_css')
def global_blog_admin_css():
    """
    Add custom CSS for blog admin interface.
    """
    return format_html(
        '<link rel="stylesheet" href="/static/blog/css/admin.css">'
        '<link rel="stylesheet" href="/static/blog/css/plant_block_autopop.css">'
    )


@hooks.register('insert_global_admin_js')
def global_blog_admin_js():
    """
    Add custom JavaScript for blog admin interface.
    """
    return format_html(
        '<script src="/static/blog/js/admin.js"></script>'
        '<script src="/static/blog/js/plant_block_autopop.js"></script>'
    )


@hooks.register('register_admin_search_area')
def register_blog_search():
    """
    Add blog content to Wagtail admin search.
    """
    return SearchArea(
        'Blog Content',
        '/blog-admin/search/',
        name='blog',
        icon_name='doc-full',
        order=300
    )


# AI-enhanced content suggestions hook
@hooks.register('register_rich_text_features')
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
@hooks.register('register_admin_urls')
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
@hooks.register('register_permissions')
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
            codename__in=['add_blogpostpage', 'change_blogpostpage', 'delete_blogpostpage']
        )
    except:
        return []


# Content moderation hooks
@hooks.register('after_create_page')
def after_create_blog_post(request, page):
    """
    Actions to perform after creating a blog post.
    """
    if isinstance(page, BlogPostPage):
        # Could trigger AI content analysis
        # Could send notifications to subscribers
        # Could update author statistics
        pass


@hooks.register('after_edit_page')
def after_edit_blog_post(request, page):
    """
    Actions to perform after editing a blog post.
    """
    if isinstance(page, BlogPostPage):
        # Recalculate reading time
        if not page.reading_time:
            page.reading_time = page.calculate_reading_time()
            page.save(update_fields=['reading_time'])