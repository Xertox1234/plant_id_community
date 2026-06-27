"""drf-spectacular schema extensions for the users app.

Registers an OpenAPI security scheme for `CookieJWTAuthentication` (the project's
default authenticator). Without it, drf-spectacular emits a "could not resolve
authenticator" warning for *every* authenticated endpoint and documents no
security scheme, so Swagger's "Authorize" button is unavailable. drf-spectacular
discovers extensions by import, so this module is imported in `UsersConfig.ready`.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CookieJWTScheme(OpenApiAuthenticationExtension):
    target_class = "apps.users.authentication.CookieJWTAuthentication"
    # NOT "cookieAuth": that name is already claimed by drf-spectacular's built-in
    # SessionAuthentication scheme (the `sessionid` cookie). Reusing it triggers a
    # "2 components with identical names … different identities" warning and an
    # incorrect schema. This is a distinct cookie (`access_token`), so it needs a
    # distinct name.
    name = "jwtCookieAuth"

    def get_security_definition(self, auto_schema):
        # The JWT access token is sent in the httpOnly `access_token` cookie
        # (CookieJWTAuthentication falls back to an Authorization: Bearer header).
        return {"type": "apiKey", "in": "cookie", "name": "access_token"}
