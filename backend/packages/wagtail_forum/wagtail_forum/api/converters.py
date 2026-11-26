"""URL converters for the forum API.

``forum_username`` is ``str`` minus NUL (forum audit F210). PostgreSQL refuses
a NUL in any text parameter, so a ``users/ali%00ce/`` that reached a
``username=`` lookup raised ValueError and 500ed. No username can hold a NUL,
so the route simply does not match and the request is a plain 404 — one guard
for every username capture instead of one per view.

Registered on import: both URLconfs that capture a username (this package's
``api/urls.py`` and the host's throttled mirror) import this module first.
"""

from django.urls import register_converter


class ForumUsernameConverter:
    regex = "[^/\x00]+"

    def to_python(self, value: str) -> str:
        return value

    def to_url(self, value: str) -> str:
        return value


register_converter(ForumUsernameConverter, "forum_username")
