#!/usr/bin/env python3
"""Tests for the `# log-prefix: exempt` rule in scripts/check_log_prefixes.py,
and for scripts/add_log_prefixes.py honouring it (todo 573).

Run: python3 scripts/test_check_log_prefixes.py
Also run by .github/workflows/harness-ci.yml.

The rule: the mark exempts a call when it is in a comment on one of the
call's own lines, or in a comment-only line directly above it. Nothing else:
not a trailing comment on the line above (that belongs to another
statement), not a mark two lines up, and not a `#` inside a string.
"""

from __future__ import annotations

import ast
import pathlib
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import add_log_prefixes as alp  # noqa: E402
import check_log_prefixes as clp  # noqa: E402


def _exempt(source: str) -> list[bool]:
    """is_exempt for every logger call in ``source``, in line order."""
    source = textwrap.dedent(source)
    marks = clp.exempt_marks(source)
    calls = sorted(
        (
            n
            for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.Call) and clp.logger_level(n)
        ),
        key=lambda n: n.lineno,
    )
    return [clp.is_exempt(marks, c) for c in calls]


class IsExemptTest(unittest.TestCase):
    def test_a_comment_only_line_directly_above_exempts(self):
        self.assertEqual(
            _exempt(
                """
                # log-prefix: exempt (relayed command output)
                logger.info("%s", line)
                """
            ),
            [True],
        )

    def test_a_mark_on_the_calls_own_line_exempts(self):
        self.assertEqual(
            _exempt('logger.info("%s", line)  # log-prefix: exempt (relay)\n'),
            [True],
        )

    def test_a_mark_on_a_continuation_line_exempts(self):
        self.assertEqual(
            _exempt(
                """
                logger.info(
                    "%s",  # log-prefix: exempt (relay)
                    line,
                )
                """
            ),
            [True],
        )

    def test_a_trailing_mark_on_the_line_above_does_not(self):
        self.assertEqual(
            _exempt(
                """
                x = 1  # log-prefix: exempt
                logger.info("unprefixed")
                """
            ),
            [False],
        )

    def test_a_single_line_calls_mark_does_not_leak_to_the_next_call(self):
        self.assertEqual(
            _exempt(
                """
                logger.info("%s", line)  # log-prefix: exempt (relay)
                logger.info("unprefixed")
                """
            ),
            [True, False],
        )

    def test_a_mark_two_lines_up_does_not(self):
        self.assertEqual(
            _exempt(
                """
                # log-prefix: exempt
                x = 1
                logger.info("unprefixed")
                """
            ),
            [False],
        )

    def test_no_mark_nearby(self):
        self.assertEqual(_exempt('logger.info("unprefixed")\n'), [False])

    def test_a_hash_in_a_string_neither_fakes_nor_hides_the_mark(self):
        self.assertEqual(
            _exempt(
                """
                logger.info("#log-prefix: exempt %s", x)
                logger.info("#%s", x)  # log-prefix: exempt (relay)
                """
            ),
            [False, True],
        )


class AddLogPrefixesTest(unittest.TestCase):
    def _rewrite(self, source: str) -> tuple[str, int]:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "mod.py"
            path.write_text(textwrap.dedent(source), encoding="utf-8")
            return alp.rewrite(path, "[EMAIL]")

    def test_an_exempt_relay_line_is_not_prefixed(self):
        new, count = self._rewrite(
            """
            # log-prefix: exempt (relayed command output, already prefixed)
            logger.info("%s (task=%s)", line, task_id)
            logger.info("sent the digest")
            """
        )
        self.assertEqual(count, 1)
        self.assertIn('logger.info("%s (task=%s)", line, task_id)', new)
        self.assertIn('logger.info("[EMAIL] sent the digest")', new)


if __name__ == "__main__":
    unittest.main()
