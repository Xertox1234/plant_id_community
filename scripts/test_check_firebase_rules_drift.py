#!/usr/bin/env python3
"""Tests for scripts/check_firebase_rules_drift.py.

Run: python3 scripts/test_check_firebase_rules_drift.py
Also run by .github/workflows/harness-ci.yml (a required status check).

The point of this check is to notice a rules file that was committed and never
deployed, so the cases worth testing are the ways it could report "clean" while
blind — the shape that let the 2026-05-23 Storage tightening sit undeployed for
3.5 months and that todo 224 hit before it:

  - a release the mapping does not recognise must FAIL, never be skipped
    (adding a bucket or a second database must not quietly leave coverage)
  - a ruleset carrying more than one source file must be INDETERMINATE, because
    comparing files[0] is the same silent gap in a different costume
  - no credentials / HTTP error / empty release list must be INDETERMINATE (2),
    which is NOT exit 0 — a check that cannot look has not looked
  - the direction annotation must name prod-behind-repo specifically, since only
    that direction is the incident; repo-behind-prod is an unmerged deploy

No network: every test drives a fake AuthorizedSession.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import check_firebase_rules_drift as drift  # noqa: E402

FIRESTORE_SRC = "rules_version = '2';\nservice cloud.firestore {\n}\n"
STORAGE_SRC = "rules_version = '2';\nservice firebase.storage {\n}\n"

STORAGE_RELEASE = "firebase.storage/demo.firebasestorage.app"


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload) if isinstance(payload, dict) else str(payload)

    def json(self):
        if not isinstance(self._payload, dict):
            raise ValueError("not JSON")
        return self._payload


class FakeSession:
    """Serves a releases list and a ruleset body per release, nothing else."""

    def __init__(self, releases, rulesets, status_code=200):
        self.releases = releases
        self.rulesets = rulesets
        self.status_code = status_code
        self.urls: list[str] = []

    def get(self, url, timeout=None):
        self.urls.append(url)
        if self.status_code != 200:
            return FakeResponse({"error": "boom"}, self.status_code)
        if url.endswith("/releases"):
            return FakeResponse({"releases": self.releases})
        name = url.split("/v1/", 1)[1]
        return FakeResponse(self.rulesets[name])


def ruleset(*contents):
    return {"source": {"files": [{"name": "f", "content": c} for c in contents]}}


def release(short, ruleset_id, update_time="2026-09-12T14:03:15Z"):
    return {
        "name": f"projects/demo/releases/{short}",
        "rulesetName": f"projects/demo/rulesets/{ruleset_id}",
        "updateTime": update_time,
    }


class DriftTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "firebase.json").write_text(
            json.dumps(
                {
                    "firestore": {"rules": "firebase/firestore.rules"},
                    "storage": {"rules": "firebase/storage.rules"},
                }
            )
        )
        (self.root / ".firebaserc").write_text(json.dumps({"projects": {"default": "demo"}}))
        (self.root / "firebase").mkdir()
        (self.root / "firebase/firestore.rules").write_text(FIRESTORE_SRC)
        (self.root / "firebase/storage.rules").write_text(STORAGE_SRC)

    def both_in_sync(self):
        return FakeSession(
            [release("cloud.firestore", "r1"), release(STORAGE_RELEASE, "r2")],
            {
                "projects/demo/rulesets/r1": ruleset(FIRESTORE_SRC),
                "projects/demo/rulesets/r2": ruleset(STORAGE_SRC),
            },
        )

    def run_check(self, session):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                code = drift.run(self.root, session, quiet=False)
            except drift.Indeterminate as exc:
                return drift.EXIT_INDETERMINATE, f"{out.getvalue()}\nINDETERMINATE: {exc}"
        return code, out.getvalue()


class MatchTests(DriftTestCase):
    def test_identical_sources_match(self):
        code, output = self.run_check(self.both_in_sync())
        self.assertEqual(code, drift.EXIT_MATCH)
        self.assertIn("MATCH  cloud.firestore", output)
        self.assertIn("All 2 release(s) match", output)

    def test_trailing_whitespace_difference_is_drift(self):
        # Byte comparison on purpose: the deploy sends the file verbatim, so any
        # difference means the deployed ruleset is not the reviewed one.
        (self.root / "firebase/storage.rules").write_text(STORAGE_SRC + "\n")
        code, _ = self.run_check(self.both_in_sync())
        self.assertEqual(code, drift.EXIT_DRIFT)


class DriftDetectionTests(DriftTestCase):
    def test_loosened_deployed_rule_is_reported(self):
        session = self.both_in_sync()
        session.rulesets["projects/demo/rulesets/r2"] = ruleset(
            STORAGE_SRC.replace("firebase.storage", "firebase.storage // OLD")
        )
        code, output = self.run_check(session)
        self.assertEqual(code, drift.EXIT_DRIFT)
        self.assertIn("DRIFT DETECTED", output)
        self.assertIn("DEPLOYED:" + STORAGE_RELEASE, output)
        self.assertIn("COMMITTED:firebase/storage.rules", output)

    def test_unmapped_release_fails_instead_of_being_skipped(self):
        # A second bucket nobody added to the mapping. The dangerous outcome is a
        # green run that silently covers one release out of two.
        session = self.both_in_sync()
        session.releases.append(release("firebase.mystery/other.app", "r3"))
        session.rulesets["projects/demo/rulesets/r3"] = ruleset(STORAGE_SRC)
        code, output = self.run_check(session)
        self.assertEqual(code, drift.EXIT_DRIFT)
        self.assertIn("maps to no firebase.json product", output)

    def test_release_live_without_a_configured_rules_file_fails(self):
        (self.root / "firebase.json").write_text(
            json.dumps({"firestore": {"rules": "firebase/firestore.rules"}})
        )
        code, output = self.run_check(self.both_in_sync())
        self.assertEqual(code, drift.EXIT_DRIFT)
        self.assertIn("configures no storage rules file", output)


class IndeterminateTests(DriftTestCase):
    def test_multi_file_ruleset_is_indeterminate_not_a_match(self):
        session = self.both_in_sync()
        session.rulesets["projects/demo/rulesets/r2"] = ruleset(STORAGE_SRC, "extra")
        code, output = self.run_check(session)
        self.assertEqual(code, drift.EXIT_INDETERMINATE)
        self.assertIn("2 source files", output)

    def test_http_error_is_indeterminate(self):
        code, output = self.run_check(FakeSession([], {}, status_code=503))
        self.assertEqual(code, drift.EXIT_INDETERMINATE)
        self.assertIn("HTTP 503", output)

    def test_empty_release_list_is_indeterminate(self):
        code, output = self.run_check(FakeSession([], {}))
        self.assertEqual(code, drift.EXIT_INDETERMINATE)
        self.assertIn("no rules releases", output)

    def test_missing_firebaserc_is_indeterminate(self):
        (self.root / ".firebaserc").unlink()
        code, _ = self.run_check(self.both_in_sync())
        self.assertEqual(code, drift.EXIT_INDETERMINATE)

    def test_firebase_json_pointing_at_a_missing_file_is_indeterminate(self):
        (self.root / "firebase/storage.rules").unlink()
        code, _ = self.run_check(self.both_in_sync())
        self.assertEqual(code, drift.EXIT_INDETERMINATE)

    def test_missing_credentials_file_is_indeterminate(self):
        with self.assertRaises(drift.Indeterminate):
            drift.build_session("/definitely/not/here.json")


class DirectionTests(unittest.TestCase):
    """Only prod-behind-repo is the incident; the message must say which it is."""

    def test_committed_newer_than_deploy_names_the_incident_shape(self):
        text = drift.describe_direction(
            drift.parse_time("2025-11-14T00:00:00Z"), drift.parse_time("2026-05-23T00:00:00Z")
        )
        self.assertIn("PRODUCTION IS BEHIND THE REPO", text)

    def test_deploy_newer_than_commit_is_not_the_incident_shape(self):
        text = drift.describe_direction(
            drift.parse_time("2026-09-12T00:00:00Z"), drift.parse_time("2026-06-05T00:00:00Z")
        )
        self.assertNotIn("PRODUCTION IS BEHIND", text)
        self.assertIn("repo is behind production", text)

    def test_unreadable_timestamp_does_not_assert_a_direction(self):
        text = drift.describe_direction(drift.parse_time("not-a-date"), None)
        self.assertIn("direction unknown", text)

    def test_uncommitted_edit_is_not_reported_as_a_stale_repo(self):
        """Regression: the exact timestamps that produced a backwards hint.

        The deployed release (2026-09-12) really is newer than the last commit
        touching storage.rules (2026-06-05), but the working tree held the
        uncommitted helper deletion — so the repo was AHEAD, not behind. The
        old message told the reader prod was ahead, whose remedy (copy prod
        over the repo) would have destroyed the edit.
        """
        text = drift.describe_direction(
            drift.parse_time("2026-09-12T14:03:15Z"),
            drift.parse_time("2026-06-05T00:00:00Z"),
            dirty=True,
        )
        self.assertIn("PRODUCTION IS BEHIND THE WORKING TREE", text)
        self.assertNotIn("repo is behind production", text)
        self.assertIn("do NOT resolve", text)

    def test_clean_tree_still_uses_the_timestamp_comparison(self):
        text = drift.describe_direction(
            drift.parse_time("2026-09-12T00:00:00Z"),
            drift.parse_time("2026-06-05T00:00:00Z"),
            dirty=False,
        )
        self.assertIn("repo is behind production", text)


class UncommittedChangeTests(unittest.TestCase):
    """has_uncommitted_changes() must read the working tree, not the log."""

    def _repo(self, tmp: str) -> pathlib.Path:
        root = pathlib.Path(tmp)
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
        run = lambda *a: subprocess.run(a, cwd=root, check=True,
                                        capture_output=True, env={**os.environ, **env})
        run("git", "init", "-q")
        (root / "firebase").mkdir()
        (root / "firebase" / "storage.rules").write_text("rules_version = '2';\n")
        run("git", "add", "-A")
        run("git", "commit", "-qm", "seed")
        return root

    def test_clean_file_reports_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            self.assertFalse(
                drift.has_uncommitted_changes(root, root / "firebase" / "storage.rules")
            )

    def test_edited_file_reports_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            target = root / "firebase" / "storage.rules"
            target.write_text("rules_version = '2';\n// edited\n")
            self.assertTrue(drift.has_uncommitted_changes(root, target))

    def test_non_git_directory_degrades_to_false_rather_than_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "f.rules").write_text("x")
            self.assertFalse(drift.has_uncommitted_changes(root, root / "f.rules"))


class MainExitTests(unittest.TestCase):
    """main() must translate Indeterminate into exit 2, not swallow it into 0.

    Added after a mutation (`return EXIT_INDETERMINATE` -> `return EXIT_MATCH` in
    main's handler) survived the whole suite: every other test calls run() directly,
    so nothing exercised the one place that decides the process exit code.
    """

    def test_bad_credentials_exit_code_is_two(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = drift.main(["--credentials", "/definitely/not/here.json"])
        self.assertEqual(code, drift.EXIT_INDETERMINATE)
        self.assertIn("INDETERMINATE", err.getvalue())
        self.assertIn("NOT a pass", err.getvalue())


class ClassifyTests(unittest.TestCase):
    def test_bare_and_bucket_qualified_names_both_classify(self):
        self.assertEqual(drift.classify("cloud.firestore"), "firestore")
        self.assertEqual(drift.classify(STORAGE_RELEASE), "storage")

    def test_prefix_match_is_anchored_on_a_segment_boundary(self):
        # 'firebase.storagex' must not classify as storage.
        self.assertIsNone(drift.classify("firebase.storagex/bucket"))
        self.assertIsNone(drift.classify("cloud.firestore.beta"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
