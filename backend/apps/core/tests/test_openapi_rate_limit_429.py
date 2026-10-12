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
A class-based view's handler is walked too (todo 607 item 7):
``method_decorator`` keeps the decorators it applies per call in its
wrapper's closure, as a list. Those views get their 429 from the schema hook
in ``plant_community_backend.api_schema`` (``_throttled_actions`` on a
ViewSet, ``_forum_throttled_methods`` on a forum view).

A limited operation that cannot be found in the schema fails (item 6), and so
does a 429 documented on a method the view's limit does not cover (item 8).
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
        for value in cells.values():
            if inspect.isfunction(value):
                todo.append(value)
            elif isinstance(value, (list, tuple)):  # method_decorator's list
                todo.extend(v for v in value if inspect.isfunction(v))
    return methods


def _view_function(view, method):
    """The function that handles ``method``: what an ``@api_view`` handler
    calls, a ViewSet's action, or a class view's method handler."""
    handler = getattr(view, method.lower(), None)
    if inspect.ismethod(handler):
        func = _closure(handler.__func__).get("func")
        if inspect.isfunction(func):
            return func  # @api_view
    action = getattr(view, "action", None)
    if action:
        handler = getattr(view, action, None)
    return getattr(handler, "__func__", None)


def _missing_429(patterns=None):
    generator = SchemaGenerator(patterns=patterns)
    schema = generator.get_schema(request=None, public=True)
    prefix = "^" + settings.SPECTACULAR_SETTINGS["SCHEMA_PATH_PREFIX"]
    limited, missing, unmatched, extra = [], [], [], []
    for route, _regex, method, view in generator._get_paths_and_endpoints():
        func = _view_function(view, method)
        if func is None:
            continue
        methods = _blocking_methods(func)
        trimmed = re.sub(prefix, "", route, flags=re.IGNORECASE)
        if not trimmed.startswith("/"):
            trimmed = "/" + trimmed
        operation = schema["paths"].get(trimmed, {}).get(method.lower())
        op = f"{method} {trimmed}"
        if not ({"*", method.upper()} & methods):
            # Limited, but not on this method: no 429 to document (item 8).
            if methods and operation and "429" in operation["responses"]:
                extra.append(op)
            continue
        if operation is None:
            # The generator yields only public endpoints, so a limited one the
            # schema lacks means the path trimming drifted (item 6).
            unmatched.append(op)
            continue
        limited.append(op)
        if "429" not in operation["responses"]:
            missing.append(op)
    return limited, missing, unmatched, extra


def test_every_rate_limited_view_documents_429():
    limited, missing, unmatched, extra = _missing_429()
    print(f"{len(limited)} rate-limited operations: {sorted(limited)}")
    # The walk still finds the decorator: both flavours, on known views.
    for known in (
        "POST /auth/login/",  # django_ratelimit
        "PATCH /auth/user/update/",  # apps.core.ratelimit
        "POST /plant-identification/identify/",
        "POST /calendar/api/garden-beds/",  # ViewSet action, method_decorator
        "POST /forum/boards/{slug}/topics/",  # forum class view
    ):
        assert known in limited, f"{known} not detected as rate-limited"
    assert not unmatched, "rate-limited but not found in the schema: " + ", ".join(
        sorted(unmatched)
    )
    assert not missing, "rate-limited but no 429 documented: " + ", ".join(
        sorted(missing)
    )
    assert not extra, "429 documented on a method that is not limited: " + ", ".join(
        sorted(extra)
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

    @extend_schema(
        request=None,
        responses={200: serializers.DictField(), 429: RATE_LIMITED},
    )
    @api_view(["GET", "POST"])
    @django_ratelimit.decorators.ratelimit(key="ip", rate="1/m", method="POST")
    def get_documents_429(request):
        return Response({})

    limited, missing, unmatched, extra = _missing_429(
        patterns=[
            path("api/v1/canary/undocumented/", undocumented),
            path("api/v1/canary/documented/", documented),
            path("api/v1/canary/not-blocking/", not_blocking),
            path("api/v1/canary/get-documents-429/", get_documents_429),
        ]
    )

    assert sorted(limited) == [
        "POST /canary/documented/",
        "POST /canary/get-documents-429/",
        "POST /canary/undocumented/",
    ]
    assert missing == ["POST /canary/undocumented/"]
    assert unmatched == []
    assert extra == ["GET /canary/get-documents-429/"]


def test_gate_sees_class_based_views():
    """Canary, todo 607 item 7: a class view or ViewSet action limited through
    ``method_decorator`` is found, and the schema hook documents its 429 only
    when the ViewSet names the action in ``_throttled_actions``."""
    from django.utils.decorators import method_decorator
    from drf_spectacular.utils import extend_schema
    from rest_framework import serializers, viewsets
    from rest_framework.views import APIView

    limit = method_decorator(
        django_ratelimit.decorators.ratelimit(key="ip", rate="1/m", method="POST")
    )

    class UndocumentedView(APIView):
        @extend_schema(request=None, responses={200: serializers.DictField()})
        @limit
        def post(self, request):
            return Response({})

    class _Actions(viewsets.ViewSet):
        @extend_schema(request=None, responses={201: serializers.DictField()})
        @limit
        def create(self, request):
            return Response({})

    class MarkedViewSet(_Actions):
        _throttled_actions = frozenset({"create"})

    class UnmarkedViewSet(_Actions):
        pass

    limited, missing, unmatched, extra = _missing_429(
        patterns=[
            path("api/v1/canary/class/", UndocumentedView.as_view()),
            path(
                "api/v1/canary/marked/<int:pk>/",
                MarkedViewSet.as_view({"post": "create"}),
            ),
            path(
                "api/v1/canary/unmarked/", UnmarkedViewSet.as_view({"post": "create"})
            ),
        ]
    )

    assert sorted(limited) == [
        "POST /canary/class/",
        "POST /canary/marked/{id}/",  # {pk} renamed after the hook
        "POST /canary/unmarked/",
    ]
    assert sorted(missing) == ["POST /canary/class/", "POST /canary/unmarked/"]
    assert unmatched == extra == []
