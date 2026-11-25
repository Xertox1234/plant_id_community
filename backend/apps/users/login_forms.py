"""Password sign-in forms for the CMS and the Django admin (todo 701).

Both pages open a Django session with no consent box. An account that has not
accepted the current policy version is refused there and sent to sign in on
the website, where it is asked (``apps/users/consent.py``).
"""

from __future__ import annotations

from typing import Any

from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError
from wagtail.admin.forms.auth import LoginForm

from .constants import POLICY_UPDATED_SIGN_IN_ON_WEBSITE_MESSAGE


def refuse_until_policy_accepted(user: Any) -> None:
    """Raise the form error for an account that must accept first."""
    from .consent import needs_policy_acceptance

    if needs_policy_acceptance(user):
        raise ValidationError(
            POLICY_UPDATED_SIGN_IN_ON_WEBSITE_MESSAGE, code="policy_update_required"
        )


class PolicyCheckedWagtailLoginForm(LoginForm):
    """``WAGTAILADMIN_USER_LOGIN_FORM``: the ``/cms/`` sign-in."""

    def confirm_login_allowed(self, user: Any) -> None:
        super().confirm_login_allowed(user)
        refuse_until_policy_accepted(user)


class PolicyCheckedAdminLoginForm(AdminAuthenticationForm):
    """``admin.site.login_form``: the ``/admin/`` sign-in."""

    def confirm_login_allowed(self, user: Any) -> None:
        super().confirm_login_allowed(user)
        refuse_until_policy_accepted(user)
