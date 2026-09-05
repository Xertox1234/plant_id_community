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
