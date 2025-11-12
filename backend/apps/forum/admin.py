"""
Django admin configuration for forum models.

Following pattern from apps/blog/admin.py
"""

from django.contrib import admin
from django.contrib import messages
from django.db.models import ProtectedError
from .models import Category, Thread, Post, Attachment, Reaction, UserProfile, FlaggedContent, ModerationAction


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for Categories with cascade protection."""
    list_display = ['name', 'slug', 'parent', 'is_active', 'display_order', 'thread_count_display', 'created_at']
    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['display_order', 'name']

    def thread_count_display(self, obj):
        """Display thread count for category."""
        count = obj.get_thread_count()
        return f"{count} thread{'s' if count != 1 else ''}"
    thread_count_display.short_description = 'Threads'

    def delete_queryset(self, request, queryset):
        """
        Override bulk delete to provide clear error messages for PROTECT constraint.

        Prevents accidental cascade deletion of child categories and threads.
        """
        for category in queryset:
            child_count = category.children.count()
            thread_count = category.get_thread_count()

            if child_count > 0:
                messages.error(
                    request,
                    f"Cannot delete category '{category.name}': Contains {child_count} "
                    f"subcategor{'ies' if child_count != 1 else 'y'}. Delete or move "
                    f"subcategories first to prevent data loss."
                )
                return

            if thread_count > 0:
                messages.warning(
                    request,
                    f"Category '{category.name}' contains {thread_count} thread{'s' if thread_count != 1 else ''}. "
                    f"Deleting will CASCADE delete all threads and their posts!"
                )

        try:
            super().delete_queryset(request, queryset)
            messages.success(request, f"Successfully deleted {queryset.count()} categor{'ies' if queryset.count() != 1 else 'y'}.")
        except ProtectedError as e:
            messages.error(
                request,
                f"Cannot delete categories: They contain child categories. "
                f"Delete or move subcategories first."
            )

    def delete_model(self, request, obj):
        """
        Override single delete to provide clear error messages for PROTECT constraint.

        Prevents accidental cascade deletion of child categories and threads.
        """
        child_count = obj.children.count()
        thread_count = obj.get_thread_count()

        if child_count > 0:
            messages.error(
                request,
                f"Cannot delete category '{obj.name}': Contains {child_count} "
                f"subcategor{'ies' if child_count != 1 else 'y'}. Delete or move "
                f"subcategories first to prevent data loss."
            )
            return

        if thread_count > 0:
            messages.warning(
                request,
                f"Category '{obj.name}' contains {thread_count} thread{'s' if thread_count != 1 else ''}. "
                f"Deleting will CASCADE delete all threads and their posts!"
            )

        try:
            super().delete_model(request, obj)
            messages.success(request, f"Successfully deleted category '{obj.name}'.")
        except ProtectedError:
            messages.error(
                request,
                f"Cannot delete category '{obj.name}': Contains child categories. "
                f"Delete or move subcategories first."
            )


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


@admin.register(FlaggedContent)
class FlaggedContentAdmin(admin.ModelAdmin):
    """Admin interface for Flagged Content (Phase 4.2)."""
    list_display = ['id', 'content_type', 'reporter', 'flag_reason', 'status', 'reviewed_by', 'created_at']
    list_filter = ['status', 'content_type', 'flag_reason', 'created_at', 'reviewed_at']
    search_fields = ['reporter__username', 'reviewed_by__username', 'explanation', 'moderator_notes']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Flag Information', {
            'fields': ('content_type', 'post', 'thread', 'reporter', 'flag_reason', 'explanation')
        }),
        ('Review Information', {
            'fields': ('status', 'reviewed_by', 'reviewed_at', 'moderator_notes')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    """Admin interface for Moderation Actions (Phase 4.2)."""
    list_display = ['id', 'moderator', 'action_type', 'flag', 'affected_user', 'created_at']
    list_filter = ['action_type', 'created_at']
    search_fields = ['moderator__username', 'affected_user__username', 'reason']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Action Information', {
            'fields': ('flag', 'moderator', 'action_type', 'reason', 'affected_user')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )
