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

**A dropped opt-out is invisible to behavioural tests.** The reference host
happens to mount the package *inside* its ``v1`` namespace, so
``NamespaceVersioning`` resolves an allowed version and every request still
returns 200 with or without this mixin (measured: dropping it left
``test_api_mounted.py`` + ``test_boards.py`` green). The breakage only appears on
a differently-mounted host. That is why the guard below is structural.

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
"""


class UnversionedForumAPIMixin:
    """Opt this view out of host request-versioning. Rationale: module docstring."""

    versioning_class = None
