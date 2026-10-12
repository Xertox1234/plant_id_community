#!/usr/bin/env python3
"""Tests for budget_rules.excerpt() -- the never-head-only property (todo 391).

Run: python3 scripts/inject/test_budget_rules.py

The hook-level properties (tail kept at every real share, share never exceeded,
sentinel reaches the edit) live in `.claude/hooks/test-inject-patterns.sh`.
This file pins a shape those cannot reach with today's rule files: a final line
longer than the tail's share of the split.
"""
import os
import re
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

    def test_a_final_rule_ending_in_a_blank_line_is_not_head_only(self):
        # PR #822: boundary_after() stops on the trailing "\n\n", so the tail
        # was a lone "\n" and `tail_start >= len(text)` missed it.
        text = "# Rules\n" + "- a short rule\n" * 80 + "- " + "x" * 2000 + "\n\n"
        for share in (1200, 1500, 1800):
            with self.subTest(share=share):
                out = br.excerpt(text, share, "docs/rules/x.md")
                self.assertFalse(
                    SPLIT_MARKER in out and not out.split("...]")[-1].strip(),
                    f"head-only excerpt at share {share}: {out[-120:]!r}",
                )

    def test_control_an_ordinary_file_still_splits(self):
        # Without this, a fix that made excerpt() always return "" would pass
        # the test above.
        text = "# Rules\n" + "".join(f"- rule number {i}\n" for i in range(200))
        out = br.excerpt(text, 1500, "docs/rules/x.md")
        self.assertIn(SPLIT_MARKER, out)
        self.assertTrue(out.startswith("# Rules\n"))
        self.assertTrue(out.endswith("- rule number 199\n"))


class EveryRoutedDomainContributesTests(unittest.TestCase):
    """Todo 440: `tail_only()` returned "" when the final rule was longer than
    the tail room -- `boundary_after()` found no boundary before the end of the
    file -- so a routed domain contributed nothing and no "open the file"
    marker either. It now falls back to a raw mid-line suffix plus the marker.
    """

    def test_a_final_rule_longer_than_the_tail_room_still_contributes(self):
        text = long_final_line_file()
        # Below MIN_SPLIT, so tail_only() runs directly; and the split
        # branch's own fallbacks at the shares the older test uses.
        for share in (300, 450, 600, 1200, 1500, 1800):
            with self.subTest(share=share):
                out = br.excerpt(text, share, "docs/rules/x.md")
                self.assertNotEqual(out, "", f"domain vanished at share {share}")
                self.assertIn("were not injected", out)
                self.assertTrue(text.endswith(out.split("...]\n\n")[-1]))
                self.assertTrue(out.endswith("x\n"))
                self.assertLessEqual(len(out.encode("utf-8")), share)

    def test_a_share_below_the_marker_cost_never_exceeds_it(self):
        # The marker alone is ~150 B; a share below that cannot carry it.
        # Pinned so the fallback never trades the byte cap for "something".
        text = long_final_line_file()
        for share in (1, 40, 120):
            with self.subTest(share=share):
                out = br.excerpt(text, share, "docs/rules/x.md")
                self.assertLessEqual(len(out.encode("utf-8")), share)

    def test_tail_only_returns_empty_only_below_the_marker_cost(self):
        # Todo 490: `tail_only()` documents that it returns "" ONLY when the
        # share cannot carry the marker itself -- 137-139 B for this file. The
        # byte cap above cannot tell "" from a bare suffix with no marker, so
        # the empty return is pinned here, and a share just past the marker is
        # the control that it is the exception rather than the rule.
        text = long_final_line_file()
        for share in (1, 40, 120):
            with self.subTest(share=share):
                self.assertEqual(br.excerpt(text, share, "docs/rules/x.md"), "")
        out = br.excerpt(text, 200, "docs/rules/x.md")
        self.assertIn("were not injected", out)
        self.assertTrue(out.endswith("x\n"))

    def test_tail_only_empty_edge_is_exactly_the_marker_cost(self):
        # Todo 555 (finding 8): the loose bracket above (1/40/120 vs 200) let a
        # 50 B over-reservation for the marker pass -- empty up to share 189.
        # Todo 589 (finding 7): the edges are DERIVED from the marker, not
        # pinned as literals, so a wording change moves them with it. The
        # marker is reserved at the whole file's size, so its cost is the
        # marker read off a real excerpt with the skipped count replaced by
        # the file's byte count. Not found by scanning shares for the first
        # non-empty output: an over-reservation would just move that edge.
        # Todo 609 (PR #1055 findings 3-5): the marker is measured, not
        # parsed. An excerpt is the marker followed by a suffix of the file,
        # and the fixture's last line is all "x", so the suffix is the longest
        # run the excerpt shares with the file's end (the marker ends in a
        # newline, never an "x"). No marker wording is read or asserted here;
        # `test_tail_only_returns_empty_only_below_the_marker_cost` pins that.
        text = long_final_line_file()
        path = "docs/rules/x.md"
        total = len(text.encode("utf-8"))

        def split(out):
            body = len(os.path.commonprefix([out[::-1], text[::-1]]))
            self.assertGreater(body, 0, f"no file suffix after the marker: {out!r}")
            self.assertLess(body, len(out), f"no marker before the suffix: {out!r}")
            return out[:-body], out[-body:]

        def tail_cost_at(share):
            # The marker prints the skipped count, and the reservation sizes
            # it at the whole file's byte count: swap the digits arithmetically.
            out = br.excerpt(text, share, path)
            head, body = split(out)
            skipped = total - len(body.encode("utf-8"))
            return len(head.encode("utf-8")) - len(str(skipped)) + len(str(total))

        # The suffix measure needs the file's last line to be one "x" run
        # longer than every share below: assert it, so a fixture change fails
        # here by name rather than as an odd split.
        self.assertTrue(text.endswith("x" * 300 + "\n"), text[-40:])

        # The marker also prints the share, so measure again just past each
        # estimate until two measurements at DIFFERENT shares agree: that cost
        # is the edge's, whatever share digits the wording carries. Todo 633
        # (finding 3): the old re-measure repeated the call that set the cost,
        # so it could not fail. The edge assertions after the loop are what
        # catch a wrong cost: off by one digit, "" moves or at_edge's size does.
        tail_cost = tail_cost_at(200)
        for _ in range(3):
            remeasured = tail_cost_at(tail_cost + 1)
            if remeasured == tail_cost:
                break
            tail_cost = remeasured
        else:
            self.fail(f"the marker cost never settled: last {tail_cost}")
        self.assertEqual(br.excerpt(text, tail_cost, path), "")
        at_edge = br.excerpt(text, tail_cost + 1, path)
        self.assertEqual(len(at_edge.encode("utf-8")), tail_cost + 1, at_edge)
        self.assertEqual(split(at_edge)[1], text[-1:], at_edge)
        # Todo 633 (finding 4): the edge carries the same marker the sibling
        # test reads the wording of at share 200 -- equal once every number
        # (the skipped count and the share) is masked -- so the wording is
        # pinned there and the shape here, without this test reading either.
        self.assertEqual(
            re.sub(r"\d+", "N", split(at_edge)[0]),
            re.sub(r"\d+", "N", split(br.excerpt(text, 200, path))[0]),
        )
        after = br.excerpt(text, tail_cost + 2, path)
        self.assertEqual(split(after)[1], text[-2:], after)


if __name__ == "__main__":
    unittest.main()
