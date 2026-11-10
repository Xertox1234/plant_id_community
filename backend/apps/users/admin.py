"""
Admin configuration for User models.
"""

import logging

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .constants import (
    DELETED_ACCOUNT_REASON_ABUSE,
    DELETED_ACCOUNT_REASON_STAFF,
    DELETED_ACCOUNT_REASON_UNDER_13,
    DELETED_ACCOUNT_STATUS_PENDING,
)
from .deletion import DeletionRefused, request_account_deletion
from .models import ActivityLog, DeletedAccount, User, UserMessage, UserPlantCollection

logger = logging.getLogger(__name__)


def _can_delete_accounts(request) -> bool:
    """Gate for the account-deletion admin actions: a superuser, or staff
    holding ``users.delete_user``. View/change on User is not enough."""
    user = request.user
    return bool(user.is_superuser or user.has_perm("users.delete_user"))


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin with additional fields."""

    list_display = (
        "username",
        "email",
        "display_name",
        "gardening_experience",
        "location",
        "follower_count",
        "following_count",
        "plants_identified",
        "is_staff",
        "is_active",
        "date_joined",
    )

    list_filter = (
        "is_staff",
        "is_active",
        "gardening_experience",
        "email_notifications",
        "date_joined",
    )

    search_fields = ("username", "email", "first_name", "last_name", "location")

    readonly_fields = (
        "date_joined",
        "last_login",
        "created_at",
        "updated_at",
        "plants_identified",
        "identifications_helped",
        "forum_posts_count",
        "follower_count",
        "following_count",
        "avatar_display",
    )

    fieldsets = tuple(BaseUserAdmin.fieldsets or ()) + (
        (
            "Profile Information",
            {
                "fields": (
                    "bio",
                    "location",
                    "website",
                    "avatar",
                    "avatar_display",
                    "gardening_experience",
                )
            },
        ),
        (
            "Social Features",
            {"fields": ("following", "follower_count", "following_count")},
        ),
        (
            "Notification Settings",
            {
                "fields": (
                    "email_notifications",
                    "plant_id_notifications",
                    "forum_notifications",
                    "care_reminder_notifications",
                )
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "plants_identified",
                    "identifications_helped",
                    "forum_posts_count",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Additional Info", {"fields": ("email", "first_name", "last_name")}),
    )

    actions = (
        "delete_account_staff",
        "delete_account_abuse",
        "delete_account_under_13",
    )

    def has_delete_permission(self, request, obj=None):
        # Staff delete through the actions below so the erase job runs. This
        # also hides Django's bulk delete_selected (it needs delete permission).
        return False

    def has_delete_account_permission(self, request):
        return _can_delete_accounts(request)

    def _delete_accounts(self, request, queryset, reason):
        scheduled = 0
        already_gone = 0
        refused = []
        label = dict(DeletedAccount.REASON_CHOICES)[reason]
        for user in queryset:
            try:
                request_account_deletion(user, reason)
            except DeletionRefused:
                refused.append(user.username)
            except User.DoesNotExist:
                # The erase job removed the row since the list was rendered.
                already_gone += 1
            else:
                scheduled += 1
                logger.info(
                    "[ACCOUNT DELETE] staff %s requested deletion of account %s (%s)",
                    request.user.pk,
                    user.pk,
                    reason,
                )
        if scheduled:
            self.message_user(
                request,
                f"{scheduled} account(s) scheduled for deletion ({label}).",
                messages.SUCCESS,
            )
        if already_gone:
            self.message_user(
                request,
                f"{already_gone} account(s) already deleted.",
                messages.INFO,
            )
        if refused:
            self.message_user(
                request,
                f"{len(refused)} refused (staff account or blog author; "
                f"handle by hand): {', '.join(refused)}",
                messages.WARNING,
            )

    @admin.action(description="Delete account (staff)", permissions=["delete_account"])
    def delete_account_staff(self, request, queryset):
        self._delete_accounts(request, queryset, DELETED_ACCOUNT_REASON_STAFF)

    @admin.action(
        description="Delete account (abuse — blocks re-sign-up)",
        permissions=["delete_account"],
    )
    def delete_account_abuse(self, request, queryset):
        self._delete_accounts(request, queryset, DELETED_ACCOUNT_REASON_ABUSE)

    @admin.action(
        description="Delete account (under 13 — blocks re-sign-up)",
        permissions=["delete_account"],
    )
    def delete_account_under_13(self, request, queryset):
        self._delete_accounts(request, queryset, DELETED_ACCOUNT_REASON_UNDER_13)

    @admin.display(description="Avatar Preview")
    def avatar_display(self, obj):
        """Display avatar thumbnail in admin."""
        if obj.avatar:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%;" />',
                obj.avatar_thumbnail.url,
            )
        return "No avatar"

    @admin.display(description="Followers")
    def follower_count(self, obj):
        """Display follower count."""
        return obj.follower_count

    @admin.display(description="Following")
    def following_count(self, obj):
        """Display following count."""
        return obj.following_count


@admin.register(UserPlantCollection)
class UserPlantCollectionAdmin(admin.ModelAdmin):
    """Admin for User Plant Collections."""

    list_display = ("name", "user", "plant_count", "is_public", "created_at")

    list_filter = ("is_public", "created_at")

    search_fields = ("name", "user__username", "description")

    readonly_fields = ("plant_count", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("user", "name", "description", "is_public")}),
        ("Statistics", {"fields": ("plant_count",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Plants")
    def plant_count(self, obj):
        """Display plant count for the collection."""
        return obj.plant_count


@admin.register(UserMessage)
class UserMessageAdmin(admin.ModelAdmin):
    """Admin for User Messages."""

    list_display = ("subject", "sender", "recipient", "is_read", "created_at")

    list_filter = ("is_read", "created_at")

    search_fields = ("subject", "message", "sender__username", "recipient__username")

    readonly_fields = ("created_at", "read_at")

    fieldsets = (
        (
            None,
            {"fields": ("sender", "recipient", "subject", "message", "parent_message")},
        ),
        ("Status", {"fields": ("is_read", "read_at")}),
        ("Timestamps", {"fields": ("created_at",)}),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("sender", "recipient")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Admin for Activity Logs."""

    list_display = ("user", "activity_type", "description", "is_public", "created_at")

    list_filter = ("activity_type", "is_public", "created_at")

    search_fields = ("user__username", "description")

    readonly_fields = ("created_at",)

    fieldsets = (
        (None, {"fields": ("user", "activity_type", "description", "is_public")}),
        (
            "Related Object",
            {"fields": ("content_type", "object_id"), "classes": ("collapse",)},
        ),
        ("Timestamps", {"fields": ("created_at",)}),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("user", "content_type")


@admin.register(DeletedAccount)
class DeletedAccountAdmin(admin.ModelAdmin):
    """Read-only view of account deletions, so a stuck one is visible.

    The plain email is deliberately not listed (it is cleared when the erase
    finishes). The one action re-queues the erase for pending rows.
    """

    list_display = (
        "id",
        "reason",
        "status",
        "steps_done",
        "requested_at",
        "deleted_at",
    )
    list_filter = ("status",)
    actions = ("retry_erase",)
    # The view-only detail page would otherwise show these for pending rows.
    exclude = ("email", "firebase_uid")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_delete_account_permission(self, request):
        return _can_delete_accounts(request)

    @admin.action(description="Retry erase", permissions=["delete_account"])
    def retry_erase(self, request, queryset):
        from .tasks import delete_account_task

        ids = list(
            queryset.filter(status=DELETED_ACCOUNT_STATUS_PENDING).values_list(
                "pk", flat=True
            )
        )
        failed = 0
        for record_id in ids:
            try:
                delete_account_task.delay(record_id)
            except Exception as exc:
                # A broker error on one row must not hide the rest; the
                # nightly re-queue of stale pending rows tries it again.
                failed += 1
                logger.error(
                    "[ACCOUNT DELETE] retry of deletion %s could not be queued: %s",
                    record_id,
                    type(exc).__name__,
                )
        requeued = len(ids) - failed
        self.message_user(
            request,
            f"{requeued} re-queued, {failed} failed (pending rows only).",
            messages.WARNING if failed else messages.SUCCESS,
        )
