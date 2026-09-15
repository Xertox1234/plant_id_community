#!/usr/bin/env bash
# Railway start command for the web service: Celery worker + gunicorn in ONE container.
#
# Why one container (todo 335 / audit 2026-09-04 H1): five forum tasks are enqueued
# with `.delay()` on shipped request paths, and until 2026-09-05 nothing consumed
# the queue — pushes, reply emails and topic summaries silently never ran. The web
# container is already funded 24/7 with ample headroom (24 vCPU / 24 GB ceilings,
# ~450 MB in use), so a co-located worker costs only its own memory; a second
# service would mean a second copy of ~50 env vars to keep in sync.
#
# Supervision rules (self-test: bin/test-start.sh):
#   * gunicorn exits on its own (any status) -> stop the worker, exit 1. Railway's
#     ON_FAILURE policy restarts the container; the web tier is what matters.
#   * the worker exits on its own (any status, even 0) -> restart it in-container
#     after WORKER_RESTART_DELAY seconds, up to WORKER_MAX_RESTARTS times, while
#     gunicorn keeps serving. Every restart is logged loudly. Past the budget the
#     script exits 1 so the failure escalates to a container restart — a dead
#     worker must never quietly leave gunicorn serving a queue nobody drains (that
#     was exactly the pre-2026-09-05 topology), but one flaky worker crash must not
#     spend Railway's bounded container-restart budget either.
#   * SIGTERM (redeploy, `railway redeploy`) -> forwarded to both children; exit 0
#     once they have stopped. railway.json's drainingSeconds gives the worker's
#     warm shutdown time to finish in-flight tasks before Railway's SIGKILL.
#     (SIGINT is trapped the same way for a local foreground Ctrl-C; the self-test
#     only exercises SIGTERM, which is the only signal Railway sends.)
#
# Overrides (tests and local runs): WEB_CMD, WORKER_CMD, PORT, CELERY_CONCURRENCY,
# WORKER_MAX_RESTARTS, WORKER_RESTART_DELAY.
#
# Needs bash >= 5.1: `wait -n PID...` with a pid LIST only exists from 5.1 — on
# 4.3–5.0 the pids are silently ignored ("wait for any job"), and on 3.2 `-n` is
# an invalid option whose failure would read as "a child exited". The image
# ships 5.2; the guard below refuses to run under anything older.
set -uo pipefail  # no -e: children's non-zero statuses are handled explicitly

if (( BASH_VERSINFO[0] < 5 || (BASH_VERSINFO[0] == 5 && BASH_VERSINFO[1] < 1) )); then
  echo "[start] needs bash >= 5.1 for 'wait -n PID...' (this is bash $BASH_VERSION); refusing to start" >&2
  exit 1
fi

: "${PORT:=8000}"
: "${CELERY_CONCURRENCY:=2}"
: "${WORKER_MAX_RESTARTS:=5}"
: "${WORKER_RESTART_DELAY:=5}"
# -B embeds beat (CELERY_BEAT_SCHEDULE: the weekly forum digest, todo 340)
# in this single worker; the schedule file lives in /tmp so the read-only
# app dir is never written.
WORKER_CMD=${WORKER_CMD:-"celery -A plant_community_backend worker -B --schedule=/tmp/celerybeat-schedule --loglevel=info --concurrency=${CELERY_CONCURRENCY} --max-tasks-per-child=500"}
WEB_CMD=${WEB_CMD:-"gunicorn plant_community_backend.wsgi:application --bind 0.0.0.0:${PORT} --workers 2 --timeout 120"}

worker_pid=""
web_pid=""
stopping=0
log() { echo "[start] $*" >&2; }
stop_children() {
  stopping=1
  kill -TERM "${worker_pid:-}" "${web_pid:-}" 2>/dev/null || true
}
trap stop_children TERM INT

# Each command runs through `bash -c` so an override may carry quotes. For a
# single simple command (the defaults) bash execs it directly, so the pid we
# hold IS gunicorn / celery and SIGTERM reaches them without an intermediary.
start_worker() { bash -c "$WORKER_CMD" & worker_pid=$!; }

finish_stopped() {
  wait "$worker_pid" "$web_pid" 2>/dev/null
  log "stopped on signal; both children exited"
  exit 0
}

# --- Firebase service-account credentials (todo 286) -------------------------
# The Admin SDK takes a FILE PATH (`credentials.Certificate(path)`), so a
# service-account JSON has to exist in the container. It must never be
# committed — this repo is public — so it arrives as a Railway variable and is
# materialized here at boot, into /tmp for the same reason celerybeat's schedule
# lives there: the app dir is treated as read-only.
#
# Why this exists: until 2026-09-15 neither FIREBASE_CREDENTIALS_PATH nor
# GOOGLE_APPLICATION_CREDENTIALS was set in production, so
# `is_firebase_available()` was False and EVERY push returned early at
# `logger.debug` — below the deployed level. No error, no log line, the task
# succeeded, nothing was delivered, on iOS and Android alike. Hence the loud
# log lines on both branches below: the failure mode this replaces was silence.
#
# Done HERE rather than in Django so both children inherit it — the export must
# happen before the worker (which actually sends) and gunicorn are forked.
#
# A malformed value logs loudly and leaves push disabled rather than exiting:
# these credentials are push-only, and taking the whole web tier down over them
# would turn a broken notification into an outage. The log line is the signal.
firebase_credentials_file=${FIREBASE_CREDENTIALS_FILE:-/tmp/firebase-service-account.json}
if [[ -n ${FIREBASE_CREDENTIALS_PATH:-} ]]; then
  log "firebase: FIREBASE_CREDENTIALS_PATH already set (${FIREBASE_CREDENTIALS_PATH}); leaving it alone"
elif [[ -z ${FIREBASE_CREDENTIALS_B64:-} ]]; then
  log "firebase: FIREBASE_CREDENTIALS_B64 unset -> FCM PUSH DISABLED (sends return early and log nothing)"
elif firebase_project=$(FIREBASE_CREDENTIALS_TARGET="$firebase_credentials_file" python3 -c '
import base64, binascii, json, os, sys

raw = os.environ["FIREBASE_CREDENTIALS_B64"].strip()
if raw.startswith("{"):
    # Pasting the JSON straight into the variable is the obvious operator
    # mistake; it costs nothing to accept.
    data = raw.encode()
else:
    # Whitespace is stripped before validating because `base64 -i file` WRAPS
    # its output at 76 columns on both macOS and GNU coreutils, so a copied
    # value normally arrives with newlines in it. validate=True would reject
    # those outright and the failure would look like a corrupt key.
    try:
        data = base64.b64decode("".join(raw.split()), validate=True)
    except (binascii.Error, ValueError) as exc:
        sys.exit(f"value is neither raw JSON nor valid base64 ({exc})")
try:
    parsed = json.loads(data)
except ValueError as exc:
    sys.exit(f"decoded value is not JSON ({exc})")
if parsed.get("type") != "service_account":
    # NO single quotes anywhere in this script: the whole thing is one
    # single-quoted shell argument, so a quote here is eaten by the shell.
    # That bug shipped for one test run -- repr() below arrived as
    # parsed.get(type), looking up the BUILTIN, which returns None and made
    # every bad credential report "type is None".
    sys.exit("JSON type is " + repr(parsed.get("type")) + ", expected service_account")
missing = [k for k in ("project_id", "private_key", "client_email") if not parsed.get(k)]
if missing:
    sys.exit(f"service-account JSON is missing {missing}")
# 0600 and O_TRUNC via os.open: the file holds a private key, and a plain
# open() would leave it world-readable under the default umask.
fd = os.open(os.environ["FIREBASE_CREDENTIALS_TARGET"], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "wb") as fh:
    fh.write(data)
# project_id only. Never the key, and not client_email either; the project id
# is what makes a credential-source divergence diagnosable from logs (the same
# reason firebase_config.initialize_firebase logs it).
print(parsed["project_id"], end="")
' 2>/tmp/firebase-cred-error)
then
  export FIREBASE_CREDENTIALS_PATH="$firebase_credentials_file"
  log "firebase: credentials materialized at ${firebase_credentials_file} for project ${firebase_project} -> FCM push ENABLED"
else
  log "firebase: FIREBASE_CREDENTIALS_B64 is set but UNUSABLE: $(cat /tmp/firebase-cred-error 2>/dev/null) -> FCM PUSH STAYS DISABLED"
fi
rm -f /tmp/firebase-cred-error

start_worker
bash -c "$WEB_CMD" & web_pid=$!
log "worker pid ${worker_pid} (${WORKER_CMD}); web pid ${web_pid} (${WEB_CMD})"

worker_restarts=0
while true; do
  # Returns the first child's exit status, or 128+signal when a trapped signal
  # interrupted the wait (the trap has already set stopping=1 by then).
  wait -n "$worker_pid" "$web_pid"
  status=$?
  (( stopping )) && finish_stopped

  if ! kill -0 "$web_pid" 2>/dev/null; then
    log "web exited with status ${status}; stopping the worker and exiting 1 so Railway restarts the container"
    stop_children
    wait "$worker_pid" "$web_pid" 2>/dev/null
    exit 1
  fi

  # Only the worker exited.
  if (( worker_restarts >= WORKER_MAX_RESTARTS )); then
    log "worker exited with status ${status} after ${WORKER_MAX_RESTARTS} in-container restarts; exiting 1 so Railway restarts the container"
    stop_children
    wait "$worker_pid" "$web_pid" 2>/dev/null
    exit 1
  fi
  (( worker_restarts++ ))
  log "worker exited with status ${status}; restart ${worker_restarts}/${WORKER_MAX_RESTARTS} in ${WORKER_RESTART_DELAY}s (web pid ${web_pid} keeps serving)"
  sleep "$WORKER_RESTART_DELAY" & wait $!   # interruptible by the trap
  (( stopping )) && finish_stopped
  start_worker
  log "worker restarted as pid ${worker_pid}"
done
