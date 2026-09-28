#!/usr/bin/env python3
"""Tests for scripts/todos/slot_env.py.

Run: python3 scripts/todos/test_slot_env.py (also run by harness-ci.yml).

Two concurrent backend test runs sharing one database produce fake failures
(memory: project_reuse_db_wagtail_root_truncation). These pin that each slot
gets its own database and Redis DB, and that nothing leaks into .env.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slot_env as se  # noqa: E402

FAILURES = []


def NO_SOCKETS(path):  # the TCP checks must not depend on this machine's /tmp
    return False


def sockets(*present):
    return lambda path: path in present


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

    env = se.slot_env({"PATH": "/bin"}, DOTENV, 2, "/wt/g1", exists=NO_SOCKETS)
    check("slot 2 gets its own database",
          env["DATABASE_URL"] == "postgresql://u:p@localhost:5432/plant_community_w2?sslmode=disable", env)
    check("slot 2 gets Redis DB 11", env["REDIS_URL"] == "redis://127.0.0.1:6379/11")
    check("PYTHONPATH puts the worktree's wagtail_forum first",
          env["PYTHONPATH"] == "/wt/g1/backend/packages/wagtail_forum")
    check("other variables pass through", env["PATH"] == "/bin")
    check("SWEEP_SLOT is set", env["SWEEP_SLOT"] == "2")

    env = se.slot_env({"DATABASE_URL": "postgres://h/plant_community_w5", "PYTHONPATH": "/x"}, DOTENV, 3, "/wt", exists=NO_SOCKETS)
    check("an environment DATABASE_URL wins and is re-slotted", env["DATABASE_URL"] == "postgres://h/plant_community_w3")
    check("an existing PYTHONPATH is kept after ours", env["PYTHONPATH"] == f"/wt/backend/packages/wagtail_forum{os.pathsep}/x")

    for bad in (0, 7):
        try:
            se.slot_env({}, DOTENV, bad, "/wt", exists=NO_SOCKETS)
            raised = False
        except ValueError:
            raised = True
        check(f"slot {bad} is refused", raised)
    try:
        se.slot_env({}, "SECRET_KEY=x\n", 1, "/wt", exists=NO_SOCKETS)
        raised = False
    except ValueError:
        raised = True
    check("no DATABASE_URL anywhere is refused, not defaulted", raised)
    check("Redis defaults to localhost when unset",
          se.slot_env({}, "DATABASE_URL=postgres://h/db\n", 1, "/wt", exists=NO_SOCKETS)["REDIS_URL"] == "redis://127.0.0.1:6379/10")

    # Pilot 2026-09-28: .worktreeinclude delivered no backend/.env to either harness worktree,
    # so python-decouple had nothing to read. The main checkout's values come in as process env.
    env = se.slot_env({"PATH": "/bin"}, DOTENV, 1, "/wt", exists=NO_SOCKETS)
    check("a worktree's own .env is not copied into the environment", "SECRET_KEY" not in env, env)
    env = se.slot_env({"PATH": "/bin", "DEBUG": "False"}, DOTENV + "DEBUG=True\nALLOWED_HOSTS=x\n", 1, "/wt",
                      inherit_dotenv=True, exists=NO_SOCKETS)
    check("an inherited .env reaches the environment", env.get("ALLOWED_HOSTS") == "x", env)
    check("an inherited .env never overrides the environment", env["DEBUG"] == "False", env)
    check("an inherited DATABASE_URL is still re-slotted",
          env["DATABASE_URL"] == "postgresql://u:p@localhost:5432/plant_community_w1?sslmode=disable", env)

    # The sandbox blocks loopback TCP but can allow a listed Unix socket (todo 469), so a local
    # service whose socket file exists is reached through it.
    both = sockets("/tmp/.s.PGSQL.5432", "/tmp/redis.sock")
    env = se.slot_env({}, DOTENV, 2, "/wt", exists=both)
    check("local Postgres with a socket uses it, keeping user and slot",
          env["DATABASE_URL"] == "postgresql://u:p@%2Ftmp:5432/plant_community_w2?sslmode=disable", env)
    check("local Redis with a socket uses it on the slot's DB", env["REDIS_URL"] == "unix:///tmp/redis.sock?db=11", env)
    check("Celery gets its own socket form", env["CELERY_BROKER_URL"] == "redis+socket:///tmp/redis.sock?virtual_host=11",
          env)
    env = se.slot_env({"DATABASE_URL": "postgres://localhost/x"}, "", 1, "/wt", exists=both)
    check("a URL with no user or port becomes a bare socket host",
          env["DATABASE_URL"] == "postgres://%2Ftmp/plant_community_w1", env)
    env = se.slot_env({"DATABASE_URL": "postgres://127.0.0.1:5433/x"}, "", 1, "/wt", exists=both)
    check("the socket file follows the URL's port", env["DATABASE_URL"] == "postgres://127.0.0.1:5433/plant_community_w1",
          env)
    env = se.slot_env({"DATABASE_URL": "postgres://db.example.com/x", "REDIS_URL": "redis://cache.example.com:6379/1"},
                      "", 1, "/wt", exists=both)
    check("a remote Postgres stays on TCP", env["DATABASE_URL"] == "postgres://db.example.com/plant_community_w1", env)
    check("a remote Redis stays on TCP and sets no broker",
          env["REDIS_URL"] == "redis://cache.example.com:6379/10" and "CELERY_BROKER_URL" not in env, env)
    env = se.slot_env({}, DOTENV, 1, "/wt", exists=sockets("/tmp/.s.PGSQL.5432"))
    check("no Redis socket file: Redis stays on TCP",
          env["REDIS_URL"] == "redis://127.0.0.1:6379/10" and "CELERY_BROKER_URL" not in env, env)
    env = se.slot_env({"REDIS_URL": "redis://:pw@localhost:6379/1"}, DOTENV, 1, "/wt", exists=both)
    check("a Redis URL with a password stays on TCP", env["REDIS_URL"] == "redis://:pw@localhost:6379/10", env)
    env = se.slot_env({"CELERY_BROKER_URL": "redis://elsewhere/2"}, DOTENV, 1, "/wt", exists=both)
    check("an explicit CELERY_BROKER_URL is kept", env["CELERY_BROKER_URL"] == "redis://elsewhere/2", env)

    with tempfile.TemporaryDirectory() as tmp:
        main_root, wt = Path(tmp) / "main", Path(tmp) / "wt"
        (main_root / "backend").mkdir(parents=True)
        (wt / "backend").mkdir(parents=True)
        (main_root / "backend" / ".env").write_text("DATABASE_URL=postgres://h/main\n")
        path, inherited = se.dotenv_path(wt, main_root)
        check("a worktree without backend/.env reads the main checkout's",
              path == main_root / "backend" / ".env" and inherited, (path, inherited))
        (wt / "backend" / ".env").write_text("DATABASE_URL=postgres://h/wt\n")
        path, inherited = se.dotenv_path(wt, main_root)
        check("a worktree's own backend/.env wins", path == wt / "backend" / ".env" and not inherited,
              (path, inherited))
        path, inherited = se.dotenv_path(wt, wt)
        check("the main checkout itself never inherits from itself", not inherited, (path, inherited))

    # End to end through a real `git worktree add` (review round 1 of PR #864): the flag must reach
    # slot_env, and main_checkout must name the main checkout from either side, whatever the cwd.
    with tempfile.TemporaryDirectory() as tmp:
        main_root, wt = Path(tmp) / "main", Path(tmp) / "wt"
        (main_root / "scripts" / "todos").mkdir(parents=True)
        shutil.copy(Path(__file__).with_name("slot_env.py"), main_root / "scripts" / "todos" / "slot_env.py")
        git = ["git", "-c", "user.name=x", "-c", "user.email=x@x", "-C", str(main_root)]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "."], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "init"], check=True)
        subprocess.run(git + ["worktree", "add", "-q", str(wt)], check=True)
        (main_root / "backend").mkdir()
        (main_root / "backend" / ".env").write_text("DATABASE_URL=postgres://h/main\nFOO=bar\n")

        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            check("main_checkout names the main checkout from a worktree",
                  se.main_checkout(wt).resolve() == main_root.resolve(), se.main_checkout(wt))
            check("main_checkout names the main checkout from itself, cwd elsewhere",
                  se.main_checkout(main_root).resolve() == main_root.resolve(), se.main_checkout(main_root))
        finally:
            os.chdir(cwd)

        out = subprocess.run(
            [sys.executable, str(wt / "scripts" / "todos" / "slot_env.py"), "1", "--", sys.executable, "-c",
             "import os; print(os.environ.get('FOO'), os.environ['DATABASE_URL'])"],
            capture_output=True, text=True, env={k: v for k, v in os.environ.items()
                                                 if k not in ("FOO", "DATABASE_URL")})
        check("a worktree without backend/.env runs with the main checkout's values",
              out.stdout.split() == ["bar", "postgres://h/plant_community_w1"], (out.stdout, out.stderr))

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
