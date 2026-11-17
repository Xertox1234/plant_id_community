"""The forum's avatar fallback (``WAGTAILFORUM_AUTHOR_AVATAR_FALLBACK``).

The app has two photos per member: ``User.avatar``, set on the mobile and web
profile screens, and ``ForumProfile.avatar``, which only the web forum
settings can set. A member who set the first and not the second was shown as
an initial everywhere in the forum. The forum package asks this callable for
any author whose forum profile has no avatar.
"""


def account_avatar_url(user) -> str | None:
    """URL of the account photo, or None. Reads only ``User.avatar``, a
    column already loaded with the user, so it never queries."""
    avatar = getattr(user, "avatar", None)
    return avatar.url if avatar else None
