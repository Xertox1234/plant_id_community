"""A ``requests`` exception must never be interpolated into a log (todo 358).

``requests`` builds its exception message from the **prepared** URL --
``"401 Client Error: Unauthorized for url: https://host/p?token=..."`` -- so
``str(e)`` writes any query-string credential into the log. Three keys leaked
this way (``TREFLE_API_KEY`` as ``token``, ``PLANTNET_API_KEY`` as ``api-key``,
``OPENWEATHER_API_KEY`` as ``appid``), and the worst site was a retry decorator
that logged once per attempt. Nothing at the log site mentions a key, which is
why neither a reader nor a taint scanner catches it. Use
``log_safe_api_error(exc)`` from ``apps.core.utils.pii_safe_logging``.

Todo 354 shipped this guard scoped to the two query-string-authenticated
services. Todo 358 widened it to the whole backend code tree: the four
remaining offenders were all header-authenticated and safe *today*, which is a
property of where the key happens to sit rather than anything structural.

What the guard does NOT see -- so a green run is not misread:

* Only calls whose func unparses with the prefix ``logger.``. A module logging
  through ``self.logger.`` or ``log.`` is invisible. ``apps/core/utils/
  structured_logger.py`` is the only code in that shape and is imported
  nowhere.
* ``logger.exception("constant message")`` passes, yet still writes the
  exception message via the traceback. That is why both ``get_service_status``
  methods branch on ``isinstance(exc, requests.RequestException)`` instead.
* ``raise SomeError(f"...{e}")`` is not a logger call and is never inspected.
  ``packages/wagtail_forum/wagtail_forum/embeds.py:89`` does exactly this and
  is deliberately out of scope: its oEmbed request carries no credential (the
  params are ``url``/``format``/``maxwidth``/``maxheight``), and the caller
  swallows ``EmbedNotFoundException`` into a plain link card, so the message
  reaches no response body. Widening the sweep to ``packages/`` covers that
  file's *logger* calls only.
* ``return {"error": str(e)}`` is not a logger call either, and is likewise
  never inspected -- the same gap as ``raise``, but reaching a response body
  rather than a message. Five such sites survive in the service layer (todo
  377); the two that an anonymous endpoint actually reaches, PlantNet's and
  Trefle's ``get_service_status``, were fixed in todo 354.
* The handler type is matched on the literal string ``requests``, so
  ``from requests.exceptions import ConnectionError`` would slip past. No file
  imports that way today, and ``docs/rules/triggers.json``'s
  ``requests-exception-interpolated`` has the identical limitation.
"""

import ast
import pathlib
import re
import subprocess

import pytest

# apps/core/tests/<this file> -> backend/
BACKEND = pathlib.Path(__file__).resolve().parents[3]

# The importable code trees, named explicitly. NOT a recursive walk of
# BACKEND: `venv/` lives there, and third-party packages interpolate requests
# exceptions freely.
ROOTS = ("apps", "packages", "plant_community_backend")

# Build artefacts that shadow real source. `packages/wagtail_forum/build/`
# holds 120 stale gitignored copies of the package; scanning them means the
# sweep disagrees with itself between a local tree and a fresh CI checkout,
# and a violation already fixed in the real file fails from its stale twin.
# `test_the_sweep_scans_no_build_artefact` proves this list is complete.
SKIP_DIRS = {
    "build",
    "dist",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "site-packages",
}

# The ONLY shapes that may carry the exception into a log. Anything else --
# `e`, `str(e)`, `e.args[0]`, `e.response.url`, `e.request.url` -- reproduces
# the prepared URL and is reported. An allowlist on purpose: the first version
# of this guard marked safe every name under ANY attribute access, which let
# `e.response.url` and `e.request.url` (literally the prepared URL) and
# `e.args[0]` (literally the string `str(e)` returns) through unflagged.
APPROVED_SHAPES = tuple(
    re.compile(pattern)
    for pattern in (
        r"^type\(\w+\)\.__name__$",
        r"^\w+\.response\.status_code$",
        # The provider's error BODY, not its URL. Pre-dates this guard;
        # PlantNet and plant.health both log it beneath their status line.
        r"^\w+\.response\.text(\[[^\]]*\])?$",
        r"^(\w+\.)*log_safe_api_error\(\w+\)$",
    )
)


def _backend_python_files(roots=ROOTS):
    """Every ``.py`` under ``roots``, artefact directories removed.

    ``roots`` is a parameter so the anti-vacuity test can drive the collapse
    case without editing module state.
    """

    def keep(path):
        return not any(
            part in SKIP_DIRS or part.endswith(".egg-info")
            for part in path.relative_to(BACKEND).parts
        )

    return [
        path
        for root in roots
        for path in sorted((BACKEND / root).rglob("*.py"))
        if keep(path)
    ]


def _files_with_requests_handlers(roots=ROOTS):
    """Files carrying any ``except`` clause naming a ``requests`` exception.

    Deliberately BROADER than the guard's own predicate, which additionally
    requires ``handler.name`` -- discovery must not be able to hide a file
    from the sweep it feeds. Returns paths relative to ``BACKEND`` so pytest
    node ids stay readable.
    """
    found = []
    for path in _backend_python_files(roots):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.ExceptHandler)
            and "requests" in ast.unparse(node.type or ast.Constant(None))
            for node in ast.walk(tree)
        ):
            found.append(str(path.relative_to(BACKEND)))
    return found


def _requests_handlers_interpolating_the_exception(path):
    """Yield (lineno, source) for every logger call that interpolates a
    ``requests`` exception.

    Scoping is deliberate. The exception name is checked only INSIDE its own
    ``except requests...`` block -- a later ``except Exception as e`` rebinds
    the same name and can never receive a ``RequestException``, so flagging it
    would be a false positive. Aliases assigned inside the handler
    (``last_exception = e``) are followed across the whole function, because
    the retry decorator logs one after the loop has ended.

    Keyword arguments are inspected as well as positional ones:
    ``logger.error("failed", extra={"err": str(e)})`` is the same leak.

    Only the shapes in ``APPROVED_SHAPES`` may carry the exception; everything
    else is reported. That is an allowlist rather than "any attribute access is
    fine", because ``e.response.url``, ``e.request.url`` and ``e.args[0]`` are
    all attribute accesses and all reproduce the prepared URL.
    """

    def logger_calls(scope):
        for call in (n for n in ast.walk(scope) if isinstance(n, ast.Call)):
            if ast.unparse(call.func).startswith("logger."):
                yield call

    def interpolates(call, names):
        for arg in [*call.args, *[kw.value for kw in call.keywords]]:
            safe = set()
            for sub in ast.walk(arg):
                if isinstance(sub, (ast.Attribute, ast.Call, ast.Subscript)) and any(
                    shape.match(ast.unparse(sub)) for shape in APPROVED_SHAPES
                ):
                    safe |= {n for n in ast.walk(sub) if isinstance(n, ast.Name)}
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Name) and sub.id in names and sub not in safe:
                    return True
        return False

    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for handler in (n for n in ast.walk(func) if isinstance(n, ast.ExceptHandler)):
            if not handler.name:
                continue
            if "requests" not in ast.unparse(handler.type or ast.Constant(None)):
                continue
            # The bound name, inside its own handler only.
            for call in logger_calls(handler):
                if interpolates(call, {handler.name}):
                    yield call.lineno, ast.unparse(call)
            # Aliases assigned in the handler outlive it -- check the function.
            aliases = {
                t.id
                for n in ast.walk(handler)
                if isinstance(n, ast.Assign)
                and isinstance(n.value, ast.Name)
                and n.value.id == handler.name
                for t in n.targets
                if isinstance(t, ast.Name)
            }
            if aliases:
                for call in logger_calls(func):
                    if interpolates(call, aliases):
                        yield call.lineno, ast.unparse(call)


@pytest.mark.parametrize("service", _files_with_requests_handlers())
def test_no_requests_handler_interpolates_its_exception(service):
    """Drift guard (todos 354, 358).

    Parametrised over every file DISCOVERED to catch a ``requests`` exception,
    with no hardcoded list. If discovery ever collapses to nothing this
    degrades to a single skipped test rather than a failure, which is what
    ``test_the_sweep_is_not_vacuous`` below exists to catch.
    """
    offenders = list(_requests_handlers_interpolating_the_exception(BACKEND / service))
    assert not offenders, "\n".join(f"  line {n}: {src}" for n, src in offenders)


def test_the_sweep_is_not_vacuous():
    """A sweep must assert it swept something.

    The obvious implementation -- ``pathlib.Path("apps").glob(...)`` -- is
    CWD-relative, and pytest never chdirs. Run from the repo root instead of
    ``backend/`` and that glob returns ``[]``, the parametrisation above
    collects one skipped test, and the guard reports green having read no
    files at all.
    """
    scanned = _backend_python_files()
    assert len(scanned) > 400, f"scope collapsed to {len(scanned)} files"

    discovered = _files_with_requests_handlers()
    # The two services whose keys actually leaked. A membership floor, not a
    # scope limit: a count floor would fail on a legitimate consolidation of
    # two HTTP clients.
    for known in (
        "apps/plant_identification/services/plantnet_service.py",
        "apps/plant_identification/services/trefle_service.py",
    ):
        assert known in discovered, f"{known} fell out of the sweep: {discovered}"

    # And the collapse case really does collapse, proven without editing
    # module state or restoring a mutated file afterwards.
    assert _backend_python_files(roots=("no-such-directory",)) == []


def test_the_sweep_scans_no_build_artefact():
    """``SKIP_DIRS`` must stay complete as the tree grows.

    Cross-checked against git rather than against the list itself, so a future
    artefact directory nobody thought of (``.tox/``, a second package's
    ``build/``) fails here and names the files. Untracked-but-not-ignored is
    fine -- that is new source someone has not committed yet.
    """
    scanned = [str(p.relative_to(BACKEND)) for p in _backend_python_files()]
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            input="\n".join(scanned),
            capture_output=True,
            text=True,
            cwd=BACKEND,
        )
    except OSError as exc:  # no git binary at all
        pytest.skip(f"git unavailable: {exc}")
    # 0 = some path is ignored, 1 = none is. Anything higher is git refusing
    # to answer (not a checkout, dubious ownership), which is not a verdict.
    if result.returncode > 1:
        pytest.skip(f"git check-ignore unusable: {result.stderr.strip()}")
    assert not result.stdout.split(), (
        "gitignored files reached the sweep; extend SKIP_DIRS:\n" + result.stdout
    )


PLANTED = """
import logging
import requests

logger = logging.getLogger(__name__)


def positional():
    try:
        pass
    except requests.exceptions.RequestException as e:
        logger.error(f"boom: {e}")


def keyword():
    try:
        pass
    except requests.exceptions.RequestException as e:
        logger.error("boom", extra={"err": str(e)})


def aliased():
    last = None
    try:
        pass
    except requests.exceptions.RequestException as e:
        last = e
    logger.error(f"after the loop: {last}")


def attribute_leaks():
    # Every one of these is an attribute access that rebuilds the prepared
    # URL, and every one passed before the APPROVED_SHAPES allowlist.
    try:
        pass
    except requests.exceptions.RequestException as e:
        logger.error(f"resp url: {e.response.url}")
        logger.error(f"req url: {e.request.url}")
        logger.error(f"args: {e.args[0]}")


def approved():
    try:
        pass
    except requests.exceptions.RequestException as e:
        logger.error(f"ok: {log_safe_api_error(e)}")
        logger.error(f"ok: {type(e).__name__} {e.response.status_code}")
        logger.error(f"ok: {e.response.text[:500]}")
    except Exception as e:
        # A RequestException can never reach here; the clause above shadows it.
        logger.error(f"ok: {e}")
"""


def test_the_guard_flags_a_planted_violation(tmp_path):
    """The guard can actually fail, and does not fire on the approved shapes.

    The specimen is written to ``tmp_path`` rather than checked in, because a
    checked-in bad example would be swept by the guard itself.
    """
    planted = tmp_path / "planted_service.py"
    planted.write_text(PLANTED, encoding="utf-8")

    flagged = {
        src for _, src in _requests_handlers_interpolating_the_exception(planted)
    }

    assert any("boom: {e}" in src for src in flagged), flagged
    assert any("extra=" in src for src in flagged), flagged
    assert any("after the loop" in src for src in flagged), flagged
    # The attribute shapes that rebuild the prepared URL. These are the ones
    # the pre-allowlist guard let through, so each is pinned separately rather
    # than as one "any of these" assertion.
    for leak in ("resp url", "req url", "args"):
        assert any(leak in src for src in flagged), (leak, flagged)
    assert not [src for src in flagged if "ok:" in src], flagged
