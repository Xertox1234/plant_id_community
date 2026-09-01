"""Wagtail admin (``/cms/``) registrations for the forum host app.

``RagAnswerReportViewSet`` (todo 289 / M13, design doc guardrail 5) is the
wrong-answer review queue: a moderator reads what the user asked, what the
answer said and which sources it cited, then marks the report actioned or
dismissed. It sits beside the package's own "Forum → Reports" queue rather
than inside it — the package's ``ForumViewSetGroup`` is composed at class
definition and the package may not know about host models
(``test_reusability``).
"""

from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import RagAnswerReport


class RagAnswerReportViewSet(SnippetViewSet):
    model = RagAnswerReport
    icon = "warning"
    menu_label = "AI answer reports"
    menu_name = "forum_ai_answer_reports"
    add_to_admin_menu = True
    list_display = ["answer_question", "reporter", "status", "created_at"]
    list_filter = ["status"]
    # The inspect view is where the moderator sees the full answer + sources
    # without a shell (the list only fits the question).
    inspect_view_enabled = True
    inspect_view_fields = [
        "answer_question",
        "answer_text",
        "answer_sources",
        "detail",
        "reporter",
        "status",
        "created_at",
        "resolved_at",
        "resolved_by",
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if qs is None:
            qs = self.model.objects.all()
        return qs.select_related("answer__user", "reporter", "resolved_by")


register_snippet(RagAnswerReportViewSet)
