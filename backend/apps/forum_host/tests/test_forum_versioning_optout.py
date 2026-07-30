"""L20 (todo 277): the forum versioning opt-out is a DRIFT GUARD, not a test of
behaviour.

Every mounted forum view must inherit `versioning_class = None` from the single
`UnversionedForumAPIMixin` (`wagtail_forum/api/versioning.py`), which states the
rationale once.

What this covers that the package's own tests do not: **host-only views and host
subclasses.**

This host sets `DEFAULT_VERSIONING_CLASS = NamespaceVersioning` with
`ALLOWED_VERSIONS = ["v1", "v2"]`, and the two mounts behave differently:

- The package's test urlconf (`wagtail_forum.tests.api.urls`) resolves to
  namespace `wagtail_forum_api` — not an allowed version — so dropping the
  opt-out 404s the package API suite. It IS caught there (measured), just as an
  undiagnosed mass-404.
- This host mounts the forum under `v1`, and `NamespaceVersioning` splits the
  nested `v1:wagtail_forum_api` on `:` and accepts `v1`. So on the real mount,
  requests return 200 either way — and the three host-only AI views
  (`summary`/`compose_assist`/`similar`) plus every throttled host subclass have
  NO package test standing behind them. Measured: reordering
  `SimilarTopicsView`'s bases left its own 18 tests and all 251 package API tests
  green; only this file went red.

Walks the HOST urlconf (`apps/forum_host/api_urls.py`) because that is what prod
serves: some routes mount package views straight, others mount host subclasses
(`api.py` throttle wrappers, `SearchView`'s `SemanticSearchMixin`), and a
subclass with re-ordered bases is exactly the regression this catches.
"""

from rest_framework.views import APIView
from wagtail_forum.api.versioning import UnversionedForumAPIMixin

# api_urls.py mounts 20 routes today. A floor (not an equality) so adding a route
# doesn't fail this test spuriously — its job is to stop the walk passing
# vacuously if the urlconf import ever yields an empty/renamed pattern list.
MIN_MOUNTED_FORUM_ROUTES = 20


def _mounted_view_classes():
    from apps.forum_host import api_urls as host

    return {p.name: p.callback.view_class for p in host.urlpatterns}


def test_every_mounted_forum_view_opts_out_of_versioning():
    views = _mounted_view_classes()
    assert len(views) >= MIN_MOUNTED_FORUM_ROUTES, (
        f"only {len(views)} forum routes walked (expected >= "
        f"{MIN_MOUNTED_FORUM_ROUTES}) — did api_urls.urlpatterns move or shrink?"
    )
    missing = [name for name, cls in views.items() if cls.versioning_class is not None]
    assert not missing, (
        f"forum views with host versioning still engaged: {missing} — mix in "
        f"UnversionedForumAPIMixin (see wagtail_forum/api/versioning.py)."
    )


def test_opt_out_comes_from_the_shared_mixin_and_wins_the_mro():
    """The 'stated once' half of L20, plus the ordering that makes it effective.

    `versioning_class is None` above would also pass if a view re-declared it
    inline — the duplication the mixin exists to remove. And DRF's own `APIView`
    declares `versioning_class = api_settings.DEFAULT_VERSIONING_CLASS` in its
    class body, so the mixin only wins by preceding `APIView` in the MRO. A
    subclass written `class X(APIView, UnversionedForumAPIMixin)` inherits the
    HOST default instead — silently identical today (that default is `None`),
    404s under a versioning host. Hence an explicit order assertion.
    """
    offenders = {}
    for name, cls in _mounted_view_classes().items():
        mro = cls.__mro__
        if UnversionedForumAPIMixin not in mro:
            offenders[name] = f"{cls.__name__} does not inherit the shared mixin"
            continue
        if mro.index(UnversionedForumAPIMixin) > mro.index(APIView):
            offenders[name] = (
                f"{cls.__name__} lists the mixin after APIView — DRF's "
                "DEFAULT_VERSIONING_CLASS wins the MRO"
            )
            continue
        # Forum-owned classes only: APIView's own declaration is the base the
        # mixin is there to override, not a duplicate of the rationale.
        local = [
            k.__name__
            for k in mro
            if k is not UnversionedForumAPIMixin
            and not k.__module__.startswith("rest_framework")
            and "versioning_class" in vars(k)
        ]
        if local:
            offenders[name] = f"versioning_class re-declared on {local}"
    assert not offenders, (
        "the versioning opt-out must be stated once, on UnversionedForumAPIMixin: "
        f"{offenders}"
    )
