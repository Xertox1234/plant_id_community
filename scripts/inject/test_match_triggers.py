#!/usr/bin/env python3
"""Tests for match_triggers — the just-in-time mistake-injection matcher.

Run: python3 scripts/inject/test_match_triggers.py

Core logic is tested through find_matches() with disk content passed in
directly. One end-to-end test drives the script as a subprocess against a real
temp file + temp trigger index, exercising stdin parse, trigger load, disk read,
and formatting together.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match_triggers as mt  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "match_triggers.py")

# --- Fixture trigger set (independent of the real triggers.json) ---------------

RATELIMIT = {
    "id": "drf-action-no-ratelimit",
    "path_glob": ["backend/**/views.py", "backend/**/viewsets.py"],
    "content_present": r"@action\b",
    "content_absent": r"ratelimit|is_ratelimited|Ratelimited",
    "message": "New @action endpoint — confirm a rate limit applies.",
    "pattern_ref": "backend/docs/patterns/architecture/rate-limiting.md",
    "severity": "warn",
}

ROUTER = {
    "id": "react-router-import",
    "path_glob": ["web/**/*.tsx", "web/**/*.ts"],
    "content_present": r"from ['\"]react-router['\"]",
    "message": "Import router hooks from 'react-router-dom', not 'react-router'.",
    "severity": "warn",
}

TRIGGERS = [RATELIMIT, ROUTER]


def edit(file_path, old_string, new_string, **kw):
    ti = {"file_path": file_path, "old_string": old_string, "new_string": new_string}
    ti.update(kw)
    return "Edit", ti


def write(file_path, content):
    return "Write", {"file_path": file_path, "content": content}


def multiedit(file_path, edits):
    return "MultiEdit", {"file_path": file_path, "edits": edits}


def ids(hits):
    return [h["id"] for h in hits]


class TestPresenceOnFragment(unittest.TestCase):
    def test_action_without_ratelimit_fires(self):
        tn, ti = edit(
            "backend/apps/forum/views.py",
            "        return Response(data)",
            "        return Response(data)\n\n    @action(detail=True)\n"
            "    def extra(self, request, pk=None):\n        return Response({})",
        )
        disk = "class V(viewsets.ModelViewSet):\n        return Response(data)\n"
        hits = mt.find_matches(tn, ti, TRIGGERS, disk)
        self.assertIn("drf-action-no-ratelimit", ids(hits))

    def test_action_with_ratelimit_in_same_fragment_silent(self):
        tn, ti = edit(
            "backend/apps/forum/views.py",
            "    pass",
            "    @ratelimit(key='ip', rate='10/m')\n    @action(detail=True)\n"
            "    def extra(self, request):\n        return Response({})",
        )
        disk = "class V(viewsets.ModelViewSet):\n    pass\n"
        hits = mt.find_matches(tn, ti, TRIGGERS, disk)
        self.assertNotIn("drf-action-no-ratelimit", ids(hits))


class TestAbsenceOnResultingFile(unittest.TestCase):
    """The false-positive guard: fragment lacks the mitigation, file already has it."""

    def test_action_added_but_file_already_ratelimited_silent(self):
        disk = (
            "class ForumViewSet(viewsets.ModelViewSet):\n"
            "    @ratelimit(key='ip', rate='10/m')\n"
            "    @action(detail=False)\n"
            "    def existing(self, request):\n"
            "        return Response([])\n\n"
            "    def get(self, request):\n"
            "        return Response(data)\n"
        )
        # The new fragment introduces @action but NO ratelimit; naive
        # absence-on-fragment would FALSE-FIRE here.
        tn, ti = edit(
            "backend/apps/forum/views.py",
            "    def get(self, request):\n        return Response(data)",
            "    def get(self, request):\n        return Response(data)\n\n"
            "    @action(detail=True)\n    def new_one(self, request):\n"
            "        return Response({})",
        )
        hits = mt.find_matches(tn, ti, TRIGGERS, disk)
        self.assertNotIn(
            "drf-action-no-ratelimit", ids(hits),
            "must stay silent: resulting file already contains a ratelimit",
        )


class TestPathGlob(unittest.TestCase):
    def test_path_mismatch_silent(self):
        tn, ti = edit(
            "backend/apps/forum/serializers.py",
            "x",
            "x\n    @action(detail=True)\n    def f(self): ...",
        )
        hits = mt.find_matches(tn, ti, TRIGGERS, "x\n")
        self.assertEqual(ids(hits), [])

    def test_nested_views_path_matches(self):
        tn, ti = edit(
            "backend/apps/forum_integration/views.py",
            "p",
            "p\n    @action(detail=True)\n    def f(self): ...",
        )
        hits = mt.find_matches(tn, ti, TRIGGERS, "p\n")
        self.assertIn("drf-action-no-ratelimit", ids(hits))


class TestWriteTool(unittest.TestCase):
    def test_write_resulting_file_is_content(self):
        tn, ti = write(
            "backend/apps/forum/views.py",
            "class V:\n    @action(detail=True)\n    def f(self): ...\n",
        )
        hits = mt.find_matches(tn, ti, TRIGGERS, None)
        self.assertIn("drf-action-no-ratelimit", ids(hits))

    def test_write_with_ratelimit_silent(self):
        tn, ti = write(
            "backend/apps/forum/views.py",
            "class V:\n    @ratelimit(rate='1/m')\n    @action(detail=True)\n"
            "    def f(self): ...\n",
        )
        hits = mt.find_matches(tn, ti, TRIGGERS, None)
        self.assertNotIn("drf-action-no-ratelimit", ids(hits))


class TestRouterImport(unittest.TestCase):
    def test_bare_react_router_fires(self):
        tn, ti = write("web/src/pages/Home.tsx", "import { useNavigate } from 'react-router'\n")
        hits = mt.find_matches(tn, ti, TRIGGERS, None)
        self.assertIn("react-router-import", ids(hits))

    def test_react_router_dom_silent(self):
        tn, ti = write("web/src/pages/Home.tsx", "import { useNavigate } from 'react-router-dom'\n")
        hits = mt.find_matches(tn, ti, TRIGGERS, None)
        self.assertNotIn("react-router-import", ids(hits))


class TestMultiEdit(unittest.TestCase):
    def test_multiedit_applies_edits_and_fires(self):
        tn, ti = multiedit(
            "backend/apps/forum/views.py",
            [
                {"old_string": "a", "new_string": "a\n    @action(detail=True)"},
                {"old_string": "b", "new_string": "b\n    def f(self): ..."},
            ],
        )
        hits = mt.find_matches(tn, ti, TRIGGERS, "a\nb\n")
        self.assertIn("drf-action-no-ratelimit", ids(hits))

    def test_multiedit_unknown_shape_degrades_no_crash(self):
        # edits is not a list — must not raise; path-only fallback (no content gate)
        tn, ti = "MultiEdit", {"file_path": "backend/apps/forum/views.py", "edits": "bogus"}
        hits = mt.find_matches(tn, ti, TRIGGERS, "whatever")
        self.assertIsInstance(hits, list)


class TestFormatting(unittest.TestCase):
    def test_format_hits_includes_severity_and_pattern_ref(self):
        out = mt.format_hits([RATELIMIT])
        self.assertIn("WARN", out)
        self.assertIn("rate limit", out)
        self.assertIn("backend/docs/patterns/architecture/rate-limiting.md", out)

    def test_format_hits_empty(self):
        self.assertEqual(mt.format_hits([]), "")


class TestGracefulDegradation(unittest.TestCase):
    def test_malformed_payload_no_crash(self):
        hits = mt.find_matches("Edit", {}, TRIGGERS, None)
        self.assertEqual(hits, [])

    def test_bad_regex_in_trigger_does_not_crash(self):
        bad = dict(RATELIMIT, content_present="(unclosed")
        tn, ti = write("backend/apps/forum/views.py", "@action\n")
        hits = mt.find_matches(tn, ti, [bad], None)
        self.assertIsInstance(hits, list)


class TestEndToEndSubprocess(unittest.TestCase):
    """Drive the script as the hook would: stdin JSON, real disk file, temp index."""

    def _run(self, payload, project_root, triggers_file):
        env = dict(os.environ)
        env["INJECT_PROJECT_ROOT"] = project_root
        env["INJECT_TRIGGERS_FILE"] = triggers_file
        p = subprocess.run(
            [sys.executable, SCRIPT],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_disk_read_suppresses_when_file_already_ratelimited(self):
        with tempfile.TemporaryDirectory() as root:
            tf = os.path.join(root, "triggers.json")
            with open(tf, "w") as fh:
                json.dump([RATELIMIT], fh)
            target_dir = os.path.join(root, "backend", "apps", "forum")
            os.makedirs(target_dir)
            target = os.path.join(target_dir, "views.py")
            disk = (
                "class V(viewsets.ModelViewSet):\n"
                "    @ratelimit(rate='1/m')\n    @action(detail=False)\n"
                "    def existing(self, request):\n        return Response([])\n"
                "    def get(self, request):\n        return Response(data)\n"
            )
            with open(target, "w") as fh:
                fh.write(disk)
            payload = {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": target,
                    "old_string": "    def get(self, request):\n        return Response(data)",
                    "new_string": "    def get(self, request):\n        return Response(data)\n"
                    "    @action(detail=True)\n    def new_one(self, request): ...",
                },
            }
            out = self._run(payload, root, tf)
            self.assertEqual(out.strip(), "", "disk already has ratelimit → silent")

    def test_non_edit_tool_silent(self):
        with tempfile.TemporaryDirectory() as root:
            tf = os.path.join(root, "triggers.json")
            with open(tf, "w") as fh:
                json.dump([RATELIMIT], fh)
            out = self._run(
                {"tool_name": "Read", "tool_input": {"file_path": "x"}}, root, tf
            )
            self.assertEqual(out.strip(), "")


class TestRealTriggerIndex(unittest.TestCase):
    """Validate the shipped docs/rules/triggers.json: schema, regex, no dangling refs."""

    @classmethod
    def setUpClass(cls):
        cls.root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        with open(os.path.join(cls.root, "docs", "rules", "triggers.json")) as fh:
            cls.index = json.load(fh)

    def test_is_nonempty_list(self):
        self.assertIsInstance(self.index, list)
        self.assertGreaterEqual(len(self.index), 6)

    def test_ids_unique(self):
        idlist = [t["id"] for t in self.index]
        self.assertEqual(len(idlist), len(set(idlist)))

    def test_each_entry_well_formed(self):
        for t in self.index:
            with self.subTest(id=t.get("id")):
                self.assertTrue(t.get("id"))
                self.assertIsInstance(t.get("path_glob"), list)
                self.assertTrue(t["path_glob"])
                self.assertTrue(t.get("message"))
                self.assertIn(t.get("severity"), ("warn", "info", "candidate"))
                for key in ("content_present", "content_absent"):
                    if t.get(key):
                        re.compile(t[key])  # raises re.error if invalid

    def test_pattern_refs_resolve(self):
        for t in self.index:
            ref = t.get("pattern_ref")
            if ref:
                with self.subTest(id=t["id"], ref=ref):
                    self.assertTrue(
                        os.path.isfile(os.path.join(self.root, ref)),
                        "dangling pattern_ref: {}".format(ref),
                    )


class TestRealIndexFiresOnKnownBugs(unittest.TestCase):
    """The shipped regexes must actually match the bug they target (and not the fix)."""

    @classmethod
    def setUpClass(cls):
        cls.root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        with open(os.path.join(cls.root, "docs", "rules", "triggers.json")) as fh:
            cls.index = json.load(fh)

    def fires(self, tool_name, tool_input, disk=None):
        return ids(mt.find_matches(tool_name, tool_input, self.index, disk))

    def test_action_without_ratelimit(self):
        tn, ti = write("backend/apps/forum_integration/api_views.py",
                        "class V:\n    @action(detail=True)\n    def f(self): ...\n")
        self.assertIn("drf-action-no-ratelimit", self.fires(tn, ti))

    def test_action_with_ratelimit_silent(self):
        tn, ti = write("backend/apps/forum_integration/api_views.py",
                        "class V:\n    @ratelimit(key='ip', rate='5/m')\n"
                        "    @action(detail=True)\n    def f(self): ...\n")
        self.assertNotIn("drf-action-no-ratelimit", self.fires(tn, ti))

    def test_migration_fstring_sql(self):
        tn, ti = write(
            "backend/apps/blog/migrations/0002_x.py",
            'migrations.RunSQL(f"ALTER TABLE {table} ADD COLUMN x int")\n',
        )
        self.assertIn("migration-fstring-sql", self.fires(tn, ti))

    def test_migration_with_sql_identifier_silent(self):
        tn, ti = write(
            "backend/apps/blog/migrations/0002_x.py",
            'cursor.execute(sql.SQL("ALTER TABLE {}").format(sql.Identifier(table)))\n',
        )
        self.assertNotIn("migration-fstring-sql", self.fires(tn, ti))

    def test_get_permissions_without_super(self):
        tn, ti = write(
            "backend/apps/forum_integration/api_views.py",
            "    def get_permissions(self):\n        return [IsAuthenticated()]\n",
        )
        self.assertIn("viewset-get-permissions-no-super", self.fires(tn, ti))

    def test_get_permissions_with_super_silent(self):
        tn, ti = write(
            "backend/apps/forum_integration/api_views.py",
            "    def get_permissions(self):\n"
            "        if self.action == 'x':\n            return super().get_permissions()\n",
        )
        self.assertNotIn("viewset-get-permissions-no-super", self.fires(tn, ti))

    def test_wagtail_signal_hasattr(self):
        tn, ti = write("backend/apps/blog/signals.py",
                       "if hasattr(instance, 'blogpostpage'):\n    pass\n")
        self.assertIn("wagtail-signal-hasattr-pagetype", self.fires(tn, ti))

    def test_pagination_hasattr_page_silent(self):
        # hasattr(paginator, 'page') is pagination, not a page-type check.
        tn, ti = write("backend/apps/blog/signals.py",
                       "if hasattr(paginator, 'page'):\n    pass\n")
        self.assertNotIn("wagtail-signal-hasattr-pagetype", self.fires(tn, ti))

    def test_react_router_bare_import(self):
        tn, ti = write("web/src/pages/Home.tsx",
                       "import { useNavigate } from 'react-router'\n")
        self.assertIn("react-router-bare-import", self.fires(tn, ti))

    def test_nonatomic_counter(self):
        tn, ti = write("backend/apps/forum_integration/services.py",
                       "topic.reply_count += 1\ntopic.save()\n")
        self.assertIn("drf-nonatomic-counter", self.fires(tn, ti))

    def test_atomic_counter_with_F_silent(self):
        tn, ti = write("backend/apps/forum_integration/services.py",
                       "Topic.objects.filter(pk=pk).update(reply_count=F('reply_count') + 1)\n")
        self.assertNotIn("drf-nonatomic-counter", self.fires(tn, ti))

    def test_bare_local_counter_silent(self):
        # A plain local-variable counter is NOT an ORM atomicity problem.
        tn, ti = write("backend/apps/forum_integration/services.py",
                       "    retry_count = 0\n    for x in items:\n        retry_count += 1\n")
        self.assertNotIn("drf-nonatomic-counter", self.fires(tn, ti))

    def test_bare_error_count_local_silent(self):
        tn, ti = write("backend/apps/forum_integration/services.py",
                       "    error_count += 1\n")
        self.assertNotIn("drf-nonatomic-counter", self.fires(tn, ti))


if __name__ == "__main__":
    unittest.main(verbosity=2)
