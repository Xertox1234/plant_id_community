"""Every `REQUIRED__` placeholder in `.env.example` must refuse to boot (todo 367).

`.env.example` marks every must-replace value with a
``REQUIRED__GENERATE_WITH__`` / ``REQUIRED__GET_FROM__`` placeholder. Until todo
367 nothing enforced that convention and **four of the five booted clean in
production**:

* ``JWT_SECRET_KEY`` -- accepted, and it signed every JWT. Its own checks are
  set / ``!= SECRET_KEY`` / ``len >= 50``, and the 66-character placeholder
  cleared all three.
* ``PLANT_ID_API_KEY`` / ``PLANTNET_API_KEY`` -- accepted; the placeholders are
  41 and 44 characters against floors of 32 and 20.
* ``FIELD_ENCRYPTION_KEY`` -- accepted and never read. Removed by todo 367,
  along with ``django-encrypted-model-fields``.
* ``SECRET_KEY`` -- the only one rejected, and by **coincidence**: its generate
  hint happens to contain the word "secret", which is in ``INSECURE_PATTERNS``.

WHY A SUBPROCESS. This asserts that *settings refuse to boot*, which is a
module-import-time property. Importing ``plant_community_backend.settings`` a
second time in-process gets the already-cached module and proves nothing, and
the checks are guarded on ``not DEBUG`` while the test suite runs with DEBUG
semantics of its own. A clean interpreter with a controlled environment is the
only place the real behaviour is observable.

``env -i``-style isolation matters too: this repo has been bitten before by a
developer ``.env`` masking a missing variable. ``python-decouple`` consults
``os.environ`` before its ``.env`` repository, so the values set here win, but
the environment is still built from scratch rather than inherited.

WHY IT ENUMERATES THE FILE. A hardcoded list of key names is a list somebody has
to remember to extend. Driving the parametrisation off ``.env.example`` means a
placeholder added tomorrow is covered today.
"""

import os
import pathlib
import re
import subprocess
import sys

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[3]
ENV_EXAMPLE = BACKEND / ".env.example"

PLACEHOLDER_PREFIX = "REQUIRED__"

# A production-mode environment that boots. Every value here is syntactically
# valid and semantically fake; no network or database call happens at import.
# `test_the_baseline_environment_boots` is the control that keeps this honest --
# without it, a baseline broken for an unrelated reason would make every case
# below "pass" by failing for the wrong cause.
# The key-shaped values below are fabricated for this test and are flagged by
# detect-secrets on sight. They carry inline allowlist pragmas rather than
# baseline entries: a pragma explains itself at the site, and a baseline entry
# for a test fixture is a line-number-keyed record nobody re-reads.
BASELINE = {
    "DJANGO_SETTINGS_MODULE": "plant_community_backend.settings",
    "DEBUG": "False",
    "SECRET_KEY": "Jq7vRt2Xw9Pz4Lm8Nb3Kd6Hf1Gs5Ya0Ce7Uu2Ii9Oo4Ee6Tt3Rr8Ww1Qq5Zz",  # pragma: allowlist secret
    "JWT_SECRET_KEY": "Aa1Bb2Cc3Dd4Ee5Ff6Gg7Hh8Ii9Jj0Kk1Ll2Mm3Nn4Oo5Pp6Qq7Rr8Ss9Tt0Uu",  # pragma: allowlist secret
    "DATABASE_URL": "postgres://u:p@localhost:5432/db",
    "ALLOWED_HOSTS": "example.com",
    "PLANT_ID_API_KEY": "0123456789abcdef0123456789abcdef0123",  # pragma: allowlist secret
    "PLANTNET_API_KEY": "2b10abcdefghijklmnopqrstuv",  # pragma: allowlist secret
    "REDIS_URL": "redis://localhost:6379/0",
}

PIN_RE = re.compile(rf"^([A-Z0-9_]+)=({re.escape(PLACEHOLDER_PREFIX)}\S*)")


def _placeholders():
    """`(key, verbatim_value)` for every `REQUIRED__` line in `.env.example`."""
    found = []
    for raw in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        match = PIN_RE.match(raw.strip())
        if match:
            found.append((match.group(1), match.group(2)))
    return found


def _boot(overrides):
    """Import settings in a clean interpreter. Returns the CompletedProcess."""
    env = {
        # Enough of the real environment for the interpreter to run at all.
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        **BASELINE,
        **overrides,
    }
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_env_example_still_has_placeholders():
    """Guards the parametrisation against collapsing to zero cases.

    If `.env.example` is reworded so nothing matches, every test below silently
    disappears and the suite reports green having asserted nothing.
    """
    found = _placeholders()
    assert len(found) >= 4, f"only {len(found)} placeholders found: {found}"
    names = {key for key, _ in found}
    assert {"SECRET_KEY", "JWT_SECRET_KEY"} <= names, names


def test_the_baseline_environment_boots():
    """The control.

    Without it, a baseline that is broken for an unrelated reason makes every
    rejection test below pass for the wrong cause -- the false-green shape this
    repo keeps rediscovering.
    """
    result = _boot({})
    assert result.returncode == 0, (
        "the baseline production environment does not boot, so the rejection "
        f"tests below prove nothing:\n{result.stderr[-3000:]}"
    )


@pytest.mark.parametrize("key,value", _placeholders(), ids=lambda v: str(v)[:30])
def test_a_verbatim_placeholder_refuses_to_boot(key, value):
    """Production settings must reject the unmodified `.env.example` value."""
    result = _boot({key: value})

    assert result.returncode != 0, (
        f"{key} booted cleanly with its verbatim .env.example placeholder -- "
        "that value is committed to a PUBLIC repository.\n"
        f"stdout tail:\n{result.stdout[-2000:]}"
    )
    combined = result.stdout + result.stderr
    assert key in combined, (
        f"boot failed but the message never names {key}, so an operator cannot "
        f"tell which value is wrong:\n{combined[-3000:]}"
    )
    assert "ImproperlyConfigured" in combined, combined[-3000:]


def test_the_removed_encryption_setting_is_gone():
    """`FIELD_ENCRYPTION_KEY` was accepted and never read (todo 367).

    No `.py` referenced it and `encrypted_model_fields` was not in
    INSTALLED_APPS, so `django-encrypted-model-fields` was an unused crypto
    dependency: attack surface and audit noise for no behaviour. Both were
    removed; this pins that they stay removed rather than drifting back via a
    copy-pasted example file.
    """
    assert "FIELD_ENCRYPTION_KEY" not in ENV_EXAMPLE.read_text(encoding="utf-8")
    requirements = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
    assert "django-encrypted-model-fields" not in requirements
