#!/usr/bin/env python3
"""Tests for scripts/todos/slot_env.py.

Run: python3 scripts/todos/test_slot_env.py (also run by harness-ci.yml).

Two concurrent backend test runs sharing one database produce fake failures
(memory: project_reuse_db_wagtail_root_truncation). These pin that each slot
gets its own database and Redis DB, and that nothing leaks into .env.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slot_env as se  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        FAILURES.append(label)


DOTENV = (
    "# comment\nSECRET_KEY=abc\nDATABASE_URL='postgresql://u:p@localhost:5432/plant_community?sslmode=disable'\n"
    "export REDIS_URL=redis://127.0.0.1:6379/1\n"
)


def main():
    parsed = se.parse_dotenv(DOTENV)
    check("parse_dotenv strips quotes and export", parsed["REDIS_URL"] == "redis://127.0.0.1:6379/1"
          and parsed["DATABASE_URL"].startswith("postgresql://"), parsed)

    env = se.slot_env({"PATH": "/bin"}, DOTENV, 2, "/wt/g1")
    check("slot 2 gets its own database",
          env["DATABASE_URL"] == "postgresql://u:p@localhost:5432/plant_community_w2?sslmode=disable", env)
    check("slot 2 gets Redis DB 11", env["REDIS_URL"] == "redis://127.0.0.1:6379/11")
    check("PYTHONPATH puts the worktree's wagtail_forum first",
          env["PYTHONPATH"] == "/wt/g1/backend/packages/wagtail_forum")
    check("other variables pass through", env["PATH"] == "/bin")
    check("SWEEP_SLOT is set", env["SWEEP_SLOT"] == "2")

    env = se.slot_env({"DATABASE_URL": "postgres://h/plant_community_w5", "PYTHONPATH": "/x"}, DOTENV, 3, "/wt")
    check("an environment DATABASE_URL wins and is re-slotted", env["DATABASE_URL"] == "postgres://h/plant_community_w3")
    check("an existing PYTHONPATH is kept after ours", env["PYTHONPATH"] == f"/wt/backend/packages/wagtail_forum{os.pathsep}/x")

    for bad in (0, 7):
        try:
            se.slot_env({}, DOTENV, bad, "/wt")
            raised = False
        except ValueError:
            raised = True
        check(f"slot {bad} is refused", raised)
    try:
        se.slot_env({}, "SECRET_KEY=x\n", 1, "/wt")
        raised = False
    except ValueError:
        raised = True
    check("no DATABASE_URL anywhere is refused, not defaulted", raised)
    check("Redis defaults to localhost when unset",
          se.slot_env({}, "DATABASE_URL=postgres://h/db\n", 1, "/wt")["REDIS_URL"] == "redis://127.0.0.1:6379/10")

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
