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


class TestPostMigrateReceiverTrigger(unittest.TestCase):
    """Todo 374 — asserted against the REAL docs/rules/triggers.json.

    The motivating bug: a `post_migrate` receiver called
    `Collection.get_first_root_node().get_children()`. `flush` re-emits
    `post_migrate` after truncating everything, and Wagtail's root collection
    comes from a data migration that does not re-run — so the receiver raised
    inside `TransactionTestCase` teardown and failed 12 unrelated blog tests.
    """

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        cls.real = mt.load_triggers(root)

    def test_new_post_migrate_receiver_fires(self):
        tn, ti = write(
            "backend/apps/garden/bootstrap.py",
            "from django.db.models.signals import post_migrate\n\n"
            "def seed(sender, **kwargs):\n    pass\n\n"
            "post_migrate.connect(seed)\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn("post-migrate-receiver-must-not-raise", ids(hits))

    def test_guarded_receiver_is_silent(self):
        """The shipped fix must not fire on itself.

        The negative exercises the pattern rather than avoiding it: this file
        DOES contain `post_migrate`, so only the guard suppresses it.
        """
        tn, ti = write(
            "backend/apps/forum_host/bootstrap.py",
            "from django.db.models.signals import post_migrate\n\n"
            "def _ensure(sender, **kwargs):\n"
            "    if Collection.get_first_root_node() is None:\n"
            "        return\n\n"
            "post_migrate.connect(_ensure)\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("post-migrate-receiver-must-not-raise", ids(hits))


class TestRequestsExceptionUrlAttribute(unittest.TestCase):
    """Todo 358 review — asserted against the REAL docs/rules/triggers.json.

    The motivating bug: the drift guard's safe-set marked every name under any
    attribute access as safe, so ``e.response.url`` / ``e.request.url`` /
    ``e.args[0]`` -- each of which rebuilds the prepared URL the guard exists to
    keep out of logs -- passed unflagged. Fixtures below are the exact lines
    from that guard's planted specimen, not idealised ones.
    """

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        cls.real = mt.load_triggers(root)

    def test_response_url_fires(self):
        tn, ti = write(
            "backend/apps/plant_identification/services/some_service.py",
            '        logger.error(f"resp url: {e.response.url}")\n',
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn("requests-exception-url-attribute", ids(hits))

    def test_request_url_fires(self):
        tn, ti = write(
            "backend/apps/plant_identification/services/some_service.py",
            '        logger.error(f"req url: {e.request.url}")\n',
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn("requests-exception-url-attribute", ids(hits))

    def test_args_index_fires(self):
        tn, ti = write(
            "backend/apps/plant_identification/services/some_service.py",
            '        logger.error(f"args: {e.args[0]}")\n',
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn("requests-exception-url-attribute", ids(hits))

    def test_approved_status_code_shape_is_silent(self):
        """The nearest APPROVED neighbour must not fire.

        This is the negative that actually exercises the regex: it is an
        attribute chain on the same bound name, differing only in the final
        attribute. A negative with no attribute access at all would prove
        nothing.
        """
        tn, ti = write(
            "backend/apps/plant_identification/services/some_service.py",
            '        logger.error(f"{type(e).__name__} {e.response.status_code}")\n',
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("requests-exception-url-attribute", ids(hits))

    def test_unrelated_exception_attribute_is_silent(self):
        """The one pre-existing repo occurrence, verbatim, must stay silent.

        ``apps/users/tests/test_oauth_google.py:158`` reads
        ``ctx.exception.response.url`` -- a Django redirect, not a requests
        exception. The bound-name prefix in the regex is what excludes it.
        """
        tn, ti = write(
            "backend/apps/users/tests/test_oauth_google.py",
            '        self.assertIn("error=unverified_email", '
            "ctx.exception.response.url)\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("requests-exception-url-attribute", ids(hits))


class TestE2ESelectorAndStateTriggers(unittest.TestCase):
    """Todo 331 codification — asserted against the REAL docs/rules/triggers.json.

    Unlike the classes above, these load the shipped index rather than the local
    fixture set, because the point is to pin the regexes that actually run. That
    matters: the dataset trigger's first regex (`documentElement\\.dataset\\.`) did
    NOT match the code that motivated it — the real helper aliased the element
    (`const el = document.documentElement; el.dataset.mode = ...`), so the trigger
    would have silently missed its own bug. Fixtures use the shipped shapes.
    """

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.real = mt.load_triggers(root)

    def test_exact_match_href_exclusion_fires(self):
        tn, ti = write(
            "web/e2e/forum.spec.js",
            'page.locator(\'#main-content a[href^="/forum/"]:not([href="/forum/new-thread"])\')\n',
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn("exact-match-href-not-selector", ids(hits))

    def test_prefix_href_exclusion_silent(self):
        tn, ti = write(
            "web/e2e/forum.spec.js",
            'page.locator(\'#main-content a[href^="/forum/"]:not([href^="/forum/new-thread"])\')\n',
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("exact-match-href-not-selector", ids(hits))

    def test_aliased_dataset_write_fires(self):
        # The shape that actually shipped — element aliased, then assigned.
        tn, ti = write(
            "web/e2e/theme.spec.ts",
            "const el = document.documentElement;\n  el.dataset.mode = a.mode;\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn("e2e-writes-documentelement-dataset", ids(hits))

    def test_dataset_read_only_silent(self):
        # Reading/asserting a dataset value is fine; only writing drives state.
        # NOTE: this fixture alone is vacuous — it is the one read form containing
        # no '=' at all, so it passed even while `\\s*=` was matching the first
        # character of '==='. The comparison cases below are the real guard.
        tn, ti = write("web/e2e/theme.spec.ts", "expect(el.dataset.mode).toBe('dark');\n")
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("e2e-writes-documentelement-dataset", ids(hits))

    def test_dataset_comparison_silent(self):
        """A comparison is a read. `\\s*=` matches the first char of '===' unless
        the pattern excludes it — caught in review of this PR, not by the suite."""
        for frag in (
            "if (el.dataset.mode === 'dark') { return; }\n",
            "expect(html.dataset.mode == 'dark').toBe(true);\n",
            "if (el.dataset.mode !== 'dark') { return; }\n",
        ):
            with self.subTest(frag=frag.strip()):
                tn, ti = write("web/e2e/theme.spec.ts", frag)
                hits = mt.find_matches(tn, ti, self.real, None)
                self.assertNotIn("e2e-writes-documentelement-dataset", ids(hits))

    def test_storage_driven_theme_silent(self):
        tn, ti = write(
            "web/e2e/theme.spec.ts",
            "localStorage.setItem('gt-mode', a.mode);\n  await page.reload();\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("e2e-writes-documentelement-dataset", ids(hits))

    def test_hardcoded_conn_max_age_fires(self):
        """All three spellings, not just the dj_database_url kwarg. The rule text
        says "CONN_MAX_AGE"; a lowercase-only pattern missed the two canonical
        Django forms a future author is most likely to write."""
        for frag in (
            "        conn_max_age=600,\n",
            "    DATABASES['default']['CONN_MAX_AGE'] = 600\n",
            "        'CONN_MAX_AGE': 600,\n",
        ):
            with self.subTest(frag=frag.strip()):
                tn, ti = write("backend/plant_community_backend/settings.py", frag)
                hits = mt.find_matches(tn, ti, self.real, None)
                self.assertIn("unconditional-conn-max-age", ids(hits))

    def test_zero_conn_max_age_silent(self):
        tn, ti = write("backend/plant_community_backend/settings.py", "        conn_max_age=0,\n")
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("unconditional-conn-max-age", ids(hits))

    def test_real_settings_block_silent(self):
        """The shipped, fixed settings.py must not self-fire — it names
        CONN_MAX_AGE in prose twice and assigns DB_CONN_MAX_AGE = config(...)."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        real_settings = os.path.join(root, "backend", "plant_community_backend", "settings.py")
        with open(real_settings, encoding="utf-8") as fh:
            body = fh.read()
        start = body.index("# Persistent connections are a production optimisation")
        tn, ti = write(
            "backend/plant_community_backend/settings.py", body[start : start + 1200]
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("unconditional-conn-max-age", ids(hits))

    def test_gated_conn_max_age_silent(self):
        tn, ti = write(
            "backend/plant_community_backend/settings.py",
            "        conn_max_age=DB_CONN_MAX_AGE,\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("unconditional-conn-max-age", ids(hits))


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

    def test_new_action_on_wagtail_viewset_fires_unrouted_warning(self):
        # todo 307: 6 of 7 @action methods on BlogPostPageViewSet shipped
        # with no path() entry — unreachable, 404, no error anywhere.
        tn, ti = write(
            "backend/apps/blog/api/viewsets.py",
            "class BlogPostPageViewSet(PagesAPIViewSet):\n"
            "    @action(detail=False, methods=['get'])\n"
            "    def featured(self, request): ...\n",
        )
        self.assertIn("wagtail-action-unrouted", self.fires(tn, ti))

    def test_new_action_on_non_wagtail_viewset_silent(self):
        # A plain DRF viewset (not under apps/*/api/) mounted via
        # SimpleRouter auto-mounts @action methods — the Wagtail-specific
        # warning would be a false positive here.
        tn, ti = write(
            "backend/apps/forum_integration/api_views.py",
            "class V:\n    @action(detail=True)\n    def f(self): ...\n",
        )
        self.assertNotIn("wagtail-action-unrouted", self.fires(tn, ti))

    def test_bare_strip_tags_fires(self):
        # todo 275: strip_tags substitutes nothing for a tag, so adjacent blocks fuse.
        tn, ti = write(
            "backend/apps/forum_host/compose_assist.py",
            'def flatten(raw):\n    return strip_tags(raw or "").strip()\n',
        )
        self.assertIn("strip-tags-not-html-to-text", self.fires(tn, ti))

    def test_strip_tags_with_boundary_and_unescape_silent(self):
        tn, ti = write(
            "backend/apps/forum_host/compose_assist.py",
            'def flatten(raw):\n'
            '    return html.unescape(strip_tags(_BLOCK_BOUNDARY_RE.sub("\\n", raw)))\n',
        )
        self.assertNotIn("strip-tags-not-html-to-text", self.fires(tn, ti))

    def test_tiptap_insertcontent_string_fires(self):
        # todo 275: a string arg is parsed as HTML → model output becomes structure.
        tn, ti = write(
            "web/src/components/forum/TipTapEditor.tsx",
            "editor.chain().focus().insertContent(improved).run();\n",
        )
        self.assertIn("tiptap-insertcontent-html-string", self.fires(tn, ti))

    def test_tiptap_insertcontent_nodes_silent(self):
        tn, ti = write(
            "web/src/components/forum/TipTapEditor.tsx",
            "const nodes = lines.map((line) => ({ type: 'paragraph', "
            "content: [{ type: 'text', text: line }] }));\n"
            "editor.chain().focus().insertContent(nodes).run();\n",
        )
        self.assertNotIn("tiptap-insertcontent-html-string", self.fires(tn, ti))

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

    def test_escape_search_query_call_fires(self):
        tn, ti = write(
            "backend/apps/forum_integration/api_views.py",
            "safe_query = escape_search_query(query)\n"
            "qs = qs.filter(title__icontains=safe_query)\n",
        )
        self.assertIn(
            "escape-search-query-before-orm-wildcard-lookup", self.fires(tn, ti)
        )

    def test_plain_icontains_no_escape_call_silent(self):
        # No escape_search_query() call at all — nothing to double-check.
        tn, ti = write(
            "backend/apps/forum_integration/api_views.py",
            "qs = qs.filter(title__icontains=query)\n",
        )
        self.assertNotIn(
            "escape-search-query-before-orm-wildcard-lookup", self.fires(tn, ti)
        )

    def test_redundant_integrityerror_fallback_fires(self):
        tn, ti = write(
            "backend/apps/forum_integration/models.py",
            "try:\n"
            "    obj, _ = cls.objects.update_or_create(\n"
            "        user=user, topic_id=topic_id, defaults={'last_read_at': when}\n"
            "    )\n"
            "except IntegrityError:\n"
            "    obj = cls.objects.get(user=user, topic_id=topic_id)\n",
        )
        self.assertIn("redundant-integrityerror-fallback", self.fires(tn, ti))

    def test_get_or_create_with_no_fallback_silent(self):
        # No except IntegrityError at all — nothing to double-check.
        tn, ti = write(
            "backend/apps/forum_integration/models.py",
            "obj, created = cls.objects.get_or_create(\n"
            "    user=user, topic_id=topic_id, defaults={'last_read_at': when}\n"
            ")\n",
        )
        self.assertNotIn("redundant-integrityerror-fallback", self.fires(tn, ti))

    def test_tiptap_renderhtml_without_mergeattributes_fires(self):
        tn, ti = write(
            "web/src/components/forum/forumMentionNode.ts",
            "export const X = Mention.configure({\n"
            "  renderHTML({ options, node }) {\n"
            "    return ['span', {}, node.attrs.label];\n"
            "  },\n"
            "});\n",
        )
        self.assertIn(
            "tiptap-custom-renderhtml-missing-mergeattributes", self.fires(tn, ti)
        )

    def test_tiptap_renderhtml_with_mergeattributes_silent(self):
        tn, ti = write(
            "web/src/components/forum/forumMentionNode.ts",
            "export const X = Mention.configure({\n"
            "  renderHTML({ options, node, HTMLAttributes }) {\n"
            "    return ['span', mergeAttributes(HTMLAttributes), node.attrs.label];\n"
            "  },\n"
            "});\n",
        )
        self.assertNotIn(
            "tiptap-custom-renderhtml-missing-mergeattributes", self.fires(tn, ti)
        )


class TestTodo310Triggers(unittest.TestCase):
    """Todos 310/315 codification — asserted against the REAL docs/rules/triggers.json.

    Fixtures are the ACTUAL pre-fix code from `web/src/services/authService.ts`
    and its test file, not idealised versions: the parse-guard regex has to match
    the real four-line `let data / try / await response.json() / } catch` shape,
    and the mock regex has to match the real fake, which embeds the browser's own
    message text and an escaped quote.
    """

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.real = mt.load_triggers(root)

    # --- fake-error-type-in-json-mock ---

    def test_bare_error_in_json_mock_fires(self):
        # Verbatim from the todo-310 first draft.
        tn, ti = write(
            "web/src/services/authService.test.ts",
            "        json: async () => {\n"
            "          throw new Error('Unexpected token \\'<\\', \"<!DOCTYPE \"... is not valid JSON');\n"
            "        },\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn("fake-error-type-in-json-mock", ids(hits))

    def test_syntaxerror_in_json_mock_silent(self):
        # The corrected form. Contains the SAME message text the regex keys on,
        # so this is an adversarial negative rather than a vacuous one — only
        # the constructor differs.
        tn, ti = write(
            "web/src/services/authService.test.ts",
            "        json: async () => {\n"
            "          throw new SyntaxError('Unexpected token \\'<\\', \"<!DOCTYPE \"... is not valid JSON');\n"
            "        },\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("fake-error-type-in-json-mock", ids(hits))

    def test_unrelated_error_throw_in_test_silent(self):
        # A thrown Error with no parse-failure text must not fire.
        tn, ti = write(
            "web/src/services/authService.test.ts",
            "        json: async () => {\n"
            "          throw new Error('network down');\n"
            "        },\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("fake-error-type-in-json-mock", ids(hits))

    # --- json-parse-guard-without-shape-check ---

    def test_guarded_parse_without_shape_check_fires(self):
        # Verbatim from the todo-310 first draft, before the shape check moved in.
        tn, ti = write(
            "web/src/services/authService.ts",
            "    let data: AuthResponse;\n"
            "    try {\n"
            "      data = await response.json();\n"
            "    } catch {\n"
            "      throw new Error('unreadable');\n"
            "    }\n"
            "    return data.user;\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn("json-parse-guard-without-shape-check", ids(hits))

    def test_guarded_parse_with_shape_check_silent(self):
        # The shipped form. The `} catch` still directly follows a parse line, so
        # the presence regex alone would fire — only `--content-absent` on
        # `if (!data` suppresses it. That is what this pins.
        tn, ti = write(
            "web/src/services/authService.ts",
            "    let data: AuthResponse;\n"
            "    try {\n"
            "      data = await response.json();\n"
            "      if (!data?.user) throw new SyntaxError('login body is not an AuthResponse');\n"
            "    } catch (parseError) {\n"
            "      throw new Error('unreadable', { cause: parseError });\n"
            "    }\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("json-parse-guard-without-shape-check", ids(hits))

    def test_unguarded_parse_silent(self):
        # No try/catch at all is a DIFFERENT defect (the one todo 310 fixed), not
        # this trigger's; it must not claim that case.
        tn, ti = write(
            "web/src/services/authService.ts",
            "    const data: AuthResponse = await response.json();\n"
            "    return data.user;\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("json-parse-guard-without-shape-check", ids(hits))
class TestForumWagtailQuickWinTriggers(unittest.TestCase):
    """PR #624 codification — asserted against the REAL docs/rules/triggers.json.
    Positive fixtures are the shapes that actually shipped (or nearly did)."""

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.real = mt.load_triggers(root)

    # update_or_create keyed on a None lookup -----------------------------------
    def test_update_or_create_with_none_lookup_fires(self):
        # The pre-fix redirects.py shape: site=None in the LOOKUP kwargs.
        tn, ti = write(
            "backend/apps/forum_host/redirects.py",
            "    Redirect.objects.update_or_create(\n"
            "        old_path=old_path,\n"
            "        site=None,\n"
            "        defaults={\n"
            '            "redirect_link": new_path,\n'
            "        },\n"
            "    )\n",
        )
        self.assertIn("update-or-create-nullable-lookup", ids(mt.find_matches(tn, ti, self.real, None)))

    def test_update_or_create_with_none_only_in_defaults_silent(self):
        tn, ti = write(
            "backend/apps/forum_host/redirects.py",
            "    Redirect.objects.update_or_create(\n"
            "        old_path=old_path, site=site,\n"
            '        defaults={"redirect_page": None, "is_permanent": True},\n'
            "    )\n",
        )
        self.assertNotIn("update-or-create-nullable-lookup", ids(mt.find_matches(tn, ti, self.real, None)))

    # caplog on a non-propagating logger ----------------------------------------
    def test_caplog_on_apps_logger_without_handler_fires(self):
        # The shipped test_search_hits.py shape: the logger name lives in a
        # module constant, so the regex must match the assignment, not the call.
        tn, ti = write(
            "backend/apps/forum_host/tests/test_search_hits.py",
            'LOGGER = "apps.forum_host.search_hits"\n\n'
            "def test_a_logging_failure_does_not_fail_the_search(monkeypatch, caplog):\n"
            "    with caplog.at_level(logging.WARNING, logger=LOGGER):\n"
            '        resp = APIClient().get(SEARCH, {"q": "monstera"})\n',
        )
        self.assertIn("caplog-on-non-propagating-logger", ids(mt.find_matches(tn, ti, self.real, None)))

    def test_caplog_on_apps_logger_with_handler_attached_silent(self):
        tn, ti = write(
            "backend/apps/forum_host/tests/test_search_hits.py",
            'LOGGER = "apps.forum_host.search_hits"\n\n'
            "def test_a_logging_failure_does_not_fail_the_search(monkeypatch, caplog):\n"
            "    log = logging.getLogger(LOGGER)\n"
            "    log.addHandler(caplog.handler)\n"
            "    try:\n"
            "        with caplog.at_level(logging.WARNING, logger=LOGGER):\n"
            '            resp = APIClient().get(SEARCH, {"q": "monstera"})\n'
            "    finally:\n"
            "        log.removeHandler(caplog.handler)\n",
        )
        self.assertNotIn("caplog-on-non-propagating-logger", ids(mt.find_matches(tn, ti, self.real, None)))

    def test_caplog_on_propagating_package_logger_silent(self):
        # wagtail_forum propagates; the package suite's plain caplog use is fine.
        tn, ti = write(
            "backend/apps/forum_host/tests/test_signals.py",
            'with caplog.at_level("ERROR", logger="forum_host.notifications"):\n    pass\n',
        )
        self.assertNotIn("caplog-on-non-propagating-logger", ids(mt.find_matches(tn, ti, self.real, None)))

    # dotted list_export path -----------------------------------------------------
    def test_dotted_list_export_fires(self):
        tn, ti = write(
            "backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py",
            '    list_export = [\n        "id",\n        "post.topic.title",\n        "reporter",\n    ]\n',
        )
        self.assertIn("list-export-dotted-nullable-fk", ids(mt.find_matches(tn, ti, self.real, None)))

    def test_property_list_export_silent(self):
        tn, ti = write(
            "backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py",
            '    list_export = [\n        "id",\n        "topic_title",\n        "reporter",\n    ]\n',
        )
        self.assertNotIn("list-export-dotted-nullable-fk", ids(mt.find_matches(tn, ti, self.real, None)))


class TestCiArtifactStepTrigger(unittest.TestCase):
    """Todo 354 codification — asserted against the REAL docs/rules/triggers.json.

    Fixtures are the shipped shapes from .github/workflows/security-scan.yml
    before and after PR #678, not idealised versions: the pre-fix step wrote its
    report and swallowed the exit code, so a crashed pip-audit was
    indistinguishable from a clean audit and new-vuln-gate silently audited
    nothing for months.
    """

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.real = mt.load_triggers(root)

    PRE_FIX = (
        "          pip-audit -r /tmp/gate/base-requirements.txt --format json \\\n"
        "            --output /tmp/gate/base-pip.json || true\n"
        "          pip-audit -r backend/requirements.txt --format json \\\n"
        "            --output /tmp/gate/head-pip.json || true\n"
    )

    POST_FIX = PRE_FIX + (
        "          for f in /tmp/gate/base-pip.json /tmp/gate/head-pip.json; do\n"
        '            if [ ! -s "$f" ]; then\n'
        '              echo "::error::pip-audit produced no report at $f"\n'
        "              exit 1\n"
        "            fi\n"
        "          done\n"
    )

    def test_swallowed_failure_fires(self):
        tn, ti = write(".github/workflows/security-scan.yml", self.PRE_FIX)
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn("ci-artifact-step-swallows-failure", ids(hits))

    def test_redirect_form_also_fires(self):
        # The npm half uses `> file.json || true` rather than --output.
        tn, ti = write(
            ".github/workflows/security-scan.yml",
            "          (cd web && npm audit --json > /tmp/gate/head-npm.json || true)\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn("ci-artifact-step-swallows-failure", ids(hits))

    def test_asserted_artefact_is_silent(self):
        # `|| true` is still present — the assertion below it is what suppresses.
        tn, ti = write(".github/workflows/security-scan.yml", self.POST_FIX)
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("ci-artifact-step-swallows-failure", ids(hits))

    def test_unrelated_or_true_is_silent(self):
        # `|| true` with no artefact written is not what this rule is about.
        tn, ti = write(
            ".github/workflows/security-scan.yml",
            "          rm -f /tmp/gate/stale.lock || true\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn("ci-artifact-step-swallows-failure", ids(hits))


class TestEmitFlagsSuppressedAuditTrigger(unittest.TestCase):
    """Todo 355 slice 6 — asserted against the REAL docs/rules/triggers.json.

    The positive fixture is the VERBATIM text that shipped the bug in todo 366
    and was caught in code review, not a cleaned-up version of it: a --emit-flags
    audit prescribed as the way to re-assess the very ids --emit-flags suppresses.
    The negatives are the shipped files that legitimately contain --emit-flags, so
    a future widening of the regex fails here instead of crying wolf on every one
    of them.
    """

    @classmethod
    def setUpClass(cls):
        cls.root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        cls.real = mt.load_triggers(cls.root)

    TRIGGER = "pip-audit-emit-flags-hides-the-entry-under-review"

    def test_the_real_todo_366_text_fires(self):
        tn, ti = write(
            "todos/366-pending-p3-suppression-reassessment.md",
            "1. Query OSV at the pinned version and run the local audit:\n\n"
            "   ```bash\n"
            "   cd backend && pip-audit -r requirements.txt \\\n"
            "     ${=$(python3 ../scripts/check_suppressions.py --emit-flags)}\n"
            "   ```\n",
        )
        self.assertIn(self.TRIGGER, ids(mt.find_matches(tn, ti, self.real, None)))

    def test_shipped_files_that_use_emit_flags_do_not_self_fire(self):
        """The already-correct files must stay silent on their own content.

        Each mentions --emit-flags AND its unsuppressed counterpart, so
        --content-absent gates them. Written as a whole-file Write, because that
        is what makes `resulting_file` the real file: a fragment-only Write would
        drop the counterpart and fire, which is correct behaviour, not a bug.
        """
        for rel in (
            ".github/security-suppressions.yml",
            ".github/workflows/security-scan.yml",
            "docs/rules/security.md",
            "scripts/sync_alarm_todo.py",
        ):
            with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("emit-flags", body, f"{rel} no longer mentions --emit-flags")
            tn, ti = write(rel, body)
            self.assertNotIn(self.TRIGGER, ids(mt.find_matches(tn, ti, self.real, body)), rel)


class TestPackageLockOnlySkewTrigger(unittest.TestCase):
    """Todo 356 — asserted against the REAL docs/rules/triggers.json.

    The positive fixture is the VERBATIM step this PR shipped BEFORE code review
    caught the gap — `--package-lock-only` with no lockfile-sync check — not a
    cleaned-up version of it. The negative is the shipped file after the fix, so
    a future widening of the regex fails here instead of crying wolf on the very
    workflow that motivated it.
    """

    @classmethod
    def setUpClass(cls):
        cls.root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        cls.real = mt.load_triggers(cls.root)

    TRIGGER = "npm-audit-package-lock-only-misses-lockfile-skew"

    def test_the_pre_review_step_fires(self):
        tn, ti = write(
            ".github/workflows/security-scan.yml",
            "          for dir in \"${MANIFEST_DIRS[@]}\"; do\n"
            "            echo \"::group::npm audit --audit-level=moderate (cwd: $dir)\"\n"
            "            if (cd \"$dir\" && npm audit --package-lock-only --audit-level=moderate); then\n"
            "              echo \"clean: $dir\"\n"
            "            fi\n"
            "          done\n",
        )
        self.assertIn(self.TRIGGER, ids(mt.find_matches(tn, ti, self.real, None)))

    def test_the_json_report_form_also_fires(self):
        """The other shape in this repo: capturing the report rather than gating."""
        tn, ti = write(
            ".github/workflows/security-scan.yml",
            '            (cd "$dir" && npm audit --package-lock-only --json) '
            '> "npm-audit-reports/$slug.json" || true\n',
        )
        self.assertIn(self.TRIGGER, ids(mt.find_matches(tn, ti, self.real, None)))

    def test_the_shipped_fixed_workflow_does_not_self_fire(self):
        """The file carries BOTH the audit and the `npm ls` guard, so it stays silent.

        Whole-file Write, because that is what makes `resulting_file` the real
        file: a fragment-only Write would drop the guard and fire, which is the
        correct behaviour rather than a bug.
        """
        rel = ".github/workflows/security-scan.yml"
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("npm audit --package-lock-only", body)
        self.assertIn("npm ls --package-lock-only", body, "the guard was removed")
        tn, ti = write(rel, body)
        self.assertNotIn(self.TRIGGER, ids(mt.find_matches(tn, ti, self.real, body)))

    def test_a_plain_npm_audit_is_not_flagged(self):
        """`npm audit` after a real `npm ci` reads node_modules; the rule does not apply."""
        tn, ti = write(
            ".github/workflows/web-ci.yml",
            "          npm ci\n          npm audit --audit-level=moderate\n",
        )
        self.assertNotIn(self.TRIGGER, ids(mt.find_matches(tn, ti, self.real, None)))


class TestMediaRootIsolationTrigger(unittest.TestCase):
    """Todo 363 codification — asserted against the REAL docs/rules/triggers.json.

    The motivating bug: a fixture pinned `settings.MEDIA_ROOT` to isolate probe
    image writes, which is correct with local storage and a silent no-op under
    `USE_R2=True` — settings.py swaps `STORAGES["default"]` to `S3Storage`,
    which ignores MEDIA_ROOT, so the probe files would have gone to the real R2
    bucket. The positive fixture below is the real pre-fix fixture body, not an
    idealised version of it.
    """

    TRIGGER_ID = "media-root-isolation-needs-storages"
    PATH = "backend/apps/core/tests/test_image_rendition_formats.py"

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        cls.real = mt.load_triggers(root)

    def test_media_root_only_fixture_fires(self):
        tn, ti = write(
            self.PATH,
            '@pytest.fixture(autouse=True)\n'
            'def _isolated_media_root(settings, tmp_path):\n'
            '    """Keep probe uploads out of the real MEDIA_ROOT."""\n'
            "    settings.MEDIA_ROOT = str(tmp_path)\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn(self.TRIGGER_ID, ids(hits))

    def test_pinning_storages_as_well_stays_silent(self):
        tn, ti = write(
            self.PATH,
            '@pytest.fixture(autouse=True)\n'
            'def _isolated_media_root(settings, tmp_path):\n'
            "    settings.MEDIA_ROOT = str(tmp_path)\n"
            "    settings.STORAGES = {\n"
            "        **settings.STORAGES,\n"
            '        "default": {\n'
            '            "BACKEND": "django.core.files.storage.FileSystemStorage",\n'
            '            "OPTIONS": {"location": str(tmp_path)},\n'
            "        },\n"
            "    }\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn(self.TRIGGER_ID, ids(hits))

    def test_unrelated_backend_test_file_stays_silent(self):
        tn, ti = write(
            "backend/apps/core/tests/test_something_else.py",
            "def test_nothing_to_do_with_storage():\n    assert True\n",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn(self.TRIGGER_ID, ids(hits))


class TestNpmLockfileLibcTrigger(unittest.TestCase):
    """PR #718 codification — asserted against the REAL docs/rules/triggers.json.

    The motivating bug: regenerating package-lock.json with npm 11.6.0 silently
    stripped all 16 `libc` fields from the @img/sharp-* entries. That is the
    musl/glibc discriminator, so Alpine fails at RUNTIME ("cannot load shared
    library") — and it is invisible to `npm audit`, to CI (all 17 checks passed
    on the broken lockfile), and to a normal diff read.

    Fixtures use the SHIPPED shapes: the positive is the literal fragment the PR
    added to the root package.json, not an idealised one.
    """

    TRIGGER_ID = "npm-lockfile-regen-drops-libc"

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.real = mt.load_triggers(root)

    def test_real_overrides_fragment_fires(self):
        # Verbatim from PR #718's package.json edit.
        tn, ti = edit(
            "package.json",
            '  "scripts": {',
            '  "//sharp-override": "Pins sharp above miniflare...",\n'
            '  "overrides": {\n'
            '    "sharp": "^0.35.4"\n'
            '  },\n'
            '  "scripts": {',
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn(self.TRIGGER_ID, ids(hits))

    def test_devdependencies_bump_fires(self):
        tn, ti = edit(
            "package.json",
            '  "devDependencies": {\n    "wrangler": "^4.129.0"\n  },',
            '  "devDependencies": {\n    "wrangler": "^4.130.0"\n  },',
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn(self.TRIGGER_ID, ids(hits))

    def test_nested_manifest_fires(self):
        tn, ti = edit(
            "web/package.json",
            '  "dependencies": {\n    "react": "^19.0.0"\n  },',
            '  "dependencies": {\n    "react": "^19.1.0"\n  },',
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn(self.TRIGGER_ID, ids(hits))

    def test_scripts_only_edit_stays_silent(self):
        # Exercises the regex: a real package.json edit, full of `"key":` shapes
        # and quoted values, that touches no dependency key.
        tn, ti = edit(
            "package.json",
            '  "scripts": {',
            '  "scripts": {\n'
            '    "deploy": "wrangler deploy",\n'
            '    "preview": "wrangler dev",\n'
            '    "typecheck": "tsc --noEmit"',
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn(self.TRIGGER_ID, ids(hits))

    def test_unrelated_json_file_stays_silent(self):
        # Same content, wrong path — proves the path glob is doing work.
        tn, ti = edit(
            "web/tsconfig.json",
            '  "compilerOptions": {',
            '  "dependencies": { "nope": "1.0.0" },\n  "compilerOptions": {',
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn(self.TRIGGER_ID, ids(hits))


class TestDartDefineMapTrigger(unittest.TestCase):
    """`dart-define-missing-from-defines-map` — todo 382.

    A per-platform var can be wired into a getter and left out of the
    `_dartDefines` map. `String.fromEnvironment` is a compile-time constant, so
    the missing entry is never read: the value silently falls back to the shared
    key and four separate signals stay green — `flutter analyze`, the bare
    `flutter test` run, every injected-map unit test, and the grep-based
    acceptance criterion. Verified by mutation, not assumed.

    The positive fixture is the literal line the PR added, not an idealised one.
    """

    TRIGGER_ID = "dart-define-missing-from-defines-map"

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.real = mt.load_triggers(root)

    def test_real_per_platform_api_key_line_fires(self):
        # Verbatim from the todo-382 edit to firebase_options.dart.
        tn, ti = edit(
            "plant_community_mobile/lib/firebase_options.dart",
            "    apiKey: _required('FIREBASE_API_KEY'),",
            "    apiKey: _required(\n"
            "      'FIREBASE_ANDROID_API_KEY',\n"
            "      fallbackKey: 'FIREBASE_API_KEY',\n"
            "    ),",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn(self.TRIGGER_ID, ids(hits))

    def test_single_line_required_fires(self):
        tn, ti = edit(
            "plant_community_mobile/lib/firebase_options.dart",
            "    projectId: _required('FIREBASE_PROJECT_ID'),",
            "    projectId: _required('FIREBASE_PROJECT_ID'),\n"
            "    apiKey: _required('FIREBASE_IOS_API_KEY'),",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertIn(self.TRIGGER_ID, ids(hits))

    def test_non_firebase_required_call_stays_silent(self):
        # Exercises the regex, not a blank: same `_required('...')` shape, same
        # file, a var that is not a FIREBASE_ one. A negative fixture that
        # contained no `_required(` at all would prove nothing.
        tn, ti = edit(
            "plant_community_mobile/lib/firebase_options.dart",
            "  static const _dartDefines = <String, String>{",
            "  static const _dartDefines = <String, String>{\n"
            "    // apiBaseUrl: _required('API_BASE_URL'),",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn(self.TRIGGER_ID, ids(hits))

    def test_same_line_in_a_test_file_stays_silent(self):
        # Same content, wrong path — proves the path glob is doing work. Tests
        # legitimately hard-code these names against an injected map.
        tn, ti = edit(
            "plant_community_mobile/test/firebase_options_test.dart",
            "void main() {",
            "void main() {\n"
            "  // _required('FIREBASE_ANDROID_API_KEY') is asserted below",
        )
        hits = mt.find_matches(tn, ti, self.real, None)
        self.assertNotIn(self.TRIGGER_ID, ids(hits))


if __name__ == "__main__":
    unittest.main(verbosity=2)
