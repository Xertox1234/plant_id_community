"""Every rate-limited view documents its 429 (todo 599 items 1 and 2).

A view under ``@ratelimit(block=True)`` (django-ratelimit's decorator or
``apps.core.ratelimit``'s) answers 429 through
``apps.core.exceptions.custom_exception_handler``, so its OpenAPI operation
must list 429, normally as ``apps.core.openapi.RATE_LIMITED``. Only LOGIN
did; register, verify-email, update-profile, identify-plant and the rest
were silent.

The decorator leaves no marker, so this test finds it by walking each view
function's wrappers (``__wrapped__`` and closure cells) for django-ratelimit's
inner ``_wrapped`` and reads its ``block`` and ``method`` from that closure.
Function views (``@api_view``) only: ``method_decorator`` applies its
decorator per call, so a class-based view's limit is not visible here.
"""

import inspect
import re

import django_ratelimit.decorators
from django.conf import settings
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from rest_framework.decorators import api_view
from rest_framework.response import Response

_RATELIMIT_FILE = inspect.getsourcefile(django_ratelimit.decorators)
_ALL_METHODS = (None,)  # django_ratelimit.ALL


def _closure(fn):
    cells = fn.__closure__ or ()
    return dict(zip(fn.__code__.co_freevars, (c.cell_contents for c in cells)))


def _blocking_methods(fn):
    """The HTTP methods a blocking ratelimit wrapper around ``fn`` limits:
    a set of upper-case names, ``{"*"}`` for every method, empty for none."""
    methods, seen, todo = set(), set(), [fn]
    while todo:
        current = todo.pop()
        if not callable(current) or id(current) in seen:
            continue
        seen.add(id(current))
        code = getattr(current, "__code__", None)
        if code is None:
            continue
        cells = _closure(current)
        if code.co_filename == _RATELIMIT_FILE and "block" in cells:
            if cells["block"]:
                method = cells.get("method")
                if method in (_ALL_METHODS, None):
                    methods.add("*")
                elif isinstance(method, str):
                    methods.add(method.upper())
                else:
                    methods.update(m.upper() for m in method)
        todo.append(getattr(current, "__wrapped__", None))
        todo.extend(v for v in cells.values() if inspect.isfunction(v))
    return methods


def _view_function(view, method):
    """The function an ``@api_view`` handler calls, or None for a class view."""
    handler = getattr(view, method.lower(), None)
    func = _closure(handler).get("func") if inspect.ismethod(handler) else None
    return func if inspect.isfunction(func) else None


def _missing_429(patterns=None):
    generator = SchemaGenerator(patterns=patterns)
    schema = generator.get_schema(request=None, public=True)
    prefix = "^" + settings.SPECTACULAR_SETTINGS["SCHEMA_PATH_PREFIX"]
    limited, missing = [], []
    for route, _regex, method, view in generator._get_paths_and_endpoints():
        func = _view_function(view, method)
        if func is None:
            continue
        methods = _blocking_methods(func)
        if not ({"*", method.upper()} & methods):
            continue
        trimmed = re.sub(prefix, "", route, flags=re.IGNORECASE)
        if not trimmed.startswith("/"):
            trimmed = "/" + trimmed
        operation = schema["paths"].get(trimmed, {}).get(method.lower())
        if operation is None:
            continue  # not in the public schema
        limited.append(f"{method} {trimmed}")
        if "429" not in operation["responses"]:
            missing.append(f"{method} {trimmed}")
    return limited, missing


def test_every_rate_limited_view_documents_429():
    limited, missing = _missing_429()
    print(f"{len(limited)} rate-limited operations: {sorted(limited)}")
    # The walk still finds the decorator: both flavours, on known views.
    for known in (
        "POST /auth/login/",  # django_ratelimit
        "PATCH /auth/user/update/",  # apps.core.ratelimit
        "POST /plant-identification/identify/",
    ):
        assert known in limited, f"{known} not detected as rate-limited"
    assert not missing, "rate-limited but no 429 documented: " + ", ".join(
        sorted(missing)
    )


def test_gate_catches_a_rate_limited_view_without_429():
    """Canary: an undocumented 429 is reported, and a documented one is not."""
    from apps.core import ratelimit as core_ratelimit
    from apps.core.openapi import RATE_LIMITED
    from drf_spectacular.utils import extend_schema
    from rest_framework import serializers

    body = extend_schema(
        request=None,
        responses={200: serializers.DictField()},
    )

    @body
    @api_view(["POST"])
    @django_ratelimit.decorators.ratelimit(key="ip", rate="1/m", method="POST")
    def undocumented(request):
        return Response({})

    @extend_schema(
        request=None, responses={200: serializers.DictField(), 429: RATE_LIMITED}
    )
    @api_view(["POST"])
    @core_ratelimit.ratelimit(key="ip", rate="1/m", method="POST")
    def documented(request):
        return Response({})

    @body
    @api_view(["POST"])
    @django_ratelimit.decorators.ratelimit(key="ip", rate="1/m", block=False)
    def not_blocking(request):
        return Response({})

    limited, missing = _missing_429(
        patterns=[
            path("api/v1/canary/undocumented/", undocumented),
            path("api/v1/canary/documented/", documented),
            path("api/v1/canary/not-blocking/", not_blocking),
        ]
    )

    assert sorted(limited) == [
        "POST /canary/documented/",
        "POST /canary/undocumented/",
    ]
    assert missing == ["POST /canary/undocumented/"]
