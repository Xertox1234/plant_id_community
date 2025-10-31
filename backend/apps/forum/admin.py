"""
Django admin configuration for forum models.

Following pattern from apps/blog/admin.py
"""

from django.contrib import admin
from .models import Category, Thread, Post, Attachment, Reaction, UserProfile


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for Categories."""
    list_display = ['name', 'slug', 'parent', 'is_active', 'display_order', 'created_at']
    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['display_order', 'name']


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    """Admin interface for Threads."""
    list_display = ['title', 'author', 'category', 'is_pinned', 'is_locked', 'post_count', 'view_count', 'created_at']
    list_filter = ['is_pinned', 'is_locked', 'is_active', 'category', 'created_at']
    search_fields = ['title', 'slug', 'excerpt']
    readonly_fields = ['id', 'slug', 'post_count', 'view_count', 'created_at', 'updated_at']
    ordering = ['-is_pinned', '-last_activity_at']


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """Admin interface for Posts."""
    list_display = ['__str__', 'thread', 'author', 'is_first_post', 'is_active', 'created_at']
    list_filter = ['is_first_post', 'is_active', 'content_format', 'created_at']
    search_fields = ['content_raw', 'thread__title', 'author__username']
    readonly_fields = ['id', 'created_at', 'updated_at', 'edited_at', 'edited_by']
    ordering = ['-created_at']


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    """Admin interface for Attachments."""
    list_display = ['original_filename', 'post', 'file_size', 'mime_type', 'display_order', 'created_at']
    list_filter = ['mime_type', 'created_at']
    search_fields = ['original_filename', 'alt_text']
    readonly_fields = ['id', 'file_size', 'mime_type', 'created_at']
    ordering = ['display_order', '-created_at']


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    """Admin interface for Reactions."""
    list_display = ['user', 'post', 'reaction_type', 'is_active', 'created_at']
    list_filter = ['reaction_type', 'is_active', 'created_at']
    search_fields = ['user__username', 'post__thread__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface for User Profiles."""
    list_display = ['user', 'trust_level', 'post_count', 'thread_count', 'helpful_count', 'last_seen_at']
    list_filter = ['trust_level', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['id', 'post_count', 'thread_count', 'helpful_count', 'created_at', 'updated_at']
    ordering = ['-helpful_count', '-post_count']
