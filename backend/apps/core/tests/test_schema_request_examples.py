"""Request examples in the OpenAPI docs for plant_identification, users and blog
(todo 582).

Every POST/PUT/PATCH in those apps that takes a body carries at least one
request example in the generated schema, and the example values are obviously
fake. Paths are post-trim (SCHEMA_PATH_PREFIX_TRIM strips /api/v1).
"""

import re

import pytest
from drf_spectacular.generators import SchemaGenerator

APP_PATH_PREFIXES = {
    "users": ("/auth/", "/api/auth/"),
    "plant_identification": ("/plant-identification/",),
    "blog": ("/blog/", "/blog-api/"),
}
WRITE_METHODS = ("post", "put", "patch")

# Write operations whose view reads no request body, so they have no example.
BODILESS_WRITES = {
    ("post", "/auth/verify-email/resend/"),
    ("post", "/auth/unsubscribe/one-click/"),  # RFC 8058: token in the query
    ("post", "/blog/comments/{id}/flag/"),
    ("post", "/blog/newsletter/unsubscribe/one-click/"),
}

# Keys whose example value would be a secret if it were real.
SECRET_KEYS = ("password", "token", "key", "refresh", "secret", "auth", "p256dh")


@pytest.fixture(scope="module")
def schema():
    return SchemaGenerator().get_schema(request=None, public=True)


def _app_of(path):
    for app, prefixes in APP_PATH_PREFIXES.items():
        if path.startswith(prefixes):
            return app
    return None


def _write_operations(schema):
    for path, operations in schema["paths"].items():
        app = _app_of(path)
        if app is None:
            continue
        for method, operation in operations.items():
            if method in WRITE_METHODS:
                yield app, method, path, operation


def _request_examples(operation):
    body = operation.get("requestBody") or {}
    return [
        example
        for media in body.get("content", {}).values()
        for example in media.get("examples", {}).values()
    ]


def _strings(value, key=""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v, k)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item, key)
    elif isinstance(value, str):
        yield key, value


def test_every_write_with_a_body_has_a_request_example(schema):
    missing = []
    bodiless = set()
    for _app, method, path, operation in _write_operations(schema):
        if "requestBody" not in operation:
            bodiless.add((method, path))
        elif not _request_examples(operation):
            missing.append(f"{method.upper()} {path}")
    assert not missing, "no request example: " + ", ".join(missing)
    # A write the schema shows without a body must be a known body-less view,
    # not one whose body drf-spectacular failed to see.
    assert bodiless == BODILESS_WRITES


def test_each_app_has_request_examples(schema):
    counts = dict.fromkeys(APP_PATH_PREFIXES, 0)
    for app, _method, _path, operation in _write_operations(schema):
        counts[app] += len(_request_examples(operation))
    print(f"request examples per app: {counts}")
    assert all(counts.values()), counts


# A secret-like value is an allowlisted shape, not "contains example": short
# lowercase words after "example-", so "example-<a real token>" fails (todo 599
# item 3).
FAKE_SECRET = re.compile(r"example(-[a-z0-9]{1,12})+")
# Under ANY key, a long unbroken run of token characters looks like a real
# credential (a JWT segment, an API key) and is refused. Not "/" or "-":
# URL paths and hyphenated placeholders are made of short words.
TOKEN_RUN = re.compile(r"[A-Za-z0-9_+=]{20,}")


def _fake_problem(key, text):
    """Why ``text`` under ``key`` might be real, or None when obviously fake."""
    if "@" in text and not text.endswith("@example.com"):
        return "an address outside example.com"
    if TOKEN_RUN.search(text):
        return "a token-like run of 20+ characters"
    if any(word in key.lower() for word in SECRET_KEYS):
        if not FAKE_SECRET.fullmatch(text):
            return "a secret-like value not shaped example-<short-words>"
    return None


def test_request_example_values_are_obviously_fake(schema):
    problems = []
    for _app, method, path, operation in _write_operations(schema):
        for example in _request_examples(operation):
            for key, text in _strings(example.get("value")):
                problem = _fake_problem(key, text)
                if problem:
                    problems.append(
                        f"{method.upper()} {path} {key}={text!r}: {problem}"
                    )
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize(
    "key,text",
    [
        ("password", "example-" + "Zq8" * 8),  # the old check passed this
        ("refresh", "example-eyJhbGciOiJIUzI1NiJ9"),
        ("token", "not-an-example"),
        ("api_key", "example_Live_Key"),
        ("description", "sk" + "_live_" + "a1B2c3D4e5F6g7H8i9J0"),
        ("email", "someone@gmail.com"),
    ],
)
def test_the_fake_check_refuses_real_looking_values(key, text):
    assert _fake_problem(key, text) is not None


@pytest.mark.parametrize(
    "key,text",
    [
        ("password", "example-password-not-real"),
        ("auth", "example-auth-secret"),
        ("email", "gardener@example.com"),
        ("bio", "Grows tomatoes on a balcony."),
    ],
)
def test_the_fake_check_accepts_obvious_placeholders(key, text):
    assert _fake_problem(key, text) is None
