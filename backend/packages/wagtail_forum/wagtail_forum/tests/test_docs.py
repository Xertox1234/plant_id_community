"""The README is the reusability contract — keep it from silently re-rotting.

Audit 2026-07-11 M18 found a 24-line README that documented none of the
settings, none of the public signals, and no bootstrap steps, while the package
was already pip-installable. Prose alone re-rots on the next setting added, so
the coverage is asserted here instead: adding a key to ``conf.DEFAULTS`` or a
new public ``Signal`` fails this test until the README documents it.
"""

import ast
import pathlib
import re

import pytest
import wagtail_forum
from wagtail_forum import conf, signals

# Source-tree layout: <pkg>/wagtail_forum/__init__.py -> ../README.md. An
# installed wheel has no README, so skip rather than fail there.
README = pathlib.Path(wagtail_forum.__file__).resolve().parent.parent / "README.md"

pytestmark = pytest.mark.skipif(
    not README.exists(), reason="README.md is not shipped in an installed wheel"
)


def _readme():
    return README.read_text(encoding="utf-8")


def test_readme_documents_every_setting():
    """Every WAGTAILFORUM_* setting a host can override must be in the README.

    Asserted on the fully-qualified name (``WAGTAILFORUM_SPAM_MAX_LINKS``), not
    the bare key, so a passing mention of the word "spam" in prose cannot
    satisfy it.

    Matched with a trailing word boundary, not a plain substring: a typo'd
    ``WAGTAILFORUM_MENTION_MAX_PER_POSTX`` *contains* the real name and would
    slip through an ``in`` check (it did — caught in review of todo 262).
    """
    text = _readme()
    missing = [
        name
        for name in sorted(conf.DEFAULTS)
        if not re.search(rf"WAGTAILFORUM_{name}\b", text)
    ]
    assert missing == [], f"README.md does not document: {missing}"


def _declared_signals():
    """Names bound to a ``Signal()`` call at module level in wagtail_forum.signals.

    Parsed from the source rather than read off ``vars(signals)``: the module
    also imports Django's own ``pre_delete``/``post_delete`` to hang receivers
    on, and those are not this package's public API.
    """
    tree = ast.parse(pathlib.Path(signals.__file__).read_text(encoding="utf-8"))
    return sorted(
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "Signal"
        for target in node.targets
        if isinstance(target, ast.Name)
    )


def test_readme_documents_every_public_signal():
    """Every Signal declared in wagtail_forum.signals is host-facing API."""
    text = _readme()
    public = _declared_signals()
    # Guard the discovery itself: an empty set would make the assert vacuous.
    assert public, "no public signals discovered — check wagtail_forum.signals"
    # Every discovered name must really be a Signal on the imported module —
    # catches a rename that the AST scan would otherwise report as documented.
    for name in public:
        assert isinstance(getattr(signals, name), signals.Signal), name
    missing = [name for name in public if name not in text]
    assert missing == [], f"README.md does not document signals: {missing}"
