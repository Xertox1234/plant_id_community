#!/usr/bin/env python3
"""Tests for budget_rules.excerpt() -- the never-head-only property (todo 391).

Run: python3 scripts/inject/test_budget_rules.py

The hook-level properties (tail kept at every real share, share never exceeded,
sentinel reaches the edit) live in `.claude/hooks/test-inject-patterns.sh`.
This file pins a shape those cannot reach with today's rule files: a final line
longer than the tail's share of the split.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import budget_rules as br  # noqa: E402

SPLIT_MARKER = "skipped to fit the injection"


def long_final_line_file(final_line_bytes=2000):
    """Many short rules, then one rule longer than any tail share below."""
    return "# Rules\n" + "- a short rule\n" * 80 + "- " + "x" * final_line_bytes + "\n"


class NeverHeadOnlyTests(unittest.TestCase):
    """A head-only excerpt is the append-only bias budget_rules exists to remove.

    Review round 2 of #750: when the tail's share lands inside the file's final
    line, `boundary_after()` returns `len(text)`, the tail is empty, and the
    split branch returned head + marker + nothing. The tail-only branch already
    refused that shape; the split branch did not.
    """

    def test_split_branch_never_emits_head_only(self):
        text = long_final_line_file()
        for share in (1200, 1500, 1800):
            with self.subTest(share=share):
                out = br.excerpt(text, share, "docs/rules/x.md")
                self.assertFalse(
                    SPLIT_MARKER in out and out.endswith("...]\n\n"),
                    f"head-only excerpt at share {share}: {out[-120:]!r}",
                )
                # Either nothing, or something that ends where the file ends.
                self.assertTrue(
                    out == "" or text.endswith(out[-40:]),
                    f"excerpt does not carry the file's tail at share {share}",
                )
                self.assertLessEqual(len(out.encode("utf-8")), share)

    def test_control_an_ordinary_file_still_splits(self):
        # Without this, a fix that made excerpt() always return "" would pass
        # the test above.
        text = "# Rules\n" + "".join(f"- rule number {i}\n" for i in range(200))
        out = br.excerpt(text, 1500, "docs/rules/x.md")
        self.assertIn(SPLIT_MARKER, out)
        self.assertTrue(out.startswith("# Rules\n"))
        self.assertTrue(out.endswith("- rule number 199\n"))


if __name__ == "__main__":
    unittest.main()
