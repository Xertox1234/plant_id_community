"""
Admin configuration for User models.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, UserPlantCollection, UserMessage, ActivityLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin with additional fields."""
    
    list_display = (
        'username', 'email', 'display_name', 'gardening_experience',
        'location', 'follower_count', 'following_count', 'plants_identified',
        'is_staff', 'is_active', 'date_joined'
    )
    
    list_filter = (
        'is_staff', 'is_active', 'gardening_experience',
        'profile_visibility', 'email_notifications', 'date_joined'
    )
    
    search_fields = ('username', 'email', 'first_name', 'last_name', 'location')
    
    readonly_fields = (
        'date_joined', 'last_login', 'created_at', 'updated_at',
        'plants_identified', 'identifications_helped', 'forum_posts_count',
        'follower_count', 'following_count', 'avatar_display'
    )
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profile Information', {
            'fields': (
                'bio', 'location', 'website', 'avatar', 'avatar_display',
                'gardening_experience'
            )
        }),
        ('Social Features', {
            'fields': (
                'following', 'follower_count', 'following_count'
            )
        }),
        ('Privacy Settings', {
            'fields': (
                'profile_visibility', 'show_email', 'show_location'
            )
        }),
        ('Notification Settings', {
            'fields': (
                'email_notifications', 'plant_id_notifications',
                'forum_notifications'
            )
        }),
        ('Statistics', {
            'fields': (
                'plants_identified', 'identifications_helped',
                'forum_posts_count'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('email', 'first_name', 'last_name')
        }),
    )
    
    def avatar_display(self, obj):
        """Display avatar thumbnail in admin."""
        if obj.avatar:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%;" />',
                obj.avatar_thumbnail.url
            )
        return "No avatar"
    avatar_display.short_description = "Avatar Preview"
    
    def follower_count(self, obj):
        """Display follower count."""
        return obj.follower_count
    follower_count.short_description = "Followers"
    
    def following_count(self, obj):
        """Display following count."""
        return obj.following_count
    following_count.short_description = "Following"


@admin.register(UserPlantCollection)
class UserPlantCollectionAdmin(admin.ModelAdmin):
    """Admin for User Plant Collections."""
    
    list_display = (
        'name', 'user', 'plant_count', 'is_public', 'created_at'
    )
    
    list_filter = ('is_public', 'created_at')
    
    search_fields = ('name', 'user__username', 'description')
    
    readonly_fields = ('plant_count', 'created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('user', 'name', 'description', 'is_public')
        }),
        ('Statistics', {
            'fields': ('plant_count',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def plant_count(self, obj):
        """Display plant count for the collection."""
        return obj.plant_count
    plant_count.short_description = "Plants"


@admin.register(UserMessage)
class UserMessageAdmin(admin.ModelAdmin):
    """Admin for User Messages."""
    
    list_display = (
        'subject', 'sender', 'recipient', 'is_read', 'created_at'
    )
    
    list_filter = ('is_read', 'created_at')
    
    search_fields = (
        'subject', 'message', 'sender__username', 'recipient__username'
    )
    
    readonly_fields = ('created_at', 'read_at')
    
    fieldsets = (
        (None, {
            'fields': ('sender', 'recipient', 'subject', 'message', 'parent_message')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('sender', 'recipient')


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Admin for Activity Logs."""
    
    list_display = (
        'user', 'activity_type', 'description', 'is_public', 'created_at'
    )
    
    list_filter = ('activity_type', 'is_public', 'created_at')
    
    search_fields = ('user__username', 'description')
    
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {
            'fields': (
                'user', 'activity_type', 'description', 'is_public'
            )
        }),
        ('Related Object', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user', 'content_type')