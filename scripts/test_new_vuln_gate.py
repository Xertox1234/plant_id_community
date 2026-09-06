#!/usr/bin/env python3
"""Tests for scripts/new_vuln_gate.py.

Run: python3 scripts/test_new_vuln_gate.py
Also run by .github/workflows/harness-ci.yml (a required status check).

The cases that matter are the ways this gate could be WRONG rather than merely
broken, because a gate that passes when it should not is invisible:
  - a missing report must FAIL, never pass silently
  - one side of a pair missing must FAIL (a half-configured gate always passes)
  - an advisory renamed between two audits must not read as new
  - npm `via` strings are transitive edges, not advisories
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import new_vuln_gate as gate  # noqa: E402


def pip_report(*vulns):
    """vulns: (package, version, id, [aliases]) tuples."""
    deps = []
    for name, version, vuln_id, aliases in vulns:
        deps.append({
            "name": name,
            "version": version,
            "vulns": [{"id": vuln_id, "aliases": list(aliases), "fix_versions": []}],
        })
    return {"dependencies": deps}


def npm_report(*entries):
    """entries: (package, ghsa, severity) tuples."""
    vulns = {}
    for name, ghsa, severity in entries:
        vulns[name] = {
            "name": name,
            "severity": severity,
            "via": [{
                "source": 1234567,
                "name": name,
                "url": f"https://github.com/advisories/{ghsa}",
                "severity": severity,
            }],
        }
    return {"vulnerabilities": vulns}


class ExtractionTests(unittest.TestCase):
    def test_pip_collects_id_and_aliases(self):
        got = gate.pip_advisories(
            pip_report(("twisted", "25.5.0", "PYSEC-2026-160", ["CVE-2026-42304"]))
        )
        (label, keys), = got.items()
        self.assertIn("PYSEC-2026-160", label)
        self.assertIn("twisted 25.5.0", label)
        self.assertEqual(keys, {"PYSEC-2026-160", "CVE-2026-42304"})

    def test_npm_extracts_ghsa_from_url(self):
        got = gate.npm_advisories(npm_report(("@tiptap/core", "GHSA-cp6q-959q-f8rh", "moderate")))
        (label, keys), = got.items()
        self.assertIn("GHSA-cp6q-959q-f8rh", label)
        self.assertIn("GHSA-cp6q-959q-f8rh", keys)

    def test_npm_via_strings_are_not_advisories(self):
        """A bare string in `via` is a transitive edge; counting it inflates every diff."""
        report = {"vulnerabilities": {"@tiptap/extension-bold": {
            "name": "@tiptap/extension-bold", "severity": "moderate",
            "via": ["@tiptap/core"],
        }}}
        self.assertEqual(gate.npm_advisories(report), {})

    def test_empty_report_yields_nothing(self):
        self.assertEqual(gate.pip_advisories({}), {})
        self.assertEqual(gate.npm_advisories({}), {})


class DiffTests(unittest.TestCase):
    def test_identical_reports_yield_no_new(self):
        base = head = gate.pip_advisories(pip_report(("a", "1.0", "CVE-1", [])))
        self.assertEqual(gate.new_advisories(base, head), [])

    def test_advisory_only_in_head_is_new(self):
        base = gate.pip_advisories(pip_report(("a", "1.0", "CVE-1", [])))
        head = gate.pip_advisories(
            pip_report(("a", "1.0", "CVE-1", []), ("b", "2.0", "CVE-2", []))
        )
        added = gate.new_advisories(base, head)
        self.assertEqual(len(added), 1)
        self.assertIn("CVE-2", added[0])

    def test_advisory_only_in_base_is_not_reported(self):
        """A PR that CLOSES an advisory must pass, not trip the gate."""
        base = gate.pip_advisories(
            pip_report(("a", "1.0", "CVE-1", []), ("b", "2.0", "CVE-2", []))
        )
        head = gate.pip_advisories(pip_report(("a", "1.0", "CVE-1", [])))
        self.assertEqual(gate.new_advisories(base, head), [])

    def test_alias_rename_is_not_new(self):
        """Base names it CVE-X; head names it PYSEC-Y aliasing CVE-X. One advisory."""
        base = gate.pip_advisories(pip_report(("a", "1.0", "CVE-2026-42304", [])))
        head = gate.pip_advisories(
            pip_report(("a", "1.0", "PYSEC-2026-160", ["CVE-2026-42304"]))
        )
        self.assertEqual(gate.new_advisories(base, head), [])

    def test_genuinely_unrelated_advisory_survives_alias_matching(self):
        base = gate.pip_advisories(pip_report(("a", "1.0", "CVE-1", ["GHSA-aaa"])))
        head = gate.pip_advisories(
            pip_report(("a", "1.0", "CVE-1", ["GHSA-aaa"]), ("b", "2.0", "CVE-9", ["GHSA-zzz"]))
        )
        self.assertEqual(len(gate.new_advisories(base, head)), 1)


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def _write(self, name, data):
        path = self.tmp / name
        path.write_text(json.dumps(data))
        return str(path)

    def test_no_pairs_given_is_a_pass(self):
        """A docs-only PR touches no manifest; the gate must still report and pass."""
        self.assertEqual(gate.main([]), 0)

    def test_clean_diff_exits_zero(self):
        same = pip_report(("a", "1.0", "CVE-1", []))
        rc = gate.main([
            "--base-pip", self._write("b.json", same),
            "--head-pip", self._write("h.json", same),
        ])
        self.assertEqual(rc, 0)

    def test_new_advisory_exits_one(self):
        rc = gate.main([
            "--base-pip", self._write("b.json", pip_report(("a", "1.0", "CVE-1", []))),
            "--head-pip", self._write("h.json", pip_report(
                ("a", "1.0", "CVE-1", []), ("b", "2.0", "CVE-2", []))),
        ])
        self.assertEqual(rc, 1)

    def test_warn_only_exits_zero_on_new_advisory(self):
        """Dependabot's path: report it, do not block the PR that closes advisories."""
        rc = gate.main([
            "--base-pip", self._write("b.json", pip_report(("a", "1.0", "CVE-1", []))),
            "--head-pip", self._write("h.json", pip_report(
                ("a", "1.0", "CVE-1", []), ("b", "2.0", "CVE-2", []))),
            "--warn-only",
        ])
        self.assertEqual(rc, 0)

    def test_missing_report_fails_rather_than_passing(self):
        """The base tree may not have been fetched. That must be loud."""
        rc = gate.main([
            "--base-pip", str(self.tmp / "does-not-exist.json"),
            "--head-pip", self._write("h.json", pip_report()),
        ])
        self.assertEqual(rc, 1)

    def test_half_a_pair_fails(self):
        """Only one side wired up would otherwise pass unconditionally."""
        rc = gate.main(["--head-pip", self._write("h.json", pip_report())])
        self.assertEqual(rc, 1)

    def test_malformed_json_fails(self):
        bad = self.tmp / "bad.json"
        bad.write_text("{not json")
        rc = gate.main(["--base-pip", str(bad), "--head-pip", str(bad)])
        self.assertEqual(rc, 1)

    def test_npm_pair_is_compared(self):
        rc = gate.main([
            "--base-npm", self._write("bn.json", npm_report()),
            "--head-npm", self._write("hn.json", npm_report(
                ("dompurify", "GHSA-xxxx-yyyy-zzzz", "high"))),
        ])
        self.assertEqual(rc, 1)

    def test_both_ecosystems_together(self):
        same_pip = pip_report(("a", "1.0", "CVE-1", []))
        same_npm = npm_report(("x", "GHSA-aaaa-bbbb-cccc", "low"))
        rc = gate.main([
            "--base-pip", self._write("b.json", same_pip),
            "--head-pip", self._write("h.json", same_pip),
            "--base-npm", self._write("bn.json", same_npm),
            "--head-npm", self._write("hn.json", same_npm),
        ])
        self.assertEqual(rc, 0)


class RealReportShapeTests(unittest.TestCase):
    """Guard the assumptions taken from a real `npm audit --json` run (2026-09-05)."""

    def test_real_npm_shape_parses(self):
        real = {
            "auditReportVersion": 2,
            "vulnerabilities": {
                "@tiptap/core": {
                    "name": "@tiptap/core",
                    "severity": "moderate",
                    "isDirect": False,
                    "via": [{
                        "source": 1158508,
                        "name": "@tiptap/core",
                        "dependency": "@tiptap/core",
                        "title": "Tiptap: mergeAttributes() turns an own __proto__ key ...",
                        "url": "https://github.com/advisories/GHSA-cp6q-959q-f8rh",
                        "severity": "moderate",
                        "range": ">=2.0.0-alpha.0 <3.30.4",
                    }],
                    "effects": ["@tiptap/extension-bold"],
                },
                "@tiptap/extension-bold": {
                    "name": "@tiptap/extension-bold",
                    "severity": "moderate",
                    "via": ["@tiptap/core"],
                },
            },
            "metadata": {},
        }
        got = gate.npm_advisories(real)
        self.assertEqual(len(got), 1, "the `via: [string]` entry must not count")
        self.assertIn("GHSA-cp6q-959q-f8rh", next(iter(got)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
