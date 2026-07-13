#!/usr/bin/env python3
"""Tests for check_agent_frontmatter — the pre-commit guard for todo 245.

Run: python3 scripts/inject/test_check_agent_frontmatter.py

Positive control: every real .claude/agents/*.md passes (all loadable since
todo 229). Negative control: a deliberately-broken fixture (bare multi-line
<example> block — the exact todo-229 regression shape) fails, pointing at the
offending file/line.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_agent_frontmatter as caf  # noqa: E402


class PositiveControlTests(unittest.TestCase):
    def test_all_real_agent_files_pass(self):
        agents_dir = caf.AGENTS_DIR
        self.assertTrue(agents_dir.is_dir(), f"{agents_dir} not found")
        paths = sorted(agents_dir.glob("*.md"))
        self.assertGreater(len(paths), 0, "expected at least one agent file")
        for path in paths:
            errors = caf.check_frontmatter(path, path.read_text().splitlines())
            self.assertEqual(errors, [], f"{path} should be loadable: {errors}")


class NegativeControlTests(unittest.TestCase):
    def test_bare_multiline_example_block_fails(self):
        # The exact todo-229 regression shape: a bare <example> tag at column 0
        # inside a multi-line `description:` block.
        broken = [
            "---",
            "name: broken-agent",
            "description: Use this agent when X.",
            "<example>",
            "Context: something.",
            'user: "do the thing"',
            "assistant: I will do the thing.",
            "</example>",
            "model: sonnet",
            "---",
        ]
        errors = caf.check_frontmatter(Path("broken-agent.md"), broken)
        self.assertTrue(errors, "expected the bare <example> block to be rejected")
        self.assertTrue(
            any(":4:" in e for e in errors),
            f"expected an error pointing at line 4, got: {errors}",
        )

    def test_missing_closing_delimiter_fails(self):
        broken = ["---", "name: x", "description: y"]
        errors = caf.check_frontmatter(Path("no-close.md"), broken)
        self.assertTrue(errors)

    def test_missing_required_key_fails(self):
        broken = ["---", "name: x", "model: sonnet", "---"]
        errors = caf.check_frontmatter(Path("no-description.md"), broken)
        self.assertTrue(any("description" in e for e in errors))

    def test_blank_line_in_frontmatter_fails(self):
        broken = ["---", "name: x", "", "description: y", "---"]
        errors = caf.check_frontmatter(Path("blank-line.md"), broken)
        self.assertTrue(any(":3:" in e for e in errors))

    def test_empty_file_fails_cleanly(self):
        # Must not raise IndexError on lines[0] — covers the `not lines` operand
        # of the line-29 `or` guard (deleting it would crash instead of erroring).
        errors = caf.check_frontmatter(Path("empty.md"), [])
        self.assertTrue(errors)

    def test_no_opening_delimiter_fails_cleanly(self):
        broken = ["# Just a heading", "some text, no frontmatter at all"]
        errors = caf.check_frontmatter(Path("no-frontmatter.md"), broken)
        self.assertTrue(errors)


class SubprocessTests(unittest.TestCase):
    """Drives the real script end-to-end — the pre-commit hook depends on its
    process exit code, which PositiveControlTests/NegativeControlTests never
    exercise (they call check_frontmatter() directly). Mirrors
    test_route_domains.py's SubprocessTests pattern."""

    SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_agent_frontmatter.py")

    def _run_with_agents_dir(self, agents_dir):
        code = (
            "import sys; sys.path.insert(0, %r); "
            "import check_agent_frontmatter as caf; "
            "from pathlib import Path; caf.AGENTS_DIR = Path(%r); "
            "sys.exit(caf.main())" % (os.path.dirname(self.SCRIPT), str(agents_dir))
        )
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    def test_real_repo_passes(self):
        r = subprocess.run([sys.executable, self.SCRIPT], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_broken_fixture_fails_with_offending_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.md"
            broken.write_text("---\nname: x\ndescription: y\n<example>\n</example>\n---\n")
            r = self._run_with_agents_dir(tmp)
            self.assertEqual(r.returncode, 1)
            self.assertIn("broken.md:4", r.stderr)

    def test_missing_agents_dir_fails(self):
        r = self._run_with_agents_dir("/nonexistent/agents/dir")
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
