"""Wagtail admin (``/cms/``) guards for user deletion (Plan B, task 7).

Wagtail's Users screen has its own delete view and a bulk "Delete" action,
both of which call ``User.delete()`` and so skip the erase job (Firestore,
Firebase login, forum content, the retention record). Block both; staff
delete an account from the Django admin "Delete account" actions instead.
"""

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from wagtail import hooks
from wagtail.users.views.bulk_actions import DeleteBulkAction

BLOCKED_MESSAGE = (
    "Users can't be deleted here. Use the Django admin Users list, action "
    "'Delete account', so the account's data is erased."
)


@hooks.register("before_delete_user")
def block_user_delete(request, user):
    messages.error(request, BLOCKED_MESSAGE)
    return redirect(reverse("wagtailusers_users:index"))


class BlockedDeleteBulkAction(DeleteBulkAction):
    """Replaces Wagtail's bulk delete: no user is ever deletable here."""

    def check_perm(self, obj):
        return False

    @classmethod
    def execute_action(cls, objects, model=None, **kwargs):
        # check_perm already filters every user out; never delete anything.
        return 0, 0


# Later order wins: the registry keeps the last class per action_type.
hooks.register("register_bulk_action", BlockedDeleteBulkAction, order=100)
