#!/usr/bin/env python3
"""Tests for scripts/check_suppressions.py.

Run: python3 scripts/test_check_suppressions.py
Also run by .github/workflows/harness-ci.yml (a required status check).

The cases that matter are the two real failure modes this script exists to
catch, both taken from live data:
  - Twisted CVE-2026-42304, suppressed as "no stable fix", while the real
    2026-08-31 pip-audit report lists fix_versions ["26.4.0", "26.4.0rc2"].
  - A `tracked_by` pointing at a completed, archived todo (the todo-089 bug).
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import check_suppressions as cs  # noqa: E402


def entry(**overrides):
    base = {
        "id": "CVE-2026-0001",
        "package": "somepkg",
        "pinned": "1.0.0",
        "reason": "Not reachable from app code.",
        "clears_when": "Upstream ships a fix.",
        "added": "2026-01-01",
        "expires": "2026-06-01",
        "owner": "@someone",
        "tracked_by": "355",
    }
    base.update(overrides)
    return base


def doc(*entries):
    return {"version": 1, "policy": {"max_expiry_days": 180}, "pip_audit": list(entries)}


class ValidateTests(unittest.TestCase):
    def test_clean_entry_passes(self):
        self.assertEqual(cs.validate(doc(entry())), [])

    def test_missing_field_is_reported(self):
        problems = cs.validate(doc(entry(owner="")))
        self.assertTrue(any("`owner`" in p for p in problems), problems)

    def test_duplicate_id_is_reported(self):
        problems = cs.validate(doc(entry(), entry()))
        self.assertTrue(any("duplicate" in p for p in problems), problems)

    def test_window_longer_than_policy_is_reported(self):
        problems = cs.validate(doc(entry(added="2026-01-01", expires="2027-01-01")))
        self.assertTrue(any("max_expiry_days" in p for p in problems), problems)

    def test_expires_before_added_is_reported(self):
        problems = cs.validate(doc(entry(added="2026-06-01", expires="2026-01-01")))
        self.assertTrue(any("must be after" in p for p in problems), problems)

    def test_unresolvable_tracked_by_is_reported(self):
        problems = cs.validate(doc(entry(tracked_by="999999")))
        self.assertTrue(any("resolves to no todo" in p for p in problems), problems)

    def test_id_with_shell_metacharacters_is_rejected(self):
        problems = cs.validate(doc(entry(id="CVE-2026-1; rm -rf /")))
        self.assertTrue(any("command line" in p for p in problems), problems)

    def test_validate_is_not_time_dependent(self):
        """--validate runs on every PR; a long-past expiry must NOT fail it."""
        long_past = entry(added="2019-12-01", expires="2020-01-01")
        self.assertEqual(cs.validate(doc(long_past)), [])

    def test_real_suppressions_file_validates(self):
        self.assertEqual(cs.validate(cs.load()), [])


class EmitFlagsTests(unittest.TestCase):
    def test_flags_are_paired(self):
        flags = cs.emit_flags(doc(entry(id="CVE-1"), entry(id="CVE-2"))).split()
        self.assertEqual(flags, ["--ignore-vuln", "CVE-1", "--ignore-vuln", "CVE-2"])

    def test_unsafe_id_refuses_to_emit(self):
        with self.assertRaises(cs.SuppressionError):
            cs.emit_flags(doc(entry(id="a b")))

    def test_real_file_emits_one_flag_per_entry(self):
        data = cs.load()
        self.assertEqual(
            len(cs.emit_flags(data).split()), 2 * len(cs.entries(data))
        )


class RecheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _report(self, dependencies):
        path = pathlib.Path(self.tmp.name) / "report.json"
        path.write_text(json.dumps({"dependencies": dependencies}))
        return path

    def test_shipped_fix_is_reported(self):
        report = self._report([
            {"name": "somepkg", "version": "1.0.0",
             "vulns": [{"id": "CVE-2026-0001", "fix_versions": ["1.1.0"], "aliases": []}]}
        ])
        problems = cs.recheck(doc(entry()), report, dt.date(2026, 2, 1))
        self.assertTrue(any("a fix has shipped" in p for p in problems), problems)

    def test_no_fix_version_is_not_reported(self):
        """An advisory with no fix must stay suppressed — this is the llm case."""
        report = self._report([
            {"name": "somepkg", "version": "1.0.0",
             "vulns": [{"id": "CVE-2026-0001", "fix_versions": [], "aliases": []}]}
        ])
        self.assertEqual(cs.recheck(doc(entry()), report, dt.date(2026, 2, 1)), [])

    def test_alias_match_is_honoured(self):
        """The suppression is keyed on the CVE; the report keys on PYSEC. Twisted's real shape."""
        report = self._report([
            {"name": "somepkg", "version": "1.0.0",
             "vulns": [{"id": "PYSEC-2026-999", "fix_versions": ["2.0.0"],
                        "aliases": ["CVE-2026-0001"]}]}
        ])
        problems = cs.recheck(doc(entry()), report, dt.date(2026, 2, 1))
        self.assertTrue(any("a fix has shipped" in p for p in problems), problems)

    def test_duplicate_vuln_rows_union_their_fix_versions(self):
        """Twisted appears twice, with ["26.4.0"] and ["26.4.0rc2"].

        Reporting only the release candidate would invite exactly the stale
        conclusion ("still RC-only") that kept the suppression alive.
        """
        report = self._report([
            {"name": "somepkg", "version": "1.0.0", "vulns": [
                {"id": "CVE-2026-0001", "fix_versions": ["26.4.0"], "aliases": []},
                {"id": "CVE-2026-0001", "fix_versions": ["26.4.0rc2"], "aliases": []},
            ]}
        ])
        problems = cs.recheck(doc(entry()), report, dt.date(2026, 2, 1))
        self.assertTrue(any("26.4.0," in p or "26.4.0rc2,26.4.0" in p for p in problems), problems)

    def test_expired_suppression_is_reported(self):
        report = self._report([])
        problems = cs.recheck(doc(entry(expires="2026-06-01")), report, dt.date(2026, 6, 2))
        self.assertTrue(any("expired" in p for p in problems), problems)

    def test_not_yet_expired_is_quiet(self):
        report = self._report([])
        self.assertEqual(
            cs.recheck(doc(entry(expires="2026-06-01")), report, dt.date(2026, 5, 31)), []
        )

    def test_missing_report_fails_rather_than_passing(self):
        problems = cs.recheck(doc(entry()), pathlib.Path("/nonexistent.json"), dt.date(2026, 1, 2))
        self.assertTrue(any("report not found" in p for p in problems), problems)

    def test_tracked_by_a_completed_todo_is_reported(self):
        """The todo-089 failure, caught mechanically."""
        archived = sorted(cs.TODOS.glob("archive/*.md"))
        if not archived:
            self.skipTest("no archived todo available to point at")
        issue_id = archived[0].name.split("-")[0]
        problems = cs.recheck(
            doc(entry(tracked_by=issue_id)), self._report([]), dt.date(2026, 1, 2)
        )
        self.assertTrue(any("COMPLETED" in p for p in problems), problems)


class TodoResolutionTests(unittest.TestCase):
    def test_resolves_a_live_todo(self):
        self.assertIsNotNone(cs.resolve_todo("355"))

    def test_resolves_an_archived_todo(self):
        self.assertIsNotNone(cs.resolve_todo("089"))

    def test_unknown_id_resolves_to_none(self):
        self.assertIsNone(cs.resolve_todo("999999"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
