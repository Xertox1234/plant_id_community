"""``settings.py`` must pass Sentry only options the installed SDK accepts (todo 395).

For this project's entire history, ``backend/sentry_sdk.py`` was a five-line
local stub -- "Minimal test stub for sentry_sdk to avoid hard dependency during
local tests" -- committed in the first backend commit. ``backend/`` is the
Django project root and therefore on ``sys.path``, so ``import sentry_sdk``
resolved to the stub and **not** to the real ``sentry-sdk`` that
``requirements.txt`` pins and every environment installs. ``init()`` was
``return None``. No error, trace or profile ever reached Sentry.

The stub did not merely hide Sentry. It hid a **config incompatibility**:
``settings.py`` passed ``request_bodies="medium"``, an option removed in
sentry-sdk 2.x, and the real SDK *rejects* unknown options rather than ignoring
them (``TypeError: Unknown option 'request_bodies'``). ``sentry_sdk.init()``
runs at import time inside ``settings.py``, so with the stub gone and
``SENTRY_DSN`` set, Django would have failed to boot -- a crash that looks like
an unrelated deploy failure to whoever trips it by setting one variable.

That is the shape this guard exists for, and it is not specific to
``request_bodies``: every option here is a string passed to a third-party
function that validates strictly, on a line that only executes in production.
The unit tests never run it, because ``SENTRY_DSN`` is unset in dev and in CI.
A future sentry-sdk major can retire another option exactly this quietly.

Scope note: this reads the settings **source** rather than calling ``init()``.
Calling it would need a DSN and would start a real transport; parsing the call
checks the same thing with no network and no credential.
"""

import ast
from pathlib import Path

import pytest
import sentry_sdk
from sentry_sdk.consts import DEFAULT_OPTIONS


def _settings_source() -> tuple[Path, str]:
    path = (
        Path(__file__).resolve().parents[3] / "plant_community_backend" / "settings.py"
    )
    assert path.is_file(), f"settings.py not found at {path}"
    return path, path.read_text(encoding="utf-8")


def _init_keywords() -> dict[str, ast.expr]:
    """Every keyword passed to ``sentry_sdk.init(...)`` in settings.py."""
    path, source = _settings_source()
    tree = ast.parse(source, filename=str(path))

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "init"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "sentry_sdk"
    ]
    assert len(calls) == 1, (
        f"expected exactly one sentry_sdk.init() call in {path}, found {len(calls)}. "
        "If a second was added, this guard must check it too."
    )

    call = calls[0]
    assert not call.args, (
        "sentry_sdk.init() takes the DSN positionally in some examples; this "
        "project passes it as dsn=. A positional arg is invisible to this guard."
    )
    starred = [kw for kw in call.keywords if kw.arg is None]
    assert not starred, (
        "sentry_sdk.init(**opts) hides the option names from this guard. "
        "Pass options as explicit keywords."
    )
    return {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}


def test_every_sentry_option_is_accepted_by_the_installed_sdk():
    """The regression itself: ``request_bodies`` was removed in sentry-sdk 2.x."""
    keywords = _init_keywords()
    # `dsn` is the one argument that is not a tunable in DEFAULT_OPTIONS.
    unknown = sorted(
        name for name in keywords if name != "dsn" and name not in DEFAULT_OPTIONS
    )
    assert not unknown, (
        f"settings.py passes {unknown} to sentry_sdk.init(), which sentry-sdk "
        f"{sentry_sdk.VERSION} does not accept. The real SDK raises "
        "TypeError: Unknown option, at import time inside settings.py -- so "
        "Django will fail to BOOT as soon as SENTRY_DSN is set. Check the "
        "sentry-sdk migration guide for the replacement; do not just delete "
        "the option without deciding what it was for."
    )


def test_request_bodies_are_off_and_stay_off():
    """The privacy decision, pinned.

    ``send_default_pii=False`` is set deliberately, commented "Don't send
    personally identifiable information". Shipping POST/PUT bodies sends login
    and registration payloads to a third party -- the same data by another
    route. When ``request_bodies="medium"`` was replaced it was a *decision*,
    not a rename, so it is asserted rather than left to the next reader.
    """
    keywords = _init_keywords()

    assert (
        "request_bodies" not in keywords
    ), "request_bodies was removed in sentry-sdk 2.x; use max_request_body_size."

    body_size = keywords.get("max_request_body_size")
    assert body_size is not None, "max_request_body_size must be set explicitly"
    assert isinstance(body_size, ast.Constant) and body_size.value == "never", (
        f"max_request_body_size is {ast.unparse(body_size)}, not 'never'. "
        "Turning request bodies on contradicts send_default_pii=False two "
        "lines above: it sends login payloads to Sentry. If that is genuinely "
        "wanted, state the reason here and in todo 395."
    )

    pii = keywords.get("send_default_pii")
    assert isinstance(pii, ast.Constant) and pii.value is False, (
        "send_default_pii must stay False; it is the other half of the same "
        "decision as max_request_body_size='never'."
    )


def test_no_local_module_shadows_the_real_sentry_sdk():
    """``backend/`` is on sys.path, so any ``sentry_sdk.py`` there wins.

    This is the bug todo 395 fixed, asserted so it cannot come back by someone
    re-adding a convenience stub. Deliberately checks the *resolved* module
    rather than the one known stub path -- the failure mode is "a local file
    shadows an installed package", not "this particular file exists".
    """
    resolved = Path(sentry_sdk.__file__).resolve()
    project_root = Path(__file__).resolve().parents[3]

    # This project's documented venv is backend/venv, so the REAL installed SDK
    # resolves inside project_root too. A bare `not is_relative_to` therefore
    # failed for every local developer while passing in CI, where site-packages
    # sits outside the repo -- a guard that fires on the correct state is one
    # people learn to ignore, which is how a shadowing stub survives. Exempt the
    # package directories; the repo check still catches a stub anywhere else.
    in_site_packages = any(
        part in ("site-packages", "dist-packages") for part in resolved.parts
    )

    assert in_site_packages or not resolved.is_relative_to(project_root), (
        f"import sentry_sdk resolves to {resolved}, inside the project root "
        f"{project_root} and outside any site-packages. A local module is "
        f"shadowing the installed "
        f"sentry-sdk ({sentry_sdk.VERSION}), which silently "
        "disables ALL error reporting -- init() becomes a no-op and nothing "
        "ever reaches Sentry. This is exactly the todo 395 regression."
    )
    assert hasattr(
        sentry_sdk, "capture_message"
    ), "the resolved sentry_sdk has no capture_message; it is not the real SDK"


@pytest.mark.parametrize("option", ["traces_sample_rate", "profiles_sample_rate"])
def test_sample_rates_are_configurable_not_hardcoded(option):
    """Both rates cost money per event; they must stay env-tunable."""
    keywords = _init_keywords()
    assert option in keywords, f"{option} disappeared from settings.py"
    assert isinstance(keywords[option], ast.Call), (
        f"{option} is hardcoded as {ast.unparse(keywords[option])}. It reads "
        "from config() so the rate can be turned down without a deploy."
    )
