"""
Wagtail hooks for forum integration.

This module provides admin interface customizations, menu items,
and other Wagtail-specific integrations for the forum system.
"""

from django.urls import path, reverse
from django.utils.html import format_html
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count

# ModelAdmin is deprecated in newer Wagtail versions
# from wagtail.contrib.modeladmin.options import ModelAdmin, modeladmin_register
from wagtail.admin import widgets as wagtailadmin_widgets
from wagtail import hooks
from wagtail.admin.menu import AdminOnlyMenuItem, MenuItem
from wagtail.admin.search import SearchArea
from wagtail.admin.site_summary import SummaryItem

from machina.core.db.models import get_model
from .models import ForumPageMapping, ForumIndexPage, ForumCategoryPage, ForumAnnouncementPage
from . import views

Forum = get_model('forum', 'Forum')
Topic = get_model('forum_conversation', 'Topic')
Post = get_model('forum_conversation', 'Post')


@hooks.register('register_admin_urls')
def register_admin_urls():
    """
    Register custom admin URLs for forum management.
    """
    # Simplified admin URLs - more complex views would be added later
    return []


@hooks.register('register_admin_menu_item')
def register_forum_menu():
    """
    Add forum management menu items to Wagtail admin.
    """
    return MenuItem(
        'Forum Management',
        '/forum/',
        icon_name='group',
        order=300
    )


# ModelAdmin registration is commented out due to deprecation
# This would be replaced with Wagtail's newer admin interface patterns
# in a production implementation


@hooks.register('register_page_listing_buttons')
def forum_page_listing_buttons(page, page_perms=None, user=None, is_parent=False, next_url=None, **kwargs):
    """
    Add custom buttons to forum page listings in Wagtail admin.
    """
    if isinstance(page, (ForumIndexPage, ForumCategoryPage)):
        yield wagtailadmin_widgets.ListingButton(
            'View Forum Stats',
            '/forum/',
            icon_name='view',
            priority=10
        )
        
    if isinstance(page, ForumCategoryPage) and page.machina_forum_id:
        try:
            forum = Forum.objects.get(id=page.machina_forum_id)
            forum_url = f'/forum/category/{forum.id}/'
            yield wagtailadmin_widgets.ListingButton(
                'View Live Forum',
                forum_url,
                icon_name='link-external',
                priority=20
            )
        except Forum.DoesNotExist:
            pass


@hooks.register('register_page_listing_more_buttons')
def forum_page_listing_more_buttons(page, page_perms=None, user=None, is_parent=False, next_url=None, **kwargs):
    """
    Add more buttons to forum page listings.
    """
    if isinstance(page, ForumCategoryPage):
        yield wagtailadmin_widgets.Button(
            'Moderate',
            '/forum/moderation/',
            icon_name='warning',
            priority=30
        )


@hooks.register('construct_homepage_panels')
def add_forum_stats_panel(request, panels):
    """
    Add forum statistics to the Wagtail admin homepage.
    """
    try:
        total_forums = Forum.objects.filter(type=Forum.FORUM_POST).count()
        total_topics = Topic.objects.filter(approved=True).count()
        total_posts = Post.objects.filter(approved=True).count()
        pending_posts = Post.objects.filter(approved=False).count()
        
        panel_content = format_html(
            """
            <div class="panel summary nice-padding">
                <h3><a href="{stats_url}">Forum Statistics</a></h3>
                <ul class="stats">
                    <li><strong>{forums}</strong> Forum Categories</li>
                    <li><strong>{topics}</strong> Total Topics</li>
                    <li><strong>{posts}</strong> Total Posts</li>
                    {pending_html}
                </ul>
                <div class="panel-actions">
                    <a href="{moderation_url}" class="button">Moderation Queue</a>
                    <a href="{stats_url}" class="button">View Detailed Stats</a>
                </div>
            </div>
            """,
            stats_url='/forum/',
            moderation_url='/forum/moderation/',
            forums=total_forums,
            topics=total_topics,
            posts=total_posts,
            pending_html=format_html(
                '<li class="warning"><strong>{}</strong> Posts Pending Approval</li>',
                pending_posts
            ) if pending_posts > 0 else ''
        )
        
        from wagtail.admin.panels import Panel
        
        class ForumStatsPanel(Panel):
            def __init__(self, html_content):
                self.html_content = html_content
                self.order = 250
                
            def render(self):
                return self.html_content
                
            @property
            def media(self):
                from django import forms
                return forms.Media()
        
        panels.append(ForumStatsPanel(panel_content))
        
    except Exception:
        # Graceful degradation if forum models aren't ready
        pass


@hooks.register('construct_homepage_summary_items')
def add_forum_summary_items(request, items):
    """
    Add forum summary items to Wagtail homepage.
    """
    try:
        items.append(SummaryItem(
            'Forums',
            Forum.objects.filter(type=Forum.FORUM_POST).count(),
            'View Forum Stats',
            '/forum/',
            icon_name='group',
            order=300
        ))
        
        items.append(SummaryItem(
            'Topics',
            Topic.objects.filter(approved=True).count(),
            'View Topics',
            '/forum/',
            icon_name='doc-full',
            order=301
        ))
        
        pending_count = Post.objects.filter(approved=False).count()
        if pending_count > 0:
            items.append(SummaryItem(
                'Pending Posts',
                pending_count,
                'Moderate',
                '/forum/moderation/',
                icon_name='warning',
                order=302
            ))
            
    except Exception:
        pass


@hooks.register('register_rich_text_features')
def register_forum_rich_text_features(features):
    """
    Add forum-specific rich text features.
    """
    # Add AI assistance feature for rich text editing
    features.default_features.append('ai')


@hooks.register('before_serve_page')
def check_forum_page_permissions(page, request, serve_args, serve_kwargs):
    """
    Check permissions before serving forum pages.
    """
    if isinstance(page, (ForumIndexPage, ForumCategoryPage, ForumAnnouncementPage)):
        # Add any custom permission checks here
        # This hook allows us to intercept page serving and add forum-specific logic
        pass


@hooks.register('construct_main_menu')
def hide_unused_menu_items(request, menu_items):
    """
    Customize the main admin menu for forum administrators.
    """
    # Remove or modify menu items based on user permissions
    if not request.user.is_superuser:
        # Regular staff users don't need access to some advanced features
        menu_items[:] = [item for item in menu_items if item.name not in ['settings', 'help']]


@hooks.register('register_settings_menu_item')
def register_forum_settings_menu_item():
    """
    Add forum settings to the Wagtail admin settings menu.
    """
    return MenuItem(
        'Forum Settings',
        '/forum/',
        icon_name='cog',
        order=500
    )


@hooks.register('insert_global_admin_css')
def global_admin_css():
    """
    Add custom CSS for forum admin interface.
    """
    return format_html(
        '<link rel="stylesheet" href="/static/forum_integration/css/admin.css">'
    )


@hooks.register('insert_global_admin_js')
def global_admin_js():
    """
    Add custom JavaScript for forum admin interface.
    """
    return format_html(
        '<script src="/static/forum_integration/js/admin.js"></script>'
    )


@hooks.register('construct_page_chooser_queryset')
def limit_forum_page_choices(pages, request):
    """
    Customize page chooser querysets for forum-related fields.
    """
    # This could be used to limit which pages appear in page choosers
    # when creating forum-related content
    return pages


@hooks.register('register_admin_search_area')
def register_forum_search():
    """
    Add forum content to Wagtail admin search.
    """
    return SearchArea(
        'Forum Content',
        '/forum/search/',
        name='forum',
        icon_name='group',
        order=400
    )


# Custom admin views would be registered here
# Currently simplified to avoid non-existent view references


# Permission setup for forum integration
@hooks.register('register_permissions')
def register_forum_permissions():
    """
    Register custom permissions for forum functionality.
    """
    return Permission.objects.filter(
        content_type=ContentType.objects.get_for_model(ForumPageMapping),
        codename__in=['add_forumpagemapping', 'change_forumpagemapping', 'delete_forumpagemapping']
    )