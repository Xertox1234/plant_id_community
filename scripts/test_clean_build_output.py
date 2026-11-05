#!/usr/bin/env python3
"""Tests for scripts/clean_build_output.py (todo 697).

Run: python3 scripts/test_clean_build_output.py
Also run by .github/workflows/harness-ci.yml.

Every case runs against a temp build root and fake worktrees whose
``plant_community_mobile/build`` links point into it. Nothing touches U34Bolt.
"""

from __future__ import annotations

import io
import os
import pathlib
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import clean_build_output as cbo  # noqa: E402

DAY = 86400.0
NOW = time.time()


def age(path: pathlib.Path, days: float) -> None:
    """Set the mtime of ``path`` and everything under it to ``days`` ago."""
    t = NOW - days * DAY
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        for name in dirnames + filenames:
            os.utime(os.path.join(dirpath, name), (t, t), follow_symlinks=False)
    os.utime(path, (t, t), follow_symlinks=False)


class Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self._tmp.name)
        self.root = self.base / "build"
        self.root.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def entry(self, name: str, days: float = 10, size: int = 1024) -> pathlib.Path:
        d = self.root / name
        (d / "ios").mkdir(parents=True)
        (d / "ios" / "app.bin").write_bytes(b"x" * size)
        age(d, days)
        return d

    def worktree(self, name: str, target: pathlib.Path) -> str:
        wt = self.base / "worktrees" / name
        (wt / "plant_community_mobile").mkdir(parents=True)
        os.symlink(target, wt / "plant_community_mobile" / "build")
        return str(wt)

    def run_main(self, *argv: str, worktrees: list[str] | None = None) -> tuple[int, str]:
        out = io.StringIO()
        code = cbo.main(
            ["--root", str(self.root), *argv],
            worktrees=[] if worktrees is None else worktrees,
            now=NOW,
            out=out,
        )
        return code, out.getvalue()


class DryRunTests(Fixture):
    def test_lists_orphans_with_size_and_deletes_nothing(self):
        self.entry("scan2-c", size=1024 * 1024)
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertRegex(out, r"orphan 1\.0 MB \d{4}-\d\d-\d\d \d\d:\d\d scan2-c")
        self.assertIn("Orphans: 1,", out)
        self.assertIn("Dry run: nothing deleted.", out)
        self.assertTrue((self.root / "scan2-c").exists())

    def test_live_entry_is_reported_live(self):
        live = self.entry("g1")
        wt = self.worktree("g1", live)
        code, out = self.run_main(worktrees=[wt])
        self.assertEqual(code, 0)
        self.assertIn("live ", out)
        self.assertIn("Orphans: 0,", out)


class ApplyTests(Fixture):
    def test_apply_deletes_old_orphan_and_keeps_live_and_young(self):
        old = self.entry("testflight-18", days=10)
        young = self.entry("fresh", days=0.5)
        live = self.entry("g1", days=30)
        wt = self.worktree("g1", live)
        code, out = self.run_main("--apply", worktrees=[wt])
        self.assertEqual(code, 0, out)
        self.assertFalse(old.exists())
        self.assertTrue(young.exists(), "an orphan younger than --min-age was deleted")
        self.assertTrue(live.exists(), "an entry a live worktree uses was deleted")
        self.assertIn("deleted testflight-18", out)
        self.assertIn("kept   fresh", out)

    def test_live_entry_is_never_deleted_even_with_min_age_zero(self):
        live = self.entry("g1", days=365)
        wt = self.worktree("g1", live)
        code, _ = self.run_main("--apply", "--min-age", "0", worktrees=[wt])
        self.assertEqual(code, 0)
        self.assertTrue(live.exists())

    def test_link_into_a_subfolder_keeps_the_whole_entry(self):
        live = self.entry("g2", days=365)
        wt = self.worktree("g2", live / "ios")
        self.run_main("--apply", "--min-age", "0", worktrees=[wt])
        self.assertTrue(live.exists())

    def test_link_at_the_root_itself_keeps_everything(self):
        a = self.entry("a", days=365)
        wt = self.worktree("whole", self.root)
        self.run_main("--apply", "--min-age", "0", worktrees=[wt])
        self.assertTrue(a.exists())

    def test_min_age_is_respected(self):
        e = self.entry("five-days", days=5)
        self.run_main("--apply", "--min-age", "7")
        self.assertTrue(e.exists())
        self.run_main("--apply", "--min-age", "4")
        self.assertFalse(e.exists())

    def test_newest_file_inside_decides_age(self):
        e = self.entry("still-building", days=30)
        t = NOW - 0.1 * DAY
        os.utime(e / "ios" / "app.bin", (t, t))
        self.run_main("--apply")
        self.assertTrue(e.exists())

    def test_unreadable_worktree_list_deletes_nothing(self):
        e = self.entry("orphan", days=30)
        out = io.StringIO()
        with mock.patch.object(cbo, "git_worktrees", side_effect=OSError("no git")):
            code = cbo.main(["--root", str(self.root), "--apply"], now=NOW, out=out)
        self.assertEqual(code, 1)
        self.assertTrue(e.exists())


class SymlinkTests(Fixture):
    def test_symlink_inside_an_orphan_is_removed_not_followed(self):
        outside = self.base / "precious"
        outside.mkdir()
        (outside / "keep.txt").write_text("do not delete")
        orphan = self.entry("orphan", days=30)
        os.symlink(outside, orphan / "ios" / "escape")
        os.symlink(outside / "keep.txt", orphan / "file-link")
        age(orphan, 30)
        code, out = self.run_main("--apply")
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.lexists(orphan))
        self.assertTrue((outside / "keep.txt").exists(), "rmtree followed a symlink")
        self.assertEqual((outside / "keep.txt").read_text(), "do not delete")

    def test_top_level_symlink_is_unlinked_not_followed(self):
        outside = self.base / "elsewhere"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep")
        link = self.root / "stray-link"
        os.symlink(outside, link)
        os.utime(link, (NOW - 30 * DAY,) * 2, follow_symlinks=False)
        code, out = self.run_main("--apply")
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.lexists(link))
        self.assertTrue((outside / "keep.txt").exists())

    def test_size_does_not_count_a_linked_target(self):
        big = self.base / "big"
        big.mkdir()
        (big / "blob").write_bytes(b"x" * 5 * 1024 * 1024)
        orphan = self.entry("orphan", size=10)
        os.symlink(big, orphan / "link")
        size, _ = cbo.measure(orphan)
        self.assertLess(size, 1024 * 1024)

    def test_delete_refuses_a_path_outside_the_root(self):
        other = self.base / "other"
        other.mkdir()
        with self.assertRaises(ValueError):
            cbo.delete(self.root, other)
        self.assertTrue(other.exists())


class NoOpTests(Fixture):
    def test_missing_root_exits_zero_and_changes_nothing(self):
        before = sorted(os.listdir(self.base))
        out = io.StringIO()
        code = cbo.main(
            ["--root", str(self.base / "missing"), "--apply"], worktrees=[], now=NOW, out=out
        )
        self.assertEqual(code, 0)
        self.assertIn("does not exist; nothing to do.", out.getvalue())
        self.assertEqual(sorted(os.listdir(self.base)), before)

    def test_unmounted_drive_exits_zero_and_changes_nothing(self):
        e = self.entry("orphan", days=30)
        out = io.StringIO()
        with mock.patch.object(cbo, "is_mounted", return_value=False) as m:
            code = cbo.main(
                ["--root", str(self.root), "--mount", "/Volumes/U34Bolt", "--apply"],
                worktrees=[],
                now=NOW,
                out=out,
            )
        m.assert_called_once_with("/Volumes/U34Bolt")
        self.assertEqual(code, 0)
        self.assertIn("is not mounted; nothing to do.", out.getvalue())
        self.assertTrue(e.exists())

    def test_default_root_checks_the_mount(self):
        out = io.StringIO()
        with mock.patch.object(cbo, "is_mounted", return_value=False) as m:
            code = cbo.main(["--apply"], worktrees=[], now=NOW, out=out)
        m.assert_called_once_with(cbo.MOUNT)
        self.assertEqual(code, 0)

    def test_is_mounted_reads_df_mount_column(self):
        # A plain directory on the system disk is not its own mount point.
        self.assertFalse(cbo.is_mounted(str(self.root)))
        self.assertTrue(cbo.is_mounted("/"))


class TmpReportTests(Fixture):
    def test_tmp_reports_old_entries_and_deletes_nothing(self):
        tmp = self.base / "tmp"
        tmp.mkdir()
        old = tmp / "TemporaryDirectory.abc"
        old.mkdir()
        age(old, 30)
        new = tmp / "today.log"
        new.write_text("log")
        code, out = self.run_main("--apply", "--tmp", "--tmp-root", str(tmp))
        self.assertEqual(code, 0)
        self.assertIn("tmp-old", out)
        self.assertIn("TemporaryDirectory.abc", out)
        self.assertNotIn("today.log", out)
        self.assertTrue(old.exists())
        self.assertTrue(new.exists())


class LiveTargetTests(unittest.TestCase):
    def test_git_worktrees_parses_porcelain(self):
        porcelain = "worktree /a\nHEAD 1\nbranch refs/heads/main\n\nworktree /b c\nHEAD 2\ndetached\n"
        with mock.patch.object(cbo.subprocess, "run") as run:
            run.return_value.stdout = porcelain
            self.assertEqual(cbo.git_worktrees("/repo"), ["/a", "/b c"])

    def test_real_repo_lists_this_checkout(self):
        repo = pathlib.Path(__file__).resolve().parent.parent
        paths = [os.path.realpath(p) for p in cbo.git_worktrees(str(repo))]
        self.assertIn(os.path.realpath(repo), paths)


if __name__ == "__main__":
    unittest.main(verbosity=2)
