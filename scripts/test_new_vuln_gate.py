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
  - a ROOT-only lockfile change must scope to the root tree, never to web/
    (the gate audited web/ against web/ and printed a confident `0 new` — todo 356)
  - each npm manifest is compared against ITS OWN base, so an advisory sitting
    in web/'s base cannot cancel the same advisory arriving in the root tree
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import subprocess
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
            "--npm-pair", "web",
            self._write("bn.json", npm_report()),
            self._write("hn.json", npm_report(
                ("dompurify", "GHSA-xxxx-yyyy-zzzz", "high"))),
        ])
        self.assertEqual(rc, 1)

    def test_both_ecosystems_together(self):
        same_pip = pip_report(("a", "1.0", "CVE-1", []))
        same_npm = npm_report(("x", "GHSA-aaaa-bbbb-cccc", "low"))
        rc = gate.main([
            "--base-pip", self._write("b.json", same_pip),
            "--head-pip", self._write("h.json", same_pip),
            "--npm-pair", "web",
            self._write("bn.json", same_npm),
            self._write("hn.json", same_npm),
        ])
        self.assertEqual(rc, 0)


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class ScopeTests(unittest.TestCase):
    """Which trees a diff sends the gate to.

    This is where the todo-356 bug lived. The old predicate was a path regex in
    security-scan.yml's bash (`(^|/)package-lock\\.json$`); it correctly said
    "npm=true" for a root lockfile change and the audit step then read `web/`
    regardless, so the gate reported `0 advisories on base, 0 on head, 0 new`
    about a tree the PR had never touched.
    """

    def test_root_only_lockfile_change_scopes_to_root(self):
        """PR #669's diff verbatim — the specimen that exposed the false green."""
        dirs = gate.npm_dirs_from_changes([
            "package-lock.json",
            "package.json",
            "todos/356-pending-p2-security-scan-root-manifest-blind.md",
        ])
        self.assertEqual(dirs, ["."])
        self.assertNotIn("web", dirs)

    def test_web_only_change_scopes_to_web(self):
        self.assertEqual(gate.npm_dirs_from_changes(["web/package-lock.json"]), ["web"])

    def test_both_manifests_change_scopes_to_both(self):
        self.assertEqual(
            gate.npm_dirs_from_changes(["package-lock.json", "web/package.json"]),
            [".", "web"],
        )

    def test_unrelated_change_scopes_to_nothing(self):
        self.assertEqual(gate.npm_dirs_from_changes(["docs/rules/security.md"]), [])

    def test_manifest_without_a_lockfile_is_not_scoped_in(self):
        """design_reference/package.json has no lockfile, so it cannot be audited.

        A `(^|/)package\\.json$` regex would scope it in and then crash the audit
        step on the missing lockfile.
        """
        self.assertEqual(gate.npm_dirs_from_changes(["design_reference/package.json"]), [])

    def test_pip_predicate(self):
        self.assertTrue(gate.pip_changed(["backend/requirements.txt"]))
        self.assertTrue(gate.pip_changed(["backend/requirements-dev.txt"]))
        self.assertFalse(gate.pip_changed(["web/package.json"]))
        self.assertFalse(gate.pip_changed([]))


class ManifestDriftTests(unittest.TestCase):
    """The constant must keep describing the repo, or a manifest goes unscanned."""

    def _tracked(self, *patterns):
        out = subprocess.run(
            ["git", "ls-files", "-z", *patterns],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout
        return [p for p in out.split("\0") if p]

    def test_constant_covers_every_tracked_lockfile(self):
        """A third package-lock.json must not be able to appear unnoticed.

        `git ls-files` rather than a glob: rglob would walk web/node_modules and
        backend/venv.
        """
        found = {
            str(pathlib.PurePosixPath(path).parent)
            for path in self._tracked("package-lock.json", "*/package-lock.json")
        }
        self.assertEqual(
            found,
            set(gate.NPM_MANIFEST_DIRS),
            "a tracked package-lock.json is missing from NPM_MANIFEST_DIRS (or vice "
            "versa) — every scanner that loops over that constant is now blind to it",
        )

    def test_requirements_dev_carries_no_pins(self):
        """`pip_changed` is broader than the file the audit reads; this is why that is safe.

        backend/requirements-dev.txt is a pinless `-r requirements.txt` overlay,
        so a dev-only change has the same answer as requirements.txt by
        construction. The day it gains a pin of its own, that stops being true
        and the gate would report on the wrong tree — the todo-356 shape.
        """
        lines = [
            line.strip()
            for line in (REPO_ROOT / "backend" / "requirements-dev.txt").read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertEqual(
            lines,
            ["-r requirements.txt"],
            "requirements-dev.txt is no longer a pure overlay — either audit it "
            "directly in new-vuln-gate or narrow pip_changed()",
        )


class MultiManifestCompareTests(unittest.TestCase):
    """Each manifest against its own base. Merging the reports hides real advisories."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def _write(self, name, data):
        path = self.tmp / name
        path.write_text(json.dumps(data))
        return str(path)

    def _run(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = gate.main(argv)
        return rc, buf.getvalue()

    def test_root_advisory_is_reported_and_named(self):
        clean = npm_report()
        dirty = npm_report(("undici", "GHSA-root-aaaa-bbbb", "high"))
        same_web = npm_report(("vite", "GHSA-webw-cccc-dddd", "moderate"))
        rc, out = self._run([
            "--npm-pair", ".", self._write("br.json", clean), self._write("hr.json", dirty),
            "--npm-pair", "web", self._write("bw.json", same_web), self._write("hw.json", same_web),
        ])
        self.assertEqual(rc, 1)
        self.assertIn("npm audit (.): 0 advisories on base, 1 on head, 1 new", out)
        self.assertIn("npm audit (web): 1 advisories on base, 1 on head, 0 new", out)
        self.assertIn(".: GHSA-root-aaaa-bbbb", out)

    def test_an_advisory_in_webs_base_cannot_cancel_it_in_root(self):
        """The merge-all-reports failure mode: one id, two trees, opposite meanings."""
        shared = "GHSA-shar-eeee-ffff"
        rc, out = self._run([
            "--npm-pair", ".",
            self._write("br.json", npm_report()),
            self._write("hr.json", npm_report(("undici", shared, "high"))),
            "--npm-pair", "web",
            self._write("bw.json", npm_report(("undici", shared, "high"))),
            self._write("hw.json", npm_report(("undici", shared, "high"))),
        ])
        self.assertEqual(rc, 1, "web/'s pre-existing copy must not cancel root's new one")
        self.assertIn(f".: {shared}", out)

    def test_a_scoped_manifest_with_no_report_fails(self):
        """If the audit loop skipped a dir the compare loop names, that must be loud."""
        rc, _ = self._run([
            "--npm-pair", ".", str(self.tmp / "never-written.json"),
            self._write("hr.json", npm_report()),
        ])
        self.assertEqual(rc, 1)

    def test_no_pairs_reports_skipped_not_zero_new(self):
        """A docs-only PR must say `skipped`, never a confident `0 new`."""
        rc, out = self._run([])
        self.assertEqual(rc, 0)
        self.assertIn("npm audit: skipped (no manifest change in this PR)", out)

    def test_clean_pair_on_every_manifest_passes(self):
        same = npm_report(("x", "GHSA-aaaa-bbbb-cccc", "low"))
        rc, out = self._run([
            "--npm-pair", ".", self._write("br.json", same), self._write("hr.json", same),
            "--npm-pair", "web", self._write("bw.json", same), self._write("hw.json", same),
        ])
        self.assertEqual(rc, 0)
        self.assertIn("No new dependency advisories", out)


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
