"""Tests for the environment-integrity stamp (todos 378/379).

Two layers, deliberately:

* the pure ``compare()``/``read_pins()`` layer, driven with synthesized data;
* **wiring tests that call the conftest hooks themselves.** Without those, both
  layers could pass while ``conftest.py`` never calls ``compare()`` at all —
  the "decorative test" this repo has shipped before
  (``docs/rules/testing.md`` on mutation-verifying a guard).

``env_integrity`` is imported *through conftest* on purpose. conftest loads it
via a ``sys.path`` shim as top-level ``env_integrity``; importing it a second
way would yield a distinct module object, and monkeypatching that one would
silently fail to affect the code under test.
"""

import conftest
from conftest import env_integrity


class DummyReporter:
    """Minimal stand-in for pytest's TerminalReporter."""

    def __init__(self):
        self.lines = []

    def write_sep(self, sep, title="", **kwargs):
        self.lines.append(f"--- {title} ---")

    def write_line(self, line, **kwargs):
        self.lines.append(line)

    @property
    def text(self):
        return "\n".join(self.lines)


# --------------------------------------------------------------------------
# compare() — the pure function
# --------------------------------------------------------------------------


def test_compare_reports_a_version_mismatch_with_both_versions():
    mismatched, missing, extra = env_integrity.compare(
        {"wagtail": "8.0"}, {"wagtail": "7.4.3"}
    )
    assert mismatched == [("wagtail", "8.0", "7.4.3")]
    assert missing == []
    assert extra == []


def test_compare_reports_a_pinned_package_that_is_not_installed_at_all():
    """The bucket a naive "compare what's installed" check misses entirely.

    On 2026-09-08 django-ninja and swapper were pinned and absent; a check
    that only diffs versions of installed packages sees nothing wrong.
    """
    mismatched, missing, extra = env_integrity.compare({"django-ninja": "1.7.0"}, {})
    assert missing == [("django-ninja", "1.7.0")]
    assert mismatched == []


def test_compare_separates_mismatched_from_missing():
    mismatched, missing, _ = env_integrity.compare(
        {"wagtail": "8.0", "swapper": "1.5.0"}, {"wagtail": "7.4.3"}
    )
    assert [n for n, _, _ in mismatched] == ["wagtail"]
    assert [n for n, _ in missing] == ["swapper"]


def test_compare_reports_installed_but_unpinned_as_extra():
    _, _, extra = env_integrity.compare({}, {"nltk": "3.9.2"})
    assert extra == [("nltk", "3.9.2")]


def test_compare_excludes_editable_installs_from_extra():
    """`-e ./packages/wagtail_forum` is not a `name==version` pin.

    Without this exclusion the check reports wagtail-forum as unpinned on
    every run forever — a permanent false positive in a check whose entire
    purpose is to stay credible.
    """
    _, _, extra = env_integrity.compare(
        {}, {"wagtail-forum": "0.1.0"}, {"wagtail-forum"}
    )
    assert extra == []


def test_compare_matching_environment_is_clean():
    assert env_integrity.compare({"wagtail": "8.0"}, {"wagtail": "8.0"}) == ([], [], [])


# --------------------------------------------------------------------------
# parsing helpers
# --------------------------------------------------------------------------


def test_normalize_follows_pep503():
    assert env_integrity.normalize("ruamel.yaml.clib") == "ruamel-yaml-clib"
    assert env_integrity.normalize("Django_Ninja") == "django-ninja"


def test_read_pins_skips_editable_and_include_lines(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text(
        "wagtail==8.0\n"
        "celery[redis]==5.4.0\n"
        "-e ./packages/wagtail_forum\n"
        "-r other.txt\n"
        "# a comment\n"
        "\n"
    )
    pins = env_integrity.read_pins(req)
    assert pins == {"wagtail": "8.0", "celery": "5.4.0"}


def test_format_lines_names_the_packages_and_their_versions():
    lines = env_integrity.format_lines([("wagtail", "8.0", "7.4.3")], [])
    assert "wagtail" in lines[0]
    assert "8.0" in lines[0] and "7.4.3" in lines[0]


def test_format_lines_caps_a_long_list(monkeypatch):
    monkeypatch.setattr(env_integrity, "MAX_LISTED", 2)
    lines = env_integrity.format_lines(
        [(f"pkg{i}", "1.0", "0.9") for i in range(5)], []
    )
    assert "+3 more" in lines[0]


def test_format_lines_is_empty_when_there_is_no_drift():
    assert env_integrity.format_lines([], []) == []


def test_drift_report_runs_against_the_real_environment():
    """No mocks: proves the real pipeline executes and returns sane shapes.

    Holds whether or not the venv is currently drifted, so it stays valid
    after `pip install -r requirements.txt` heals it.
    """
    for line in env_integrity.drift_report():
        assert line.startswith(("  mismatched:", "  not installed:"))


# --------------------------------------------------------------------------
# Wiring — these call the conftest hooks, so removing a call site fails here
# --------------------------------------------------------------------------


def test_report_header_reports_the_drift_counts_from_compare(monkeypatch):
    monkeypatch.setattr(
        env_integrity,
        "compare",
        lambda *a, **k: ([("wagtail", "8.0", "7.4.3")], [("swapper", "1.5.0")], []),
    )
    header = "\n".join(conftest.pytest_report_header(config=None))
    assert "1 mismatched" in header
    assert "1 not installed" in header


def test_report_header_always_stamps_interpreter_and_tree():
    header = "\n".join(conftest.pytest_report_header(config=None))
    assert "env:" in header
    assert "tree:" in header and "HEAD" in header
    assert "uncommitted file(s)" in header


def test_report_header_survives_a_broken_check(monkeypatch):
    """Fails open: a stamp must never break a test run."""
    monkeypatch.setattr(
        env_integrity, "read_pins", lambda *a, **k: (_ for _ in ()).throw(OSError())
    )
    assert conftest.pytest_report_header(config=None) == []


def test_terminal_summary_names_the_drifted_package(monkeypatch):
    monkeypatch.setattr(
        env_integrity,
        "drift_report",
        lambda: ["  mismatched: wagtail (pinned 8.0, installed 7.4.3)"],
    )
    reporter = DummyReporter()
    conftest.pytest_terminal_summary(reporter, exitstatus=1, config=None)
    assert "wagtail" in reporter.text
    assert "ENVIRONMENT DRIFT" in reporter.text


def test_terminal_summary_is_silent_when_the_environment_is_clean(monkeypatch):
    monkeypatch.setattr(env_integrity, "drift_report", lambda: [])
    reporter = DummyReporter()
    conftest.pytest_terminal_summary(reporter, exitstatus=0, config=None)
    assert reporter.lines == []
