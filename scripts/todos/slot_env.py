#!/usr/bin/env python3
"""Run a command with one todo-sweep worker slot's test resources.

    python3 <worktree>/scripts/todos/slot_env.py <slot> -- <command> [args...]

Slot N (1..6) gets its own Postgres database -- pytest then creates
test_plant_community_wN -- and Redis DB 9+N, so the six slots of two
overlapping waves never share test state (spec §7.3). Values are set in the
process environment only, never written to .env: python-decouple lets the
environment win over backend/.env, which the worktree has via
.worktreeinclude. PYTHONPATH puts this worktree's wagtail_forum ahead of the
main checkout's editable install, which otherwise gets collected twice.
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

MAX_SLOT = 6  # Redis DBs 10..15; dev uses 1 and 3
DEFAULT_REDIS = "redis://127.0.0.1:6379/1"


def parse_dotenv(text):
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        values[key] = value.strip().strip("'\"")
    return values


def slot_env(environ, dotenv_text, slot, worktree):
    if not 1 <= slot <= MAX_SLOT:
        raise ValueError(f"slot must be 1..{MAX_SLOT}, got {slot}")
    dotenv = parse_dotenv(dotenv_text)
    db_url = environ.get("DATABASE_URL") or dotenv.get("DATABASE_URL")
    if not db_url:
        raise ValueError("no DATABASE_URL in the environment or backend/.env")
    redis_url = environ.get("REDIS_URL") or dotenv.get("REDIS_URL") or DEFAULT_REDIS
    env = dict(environ)
    env["DATABASE_URL"] = urlunsplit(urlsplit(db_url)._replace(path=f"/plant_community_w{slot}"))
    env["REDIS_URL"] = urlunsplit(urlsplit(redis_url)._replace(path=f"/{9 + slot}"))
    forum = str(Path(worktree) / "backend" / "packages" / "wagtail_forum")
    env["PYTHONPATH"] = forum + (os.pathsep + environ["PYTHONPATH"] if environ.get("PYTHONPATH") else "")
    env["SWEEP_SLOT"] = str(slot)
    return env


def main(argv):
    if len(argv) < 4 or argv[2] != "--" or not argv[1].isdigit():
        print(__doc__, file=sys.stderr)
        return 2
    worktree = Path(__file__).resolve().parents[2]
    dotenv = worktree / "backend" / ".env"
    try:
        env = slot_env(dict(os.environ), dotenv.read_text() if dotenv.is_file() else "", int(argv[1]), worktree)
    except ValueError as exc:
        print(f"slot_env: {exc}", file=sys.stderr)
        return 2
    os.execvpe(argv[3], argv[3:], env)
    return 127  # not reached


if __name__ == "__main__":
    sys.exit(main(sys.argv))
