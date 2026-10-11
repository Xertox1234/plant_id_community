"""Request examples in the OpenAPI docs for plant_identification, users and blog
(todo 582).

Every POST/PUT/PATCH in those apps that takes a body carries at least one
request example in the generated schema, and the example values are obviously
fake. Paths are post-trim (SCHEMA_PATH_PREFIX_TRIM strips /api/v1).
"""

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


def test_request_example_values_are_obviously_fake(schema):
    for _app, method, path, operation in _write_operations(schema):
        for example in _request_examples(operation):
            for key, text in _strings(example.get("value")):
                where = f"{method.upper()} {path} {key}={text!r}"
                if "@" in text:
                    assert text.endswith("@example.com"), where
                if any(word in key.lower() for word in SECRET_KEYS):
                    assert "example" in text, where
