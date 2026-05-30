#!/usr/bin/env python3
"""Tests for capture_from_review — turns review findings into candidate triggers.

Run: python3 scripts/inject/test_capture_from_review.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import capture_from_review as cfr  # noqa: E402
import capture_trigger as ct  # noqa: E402

SCRIPT = os.path.join(HERE, "capture_from_review.py")


def tmp_index():
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as fh:
        fh.write("[]")
    return path


def sig(**kw):
    base = {
        "id": "drf-action-no-ratelimit",
        "path_glob": ["backend/**/*_views.py"],
        "content_present": r"@action\b",
        "message": "New @action without a ratelimit",
    }
    base.update(kw)
    return base


def finding(**kw):
    f = {"severity": "high", "file": "backend/apps/forum_integration/api_views.py",
         "line": 12, "description": "endpoint missing ratelimit"}
    f.update(kw)
    return f


class TestProcess(unittest.TestCase):
    def test_captures_candidate_from_signature(self):
        path = tmp_index()
        try:
            res = cfr.process([finding(trigger_signature=sig())], path)
            self.assertEqual(res["captured"], ["drf-action-no-ratelimit"])
            data = ct.load(path)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["severity"], "candidate")
            self.assertTrue(data[0]["source"].startswith("review"))
        finally:
            os.remove(path)

    def test_finding_without_signature_ignored(self):
        path = tmp_index()
        try:
            res = cfr.process([finding()], path)
            self.assertEqual(res["captured"], [])
            self.assertEqual(ct.load(path), [])
        finally:
            os.remove(path)

    def test_signature_without_content_present_skipped(self):
        path = tmp_index()
        try:
            s = sig()
            del s["content_present"]
            res = cfr.process([finding(trigger_signature=s)], path)
            self.assertEqual(res["captured"], [])
            self.assertEqual(len(res["skipped"]), 1)
            self.assertEqual(ct.load(path), [])
        finally:
            os.remove(path)

    def test_bad_regex_is_error_not_captured(self):
        path = tmp_index()
        try:
            res = cfr.process([finding(trigger_signature=sig(content_present="(unclosed"))], path)
            self.assertEqual(res["captured"], [])
            self.assertEqual(len(res["errors"]), 1)
            self.assertEqual(ct.load(path), [])
        finally:
            os.remove(path)

    def test_duplicate_id_dedups(self):
        path = tmp_index()
        try:
            res = cfr.process(
                [finding(trigger_signature=sig()), finding(trigger_signature=sig())], path
            )
            self.assertEqual(res["captured"], ["drf-action-no-ratelimit"])
            self.assertEqual(res["exists"], ["drf-action-no-ratelimit"])
            self.assertEqual(len(ct.load(path)), 1)
        finally:
            os.remove(path)

    def test_idempotent_second_run(self):
        path = tmp_index()
        try:
            cfr.process([finding(trigger_signature=sig())], path)
            res = cfr.process([finding(trigger_signature=sig())], path)
            self.assertEqual(res["captured"], [])
            self.assertEqual(res["exists"], ["drf-action-no-ratelimit"])
        finally:
            os.remove(path)

    def test_message_falls_back_to_description(self):
        path = tmp_index()
        try:
            s = sig()
            del s["message"]
            cfr.process([finding(description="my desc", trigger_signature=s)], path)
            self.assertEqual(ct.load(path)[0]["message"], "my desc")
        finally:
            os.remove(path)

    def test_capture_io_failure_is_recorded_not_raised(self):
        # triggers_path pointing at a directory makes ct.capture's write fail;
        # the helper must record an error and keep going, never crash the review.
        d = tempfile.mkdtemp()
        try:
            res = cfr.process([finding(trigger_signature=sig())], d)
            self.assertEqual(res["captured"], [])
            self.assertEqual(len(res["errors"]), 1)
        finally:
            os.rmdir(d)

    def test_empty_id_recorded_as_error(self):
        path = tmp_index()
        try:
            res = cfr.process([finding(trigger_signature=sig(id=""))], path)
            self.assertEqual(res["captured"], [])
            self.assertEqual(len(res["errors"]), 1)
            self.assertEqual(ct.load(path), [])
        finally:
            os.remove(path)

    def test_source_includes_batch_label(self):
        path = tmp_index()
        try:
            cfr.process(
                [finding(batch_label="incremental-abc123 (django-drf-reviewer)",
                         trigger_signature=sig())],
                path,
            )
            self.assertIn("abc123", ct.load(path)[0]["source"])
        finally:
            os.remove(path)


class TestExtractFindings(unittest.TestCase):
    def test_plain_list_of_findings(self):
        out = cfr.extract_findings([finding(trigger_signature=sig())])
        self.assertEqual(len(out), 1)

    def test_reviewer_result_objects_flattened(self):
        data = [
            {"agent": "django-drf-reviewer", "batch_label": "b1",
             "findings": [finding(trigger_signature=sig())]},
            {"agent": "security-reviewer", "batch_label": "b2", "findings": []},
        ]
        out = cfr.extract_findings(data)
        self.assertEqual(len(out), 1)
        # batch_label propagated onto the finding for source attribution
        self.assertEqual(out[0].get("batch_label"), "b1")

    def test_dict_with_findings(self):
        out = cfr.extract_findings({"findings": [finding(trigger_signature=sig())]})
        self.assertEqual(len(out), 1)


class TestCLI(unittest.TestCase):
    def test_stdin_pipe_captures(self):
        path = tmp_index()
        try:
            env = dict(os.environ)
            env["INJECT_TRIGGERS_FILE"] = path
            payload = json.dumps([finding(trigger_signature=sig())])
            p = subprocess.run([sys.executable, SCRIPT], input=payload,
                               capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(len(ct.load(path)), 1)
            self.assertIn("captured", p.stdout.lower())
        finally:
            os.remove(path)

    def test_malformed_stdin_is_nonfatal(self):
        path = tmp_index()
        try:
            env = dict(os.environ)
            env["INJECT_TRIGGERS_FILE"] = path
            p = subprocess.run([sys.executable, SCRIPT], input="not json",
                               capture_output=True, text=True, env=env)
            # Non-fatal: exits 0, index untouched
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(ct.load(path), [])
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
