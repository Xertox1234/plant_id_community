"""The single statement of the forum API's versioning opt-out (audit L20).

Every forum API view sets ``versioning_class = None``. The rationale was
previously commented on exactly one of the 17 views, so 16 read as unexplained
copy-paste. It is stated here, once.

**Why the opt-out.** The package is host-agnostic: a host mounts
``wagtail_forum.api.urls`` wherever it likes. If that host sets
``DEFAULT_VERSIONING_CLASS`` — ``NamespaceVersioning`` in particular, which the
plant_id reference host does — DRF resolves the version from the mount's URL
namespace and 404s (``NotFound``) when no segment of it is in
``ALLOWED_VERSIONS``. The forum's own URLs carry no version segment, so a host
that mounts the package outside a version namespace would break every forum
request. It opts out rather than inheriting a host default it cannot satisfy.

**What catches a dropped opt-out, precisely.** It depends on where the view is
mounted, and the two cases differ:

- **Package views**: the package's own API test urlconf
  (``wagtail_forum.tests.api.urls``) mounts at namespace ``wagtail_forum_api``
  (Django auto-namespaces from this package's ``app_name``), which is in no
  host's ``ALLOWED_VERSIONS`` — so dropping the opt-out 404s them immediately
  (``NotFound: Invalid version in URL path``). The package API suite does catch
  this, though as an undiagnosed mass-404 rather than a named failure.
- **Host-only views and host subclasses**: invisible. The reference host mounts
  the forum *inside* its ``v1`` namespace, and ``NamespaceVersioning`` splits a
  nested namespace on ``:`` and accepts the allowed ``v1`` segment — so those
  requests return 200 with or without the mixin. Measured: reordering
  ``SimilarTopicsView``'s bases left its own 18 tests AND all 251 package API
  tests green; only the structural guard failed.

That second case is what the guard below exists for.

**Consequence.** The forum API is unversioned by contract: response shapes are
pinned by the package's tests and README (see ``## List envelopes`` there), not
by a version negotiated per request. A breaking response change is a package
version bump plus coordinated client updates, never a new ``/v2/`` path.

Usage — the mixin **must precede** the DRF base class, so its attribute wins the
MRO::

    class BoardListView(UnversionedForumAPIMixin, generics.ListAPIView):
        ...

``apps/forum_host/tests/test_forum_versioning_optout.py`` walks the host URLconf
and fails if any mounted forum view (package or host subclass) drops the opt-out
— DRF's own default for ``DEFAULT_VERSIONING_CLASS`` is ``None``, so a dropped
mixin is invisible to every other test until a host turns versioning on.

**Also composes presence-touching (todo 301).** ``TouchLastSeenMixin`` (see
``presence.py``) is a separate, independently-testable concern — it is a base
here, not inlined, so it keeps its own docstring and can be unit-tested in
isolation. It rides along on this mixin rather than getting a second
``must-be-on-every-view`` convention of its own: the same structural guard
above that catches a dropped versioning opt-out also catches a dropped
presence touch, since both now come from one inherited class.
"""

from .presence import TouchLastSeenMixin


class UnversionedForumAPIMixin(TouchLastSeenMixin):
    """Opt this view out of host request-versioning. Rationale: module docstring."""

    versioning_class = None
