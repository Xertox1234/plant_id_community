"""Tests for the environment-integrity stamp (todos 378/379).

Two layers, deliberately:

* the pure ``compare()``/``read_pins()`` layer, driven with synthesized data;
* **wiring tests that call the conftest hooks themselves.** Without those, both
  layers could pass while ``conftest.py`` never calls ``compare()`` at all —
  the "decorative test" this repo has shipped before
  (``docs/rules/testing.md`` on mutation-verifying a guard).

``env_integrity`` is imported *through conftest* on purpose. conftest loads it
by file path via ``importlib.util.spec_from_file_location`` under the private
name ``_env_integrity`` — deliberately NOT a ``sys.path`` shim, which would
leak every module beside it to top level. Importing the file a second way here
would yield a distinct module object, and monkeypatching that one would
silently fail to affect the code under test, so these tests reach the exact
object the hooks call by going through ``conftest``.
"""

import subprocess
import sys

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
        "modelsearch == 1.3.2\n"  # spaced pins are pip-legal
        "celery[redis]==5.4.0\n"
        "-e ./packages/wagtail_forum\n"
        "-r other.txt\n"
        "# a comment\n"
        "\n"
    )
    pins = env_integrity.read_pins(req)
    assert pins == {"wagtail": "8.0", "modelsearch": "1.3.2", "celery": "5.4.0"}


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

    The unconditional assertion is the point. On a healed venv — and in CI,
    which installs fresh from requirements.txt — `drift_report()` returns `[]`
    and the loop below never runs, so without it this test would be green by
    emptiness while asserting nothing at all.
    """
    report = env_integrity.drift_report()
    assert isinstance(report, list)
    for line in report:
        assert line.startswith(("  mismatched:", "  not installed:"))


# --------------------------------------------------------------------------
# Wiring — these call the conftest hooks, so removing a call site fails here
# --------------------------------------------------------------------------


def test_report_header_reports_the_drift_counts_from_compare(monkeypatch):
    # Distinct counts on purpose: with 1 pin and 1 extra, swapping the
    # `pinned`/`unpinned` labels renders an identical string and the
    # assertion below cannot see it.
    monkeypatch.setattr(
        env_integrity,
        "read_pins",
        lambda *a, **k: {"wagtail": "8.0", "celery": "5.4.0", "django": "6.1.1"},
    )
    monkeypatch.setattr(
        env_integrity,
        "compare",
        lambda *a, **k: (
            [("wagtail", "8.0", "7.4.3")],
            [("swapper", "1.5.0")],
            [("nltk", "3.9.2")],
        ),
    )
    header = "\n".join(conftest.pytest_report_header(config=None))
    # Assert the whole line, not substrings: `1 mismatched` appearing somewhere
    # cannot distinguish the real line from one with `pinned`/`unpinned`
    # swapped, and todo 380 treats the unpinned count as load-bearing.
    assert "deps: 3 pinned, 1 mismatched, 1 not installed, 1 unpinned" in header


def test_report_header_always_stamps_interpreter_and_tree():
    header = "\n".join(conftest.pytest_report_header(config=None))
    assert "env:" in header
    assert "tree:" in header and "HEAD" in header
    assert "uncommitted file(s)" in header


def _boom(*a, **k):
    raise OSError("simulated environment failure")


def test_report_header_survives_a_broken_dependency_check(monkeypatch):
    """A failing comparison degrades that ONE line, not the whole stamp.

    The earlier version of this test asserted the header collapsed to `[]`,
    which pinned the wrong behaviour: the interpreter and tree lines do not
    depend on the comparison, and they are the half a revert-control check
    actually reads.
    """
    monkeypatch.setattr(env_integrity, "read_pins", _boom)
    header = "\n".join(conftest.pytest_report_header(config=None))
    assert "deps: unavailable" in header
    assert "env:" in header
    assert "tree:" in header


def test_report_header_survives_the_checker_failing_to_load(monkeypatch):
    """`env_integrity` is None when the module cannot be imported at all."""
    monkeypatch.setattr(conftest, "env_integrity", None)
    header = "\n".join(conftest.pytest_report_header(config=None))
    assert "deps: unavailable" in header
    assert "env:" in header


def test_terminal_summary_survives_a_broken_check(monkeypatch):
    """The summary shares the header's fail-open contract; pin it too."""
    monkeypatch.setattr(env_integrity, "drift_report", _boom)
    reporter = DummyReporter()
    conftest.pytest_terminal_summary(reporter, exitstatus=1, config=None)
    assert reporter.lines == []


def test_terminal_summary_names_the_running_interpreter_not_a_fixed_path(
    monkeypatch,
):
    """Naming `backend/venv` when the drift is in another venv misdirects.

    The comparison measures `sys.prefix`; the message must agree, or a reader
    inspects a clean `backend/venv` and discounts a true warning.
    """
    monkeypatch.setattr(
        env_integrity, "drift_report", lambda: ["  mismatched: wagtail (…)"]
    )
    reporter = DummyReporter()
    conftest.pytest_terminal_summary(reporter, exitstatus=1, config=None)
    assert sys.prefix in reporter.text


def test_tree_state_scopes_the_status_call_to_backend(monkeypatch):
    """An unscoped count includes web/ and mobile/ dirt, which is noise here.

    Asserts the pathspec actually reaches git, not just that the label says
    "backend/" — the label is an f-string and would survive the scoping being
    deleted.
    """
    calls = []

    def fake_git(*args):
        calls.append(args)
        return "" if args[0] == "status" else "abc1234"

    monkeypatch.setattr(conftest, "_git", fake_git)
    conftest._tree_state()
    status_call = next(c for c in calls if c[0] == "status")
    assert status_call[-2:] == (
        "--",
        ".",
    ), f"git status must be scoped to backend/, got: {status_call}"


def test_tree_state_reports_unknown_rather_than_zero_when_git_fails(monkeypatch):
    """A silent false zero would fake a clean control arm."""
    monkeypatch.setattr(conftest, "_git", lambda *a: None)
    assert "unknown uncommitted file(s)" in conftest._tree_state()


def test_wiring_tests_patch_the_object_the_hooks_actually_call():
    """The identity these wiring tests depend on, asserted rather than assumed.

    If conftest ever loaded the checker under a different object, every
    monkeypatch below would patch a disconnected copy and the wiring tests
    would keep passing while proving nothing.
    """
    assert conftest.env_integrity is env_integrity


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


# --------------------------------------------------------------------------
# The CLI the shell hook actually calls
# --------------------------------------------------------------------------


def test_main_hook_mode_prints_the_drift_and_exits_zero(monkeypatch, capsys, tmp_path):
    """End-to-end on `main()`, which nothing else covers.

    `test-check-test-env.sh` stubs `backend/venv/bin/python` with a bash
    reimplementation of this output — correct by construction, so it proves
    nothing about `main()` itself. Mutating the `--hook` flag to `--hookk`
    previously left all 44 assertions across both suites green while breaking
    production completely.
    """
    req = tmp_path / "requirements.txt"
    req.write_text("definitely-not-installed-xyz==9.9.9\n")
    monkeypatch.setattr(env_integrity, "REQUIREMENTS", req)
    rc = env_integrity.main(["--hook"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "definitely-not-installed-xyz" in out
    assert "9.9.9" in out


def test_main_is_silent_and_zero_when_the_environment_is_clean(
    monkeypatch, capsys, tmp_path
):
    req = tmp_path / "requirements.txt"
    req.write_text("# nothing pinned\n")
    monkeypatch.setattr(env_integrity, "REQUIREMENTS", req)
    assert env_integrity.main(["--hook"]) == 0
    assert capsys.readouterr().out == ""


def test_main_without_the_hook_flag_refuses(capsys):
    """The flag is the contract with the shell hook; a typo must be loud."""
    assert env_integrity.main([]) == 2
    assert capsys.readouterr().out == ""


def test_main_fails_open_when_the_comparison_raises(monkeypatch, capsys):
    monkeypatch.setattr(env_integrity, "drift_report", _boom)
    assert env_integrity.main(["--hook"]) == 0
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------
# Guards that a weak test previously failed to discriminate
# --------------------------------------------------------------------------


def _completed(returncode, stdout=""):
    return subprocess.CompletedProcess(["git"], returncode, stdout=stdout, stderr="")


def test_git_helper_returns_none_when_the_command_fails(monkeypatch):
    """Drives `_git` itself, not `_tree_state`'s handling of None.

    The sibling test monkeypatches `_git` wholesale, so it cannot tell whether
    `_git` actually checks the return code — deleting that check left it green.

    `subprocess.run` is stubbed rather than shelling out to a real failing git:
    a live invocation would tie this to the host's git version and to the tests
    running inside a checkout at all, and `stdout` is deliberately non-empty so
    dropping the return-code check yields "junk", not the falsy "" that would
    mask the regression.
    """
    monkeypatch.setattr(
        conftest.subprocess, "run", lambda *a, **k: _completed(1, "junk")
    )
    assert conftest._git("status", "--porcelain") is None


def test_git_helper_returns_none_when_git_is_unavailable(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(conftest.subprocess, "run", boom)
    assert conftest._git("rev-parse", "--short", "HEAD") is None


def test_git_helper_distinguishes_a_clean_tree_from_a_failure(monkeypatch):
    """ "" is a clean tree; None is "could not tell". Collapsing them lies."""
    monkeypatch.setattr(
        conftest.subprocess, "run", lambda *a, **k: _completed(0, "  \n")
    )
    assert conftest._git("status", "--porcelain") == ""


def test_a_failing_tree_stamp_does_not_delete_the_dependency_line(monkeypatch):
    """The two stamp halves are independently guarded.

    Sharing one try/except means a git failure also suppresses the drift
    counts, which are the more important half.
    """
    monkeypatch.setattr(conftest, "_tree_state", _boom)
    header = "\n".join(conftest.pytest_report_header(config=None))
    assert "210 pinned" in header or "pinned" in header
    assert "deps: unavailable" not in header


def test_a_missing_checker_module_loads_as_none_instead_of_raising(
    monkeypatch, tmp_path
):
    """The guard that keeps a broken checker from aborting the whole suite.

    An unguarded `exec_module` turns a missing or syntactically broken
    `env_integrity.py` into an ImportError during conftest collection: pytest
    exits 4 with zero tests run, for all 2386 of them. Verified by hand at
    review time; pinned here so it stays fixed.
    """
    monkeypatch.setattr(conftest, "_BACKEND", tmp_path)
    assert conftest._load_env_integrity() is None


def test_a_broken_checker_module_loads_as_none_instead_of_raising(
    monkeypatch, tmp_path
):
    target = tmp_path / "apps" / "core"
    target.mkdir(parents=True)
    (target / "env_integrity.py").write_text("this is not valid python (\n")
    monkeypatch.setattr(conftest, "_BACKEND", tmp_path)
    assert conftest._load_env_integrity() is None
