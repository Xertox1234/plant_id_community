#!/usr/bin/env python3
"""Tests for route_domains — the shared path→docs/rules domain matcher.

Run: python3 scripts/inject/test_route_domains.py

_domains_for() is tested directly with an inline rules fixture (so the tests pin
the ordered/additive/fallback semantics independent of routing.json's contents).
Two subprocess tests drive the real script end-to-end: one against the real
routing.json (the firebase ordered-stacking regression), one proving fail-open
when routing.json is unreadable.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_domains as rd  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "route_domains.py")

# Inline fixture mirroring the shape of routing.json (order is load-bearing).
RULES = [
    {"globs": ["backend/apps/blog/*"], "domains": ["wagtail", "api", "security"], "mode": "additive"},
    {"globs": ["*/migrations/*"], "domains": ["database", "security"], "mode": "additive"},
    {"globs": ["*/views.py"], "domains": ["api", "security"], "mode": "additive"},
    {"globs": ["backend/*.py"], "domains": ["api", "security", "database"], "mode": "fallback"},
    {"globs": ["firebase/*", "*firebase*"], "domains": ["firebase", "security"], "mode": "additive"},
    {"globs": ["*/tests/*", "*test_*.py"], "domains": ["testing"], "mode": "additive"},
    {"globs": ["*.ts", "*.tsx"], "domains": ["typescript"], "mode": "fallback"},
]


class DomainsForTests(unittest.TestCase):
    def test_additive_stacks_multiple_rules(self):
        # blog/views.py matches blog + views → union, deduped, order-preserving.
        self.assertEqual(
            rd._domains_for("backend/apps/blog/views.py", RULES),
            ["wagtail", "api", "security"],
        )

    def test_fallback_fires_only_when_empty(self):
        # A plain backend .py matching nothing earlier → fallback fires.
        self.assertEqual(
            rd._domains_for("backend/manage.py", RULES),
            ["api", "security", "database"],
        )

    def test_fallback_suppressed_by_earlier_match(self):
        # migrations matched first → backend/*.py fallback must NOT fire.
        self.assertEqual(
            rd._domains_for("backend/apps/x/migrations/0001.py", RULES),
            ["database", "security"],
        )

    def test_firebase_stacks_on_fallback_ordered(self):
        # THE crux: fallback fires (empty), THEN firebase additive stacks on top.
        # A "fallback only if nothing matched anywhere" model would drop database.
        self.assertEqual(
            rd._domains_for("backend/apps/garden/firebase_config.py", RULES),
            ["api", "security", "database", "firebase"],
        )

    def test_backend_test_file_stacks_testing_on_fallback(self):
        self.assertEqual(
            rd._domains_for("backend/x/tests/test_foo.py", RULES),
            ["api", "security", "database", "testing"],
        )

    def test_ts_fallback_only_when_otherwise_empty(self):
        self.assertEqual(rd._domains_for("scripts/foo.ts", RULES), ["typescript"])

    def test_no_match_returns_empty(self):
        self.assertEqual(rd._domains_for("README.md", RULES), [])


class SubprocessTests(unittest.TestCase):
    def _run(self, stdin, env=None):
        return subprocess.run(
            [sys.executable, SCRIPT],
            input=stdin,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_real_routing_firebase_regression(self):
        # End-to-end against the REAL docs/rules/routing.json.
        r = self._run("backend/apps/garden/firebase_config.py\n")
        self.assertEqual(r.returncode, 0)
        out = set(r.stdout.split(","))
        self.assertIn("database", out)  # fallback fired
        self.assertIn("firebase", out)  # stacked on top

    def test_union_across_multiple_paths(self):
        # kimi passes the whole staged list in one call; per-path then unioned.
        r = self._run("backend/apps/users/views.py\nweb/src/x.ts\n")
        self.assertEqual(r.returncode, 0)
        out = set(filter(None, r.stdout.split(",")))
        self.assertEqual(out, {"api", "security", "typescript"})

    def test_fail_open_on_unreadable_routing(self):
        # Point the module's resolver at a missing file via a temp HOME-less cwd:
        # simplest is to run a tiny inline script that monkeypatches ROUTING_JSON.
        code = (
            "import sys, pathlib; sys.path.insert(0, %r);"
            "import route_domains as rd;"
            "rd.ROUTING_JSON = pathlib.Path('/nonexistent/routing.json');"
            "sys.exit(rd.main())" % os.path.dirname(SCRIPT)
        )
        r = subprocess.run(
            [sys.executable, "-c", code],
            input="backend/apps/users/views.py\n",
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")  # fail-open: no domains, no error


if __name__ == "__main__":
    unittest.main()
