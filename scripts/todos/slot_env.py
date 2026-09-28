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

A worktree with no backend/.env (the 2026-09-28 pilot: .worktreeinclude is read
from the main checkout, which may sit on a branch without it) reads the main
checkout's backend/.env instead, and its values become process environment too,
because python-decouple would otherwise find nothing. Still nothing is written.

The sandbox blocks loopback TCP, so a sandboxed worker cannot reach Postgres or
Redis on localhost (pilot P2/P5; todo 469). It can reach a Unix socket that
`sandbox.network.allowUnixSockets` lists. So when a URL points at this machine
and the service's socket file exists, the slot's URL uses the socket instead:
Postgres through `/tmp/.s.PGSQL.<port>`, Redis through `/tmp/redis.sock`
(`unixsocket` in redis.conf), with Celery's own `redis+socket://` form because
kombu does not read `unix://`. No socket file, or a remote host: TCP, as before.
"""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

MAX_SLOT = 6  # Redis DBs 10..15; dev uses 1 and 3
DEFAULT_REDIS = "redis://127.0.0.1:6379/1"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
PG_SOCKET_DIR = "/tmp"  # Homebrew Postgres' unix_socket_directories
REDIS_SOCKET = "/tmp/redis.sock"


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


def dotenv_path(worktree, main_root):
    """(path, inherited): the worktree's backend/.env, else the main checkout's."""
    own = Path(worktree) / "backend" / ".env"
    if own.is_file() or Path(main_root).resolve() == Path(worktree).resolve():
        return own, False
    return Path(main_root) / "backend" / ".env", True


def main_checkout(worktree):
    common = subprocess.run(["git", "-C", str(worktree), "rev-parse", "--path-format=absolute",
                             "--git-common-dir"], capture_output=True, text=True, check=True)
    return Path(common.stdout.strip()).parent


def pg_socket_url(db_url, exists):
    """db_url with its host swapped for the local Postgres socket directory, when there is one."""
    parts = urlsplit(db_url)
    if parts.hostname not in LOCAL_HOSTS or not exists(f"{PG_SOCKET_DIR}/.s.PGSQL.{parts.port or 5432}"):
        return db_url
    userinfo, at, _ = parts.netloc.rpartition("@")
    host = PG_SOCKET_DIR.replace("/", "%2F") + (f":{parts.port}" if parts.port else "")
    return urlunsplit(parts._replace(netloc=f"{userinfo}{at}{host}"))


def redis_socket_env(redis_url, db, exists):
    """REDIS_URL and CELERY_BROKER_URL on the local Redis socket, or {} to stay on TCP."""
    parts = urlsplit(redis_url)
    if parts.hostname not in LOCAL_HOSTS or parts.password or not exists(REDIS_SOCKET):
        return {}
    return {"REDIS_URL": f"unix://{REDIS_SOCKET}?db={db}",
            "CELERY_BROKER_URL": f"redis+socket://{REDIS_SOCKET}?virtual_host={db}"}


def slot_env(environ, dotenv_text, slot, worktree, inherit_dotenv=False, exists=os.path.exists):
    if not 1 <= slot <= MAX_SLOT:
        raise ValueError(f"slot must be 1..{MAX_SLOT}, got {slot}")
    dotenv = parse_dotenv(dotenv_text)
    db_url = environ.get("DATABASE_URL") or dotenv.get("DATABASE_URL")
    if not db_url:
        raise ValueError("no DATABASE_URL in the environment or backend/.env")
    redis_url = environ.get("REDIS_URL") or dotenv.get("REDIS_URL") or DEFAULT_REDIS
    env = dict(environ)
    if inherit_dotenv:
        for key, value in dotenv.items():
            env.setdefault(key, value)
    env["DATABASE_URL"] = urlunsplit(urlsplit(pg_socket_url(db_url, exists))._replace(path=f"/plant_community_w{slot}"))
    env["REDIS_URL"] = urlunsplit(urlsplit(redis_url)._replace(path=f"/{9 + slot}"))
    socket_env = redis_socket_env(redis_url, 9 + slot, exists)
    if env.get("CELERY_BROKER_URL"):  # an explicit broker is the caller's choice
        socket_env.pop("CELERY_BROKER_URL", None)
    env.update(socket_env)
    forum = str(Path(worktree) / "backend" / "packages" / "wagtail_forum")
    env["PYTHONPATH"] = forum + (os.pathsep + environ["PYTHONPATH"] if environ.get("PYTHONPATH") else "")
    env["SWEEP_SLOT"] = str(slot)
    return env


def main(argv):
    if len(argv) < 4 or argv[2] != "--" or not argv[1].isdigit():
        print(__doc__, file=sys.stderr)
        return 2
    worktree = Path(__file__).resolve().parents[2]
    try:
        dotenv, inherited = dotenv_path(worktree, main_checkout(worktree))
    except subprocess.CalledProcessError:
        dotenv, inherited = worktree / "backend" / ".env", False
    try:
        env = slot_env(dict(os.environ), dotenv.read_text() if dotenv.is_file() else "", int(argv[1]), worktree,
                       inherit_dotenv=inherited)
    except ValueError as exc:
        print(f"slot_env: {exc}", file=sys.stderr)
        return 2
    os.execvpe(argv[3], argv[3:], env)
    return 127  # not reached


if __name__ == "__main__":
    sys.exit(main(sys.argv))
