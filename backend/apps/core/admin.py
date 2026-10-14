from django.contrib import admin

from .email_feedback import address_hash
from .models import EmailSuppression


@admin.register(EmailSuppression)
class EmailSuppressionAdmin(admin.ModelAdmin):
    """Lift a provider suppression (todo 625).

    A hard bounce blocks every email to the address, password reset and
    verification included, until staff delete its row here (the procedure is
    in docs/operations/notification-baseline.md). Rows hold only a hash of
    the address, so the search box takes the ADDRESS and looks up its hash;
    rows are never added or edited by hand, only viewed and deleted.
    """

    list_display = ("id", "reason", "created_at", "updated_at")
    list_filter = ("reason",)
    readonly_fields = (
        "address_hash",
        "reason",
        "source_event",
        "created_at",
        "updated_at",
    )
    search_fields = ("address_hash",)
    search_help_text = "Enter the full email address; it is matched by its hash."

    def get_search_results(self, request, queryset, search_term):
        term = (search_term or "").strip()
        if not term:
            return queryset, False
        return queryset.filter(address_hash=address_hash(term)), False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
