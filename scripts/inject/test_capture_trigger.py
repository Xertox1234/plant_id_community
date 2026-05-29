#!/usr/bin/env python3
"""Tests for capture_trigger — appends a trigger to docs/rules/triggers.json.

Run: python3 scripts/inject/test_capture_trigger.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import capture_trigger as ct  # noqa: E402
import match_triggers as mt  # noqa: E402

SCRIPT = os.path.join(HERE, "capture_trigger.py")


def tmp_index(entries):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as fh:
        json.dump(entries, fh)
    return path


class TestBuildTrigger(unittest.TestCase):
    def test_minimal_valid(self):
        t = ct.build_trigger(
            id="x-y", message="do the thing", path_glob=["backend/**/x.py"]
        )
        self.assertEqual(t["id"], "x-y")
        self.assertEqual(t["severity"], "candidate")  # default
        self.assertEqual(t["path_glob"], ["backend/**/x.py"])

    def test_canonical_key_order_and_omits_empty(self):
        t = ct.build_trigger(
            id="a", message="m", path_glob=["p"], domains=["api"], severity="warn"
        )
        keys = list(t.keys())
        # canonical order, and no None-valued optionals present
        self.assertEqual(keys[0], "id")
        self.assertIn("severity", keys)
        self.assertNotIn("content_present", keys)  # omitted, not None
        self.assertNotIn("pattern_ref", keys)

    def test_missing_message_rejected(self):
        with self.assertRaises(ValueError):
            ct.build_trigger(id="a", message="", path_glob=["p"])

    def test_missing_path_glob_rejected(self):
        with self.assertRaises(ValueError):
            ct.build_trigger(id="a", message="m", path_glob=[])

    def test_invalid_regex_rejected(self):
        with self.assertRaises(ValueError):
            ct.build_trigger(id="a", message="m", path_glob=["p"], content_present="(unclosed")


class TestCapture(unittest.TestCase):
    def test_appends_new(self):
        path = tmp_index([])
        try:
            status = ct.capture(path, ct.build_trigger(id="new", message="m", path_glob=["p"]))
            self.assertEqual(status, "added")
            data = ct.load(path)
            self.assertEqual([t["id"] for t in data], ["new"])
        finally:
            os.remove(path)

    def test_dedup_skips_existing(self):
        path = tmp_index([])
        try:
            t = ct.build_trigger(id="dup", message="m", path_glob=["p"])
            self.assertEqual(ct.capture(path, t), "added")
            self.assertEqual(ct.capture(path, t), "exists")
            self.assertEqual(len(ct.load(path)), 1)
        finally:
            os.remove(path)

    def test_update_overwrites(self):
        path = tmp_index([])
        try:
            ct.capture(path, ct.build_trigger(id="u", message="old", path_glob=["p"]))
            ct.capture(path, ct.build_trigger(id="u", message="new", path_glob=["p"]), update=True)
            data = ct.load(path)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["message"], "new")
        finally:
            os.remove(path)

    def test_captured_trigger_then_matches(self):
        """End-to-end: a captured trigger actually fires in the matcher."""
        path = tmp_index([])
        try:
            ct.capture(path, ct.build_trigger(
                id="no-print", message="no bare print()", path_glob=["backend/**/*.py"],
                content_present=r"^\s*print\(", severity="warn",
            ))
            idx = ct.load(path)
            hits = mt.find_matches(
                "Write",
                {"file_path": "backend/apps/x/util.py", "content": "    print('hi')\n"},
                idx, None,
            )
            self.assertIn("no-print", [h["id"] for h in hits])
        finally:
            os.remove(path)


class TestResolvePatternRef(unittest.TestCase):
    def test_existing_ref_kept(self):
        root = os.path.dirname(os.path.dirname(HERE))  # repo root
        ref = "backend/docs/patterns/architecture/rate-limiting.md"
        kept, warn = ct.resolve_pattern_ref(ref, root)
        self.assertEqual(kept, ref)
        self.assertIsNone(warn)

    def test_missing_ref_dropped_with_warning(self):
        root = os.path.dirname(os.path.dirname(HERE))
        kept, warn = ct.resolve_pattern_ref("backend/docs/patterns/nope.md", root)
        self.assertIsNone(kept)
        self.assertIsNotNone(warn)


class TestCLI(unittest.TestCase):
    def _run(self, args, triggers_file):
        env = dict(os.environ)
        env["INJECT_TRIGGERS_FILE"] = triggers_file
        return subprocess.run(
            [sys.executable, SCRIPT] + args, capture_output=True, text=True, env=env
        )

    def test_cli_adds_then_dedups(self):
        path = tmp_index([])
        try:
            args = [
                "--id", "cli-x", "--message", "msg", "--path-glob", "backend/**/x.py",
                "--domains", "api", "--severity", "warn", "--added", "2026-05-29",
            ]
            p1 = self._run(args, path)
            self.assertEqual(p1.returncode, 0, p1.stderr)
            self.assertEqual([t["id"] for t in ct.load(path)], ["cli-x"])
            # second run: still one entry (dedup)
            p2 = self._run(args, path)
            self.assertEqual(p2.returncode, 0, p2.stderr)
            self.assertEqual(len(ct.load(path)), 1)
        finally:
            os.remove(path)

    def test_cli_missing_required_fails(self):
        path = tmp_index([])
        try:
            p = self._run(["--id", "no-msg", "--path-glob", "p"], path)
            self.assertNotEqual(p.returncode, 0)
        finally:
            os.remove(path)

    def test_cli_invalid_regex_returns_2_and_leaves_index_unchanged(self):
        # Guards the build_trigger ValueError -> main returns 2 propagation, so a
        # later refactor can't silently swallow the error and exit 0.
        path = tmp_index([])
        try:
            p = self._run(
                ["--id", "bad", "--message", "m", "--path-glob", "p",
                 "--content-present", "(unclosed"],
                path,
            )
            self.assertEqual(p.returncode, 2)
            self.assertEqual(ct.load(path), [])
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
