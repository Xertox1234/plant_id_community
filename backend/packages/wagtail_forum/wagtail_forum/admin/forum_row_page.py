"""What the *Permissions* and *Change type* screens of a forum row share."""

from __future__ import annotations

from typing import Any

from django.urls import reverse
from django.utils.translation import gettext as _
from wagtail.admin.views.generic.base import WagtailAdminTemplateMixin


class ForumRowPageMixin(WagtailAdminTemplateMixin):
    """Home / Categories & forums / the row / this page. The visible heading
    is ``wagtail_forum/admin/forum_row_page.html``."""

    index_url_name: str | None = None
    edit_url_name: str | None = None

    def get_breadcrumbs_items(self) -> list[dict[str, Any]]:
        name = self.get_page_subtitle()
        return [
            *super().get_breadcrumbs_items(),
            {
                "url": reverse(str(self.index_url_name)),
                "label": _("Categories & forums"),
            },
            {
                "url": reverse(str(self.edit_url_name), args=(self.object.pk,)),
                "label": name,
            },
            {"url": "", "label": self.get_page_title(), "sublabel": name},
        ]
