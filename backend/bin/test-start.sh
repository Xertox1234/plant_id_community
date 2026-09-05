#!/usr/bin/env bash
# Self-test for bin/start.sh: crash coupling, worker restart budget, signal forwarding.
# Run: bash backend/bin/test-start.sh   (needs bash >= 5.1 like start.sh; exits 2 otherwise)
# No pgrep/procps needed: each fake child records its own pid in $tmp.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
START="$here/start.sh"

if (( BASH_VERSINFO[0] < 5 || (BASH_VERSINFO[0] == 5 && BASH_VERSINFO[1] < 1) )); then
  echo "test-start: needs bash >= 5.1 for 'wait -n PID...' (this is bash $BASH_VERSION)" >&2
  exit 2
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fail=0
pass() { echo "PASS: $1"; }
flunk() { echo "FAIL: $1"; fail=1; }

# A fake long-running child: records its pid, then execs sleep (pid unchanged).
child() { echo "sh -c 'echo \$\$ > $tmp/$1.pid; exec sleep 30'"; }
pid_alive() { [[ -f "$tmp/$1.pid" ]] && kill -0 "$(cat "$tmp/$1.pid")" 2>/dev/null; }

# Sets EXIT_STATUS to the pid's exit status, or TIMEOUT after $2 seconds.
# (Not a $(...) helper: a subshell cannot `wait` on this shell's children.)
wait_exit() {
  local pid=$1 limit=$2 i=0
  while kill -0 "$pid" 2>/dev/null; do
    if (( i >= limit * 5 )); then EXIT_STATUS=TIMEOUT; return; fi
    (( i++ )); sleep 0.2
  done
  wait "$pid"; EXIT_STATUS=$?
}
export WORKER_RESTART_DELAY=0.2   # keep the restart cases fast

bash -n "$START" && pass "start.sh parses" || flunk "start.sh has a syntax error"

# Case 1: the web child dies non-zero -> exit 1, the worker child is stopped.
WORKER_CMD="$(child w1)" WEB_CMD="exit 3" bash "$START" >"$tmp/c1.log" 2>&1 &
pid=$!; wait_exit "$pid" 5
[[ $EXIT_STATUS == 1 ]] && pass "web crash -> exit 1" || flunk "web crash -> expected exit 1, got $EXIT_STATUS"
sleep 0.5
pid_alive w1 && flunk "worker child survived the web crash" || pass "worker child stopped after the web crash"
grep -q "web exited with status 3" "$tmp/c1.log" && pass "web crash status is logged" || flunk "log missing the web status: $(cat "$tmp/c1.log")"

# Case 2: the worker crashes ONCE -> restarted in-container, web keeps serving; then SIGTERM -> exit 0.
flaky="sh -c 'if [ -f $tmp/flaky.once ]; then echo \$\$ > $tmp/w2.pid; exec sleep 30; else touch $tmp/flaky.once; exit 7; fi'"
WORKER_MAX_RESTARTS=3 WORKER_CMD="$flaky" WEB_CMD="$(child g2)" bash "$START" >"$tmp/c2.log" 2>&1 &
pid=$!; sleep 1.5
kill -0 "$pid" 2>/dev/null && pass "container survives a single worker crash" || flunk "script exited after one worker crash"
pid_alive g2 && pass "web child kept serving through the worker restart" || flunk "web child died during the worker restart"
pid_alive w2 && pass "worker was restarted" || flunk "worker not restarted: $(cat "$tmp/c2.log")"
grep -q "worker exited with status 7; restart 1/3" "$tmp/c2.log" && pass "worker restart is logged with its status" || flunk "restart log missing: $(cat "$tmp/c2.log")"
kill -TERM "$pid"; wait_exit "$pid" 5
[[ $EXIT_STATUS == 0 ]] && pass "SIGTERM after a restart -> exit 0" || flunk "SIGTERM after a restart -> expected 0, got $EXIT_STATUS"
sleep 0.5
{ pid_alive w2 || pid_alive g2; } && flunk "a child survived SIGTERM (case 2)" || pass "both children stopped on SIGTERM (case 2)"

# Case 3: the worker keeps exiting CLEANLY (status 0) -> restarted up to the budget, then exit 1 and the web child is stopped.
WORKER_MAX_RESTARTS=2 WORKER_CMD="exit 0" WEB_CMD="$(child g3)" bash "$START" >"$tmp/c3.log" 2>&1 &
pid=$!; wait_exit "$pid" 5
[[ $EXIT_STATUS == 1 ]] && pass "worker crashloop past the budget -> exit 1" || flunk "worker crashloop -> expected exit 1, got $EXIT_STATUS"
grep -q "restart 1/2" "$tmp/c3.log" && grep -q "restart 2/2" "$tmp/c3.log" && grep -q "after 2 in-container restarts" "$tmp/c3.log" \
  && pass "restart budget is counted and its exhaustion logged" || flunk "budget log wrong: $(cat "$tmp/c3.log")"
restarts=$(grep -c "; restart [0-9]*/2 in" "$tmp/c3.log")
[[ $restarts == 2 ]] && pass "exactly WORKER_MAX_RESTARTS restarts happen (no off-by-one)" || flunk "expected exactly 2 restart lines, got $restarts: $(grep restart "$tmp/c3.log")"
sleep 0.5
pid_alive g3 && flunk "web child survived the worker crashloop" || pass "web child stopped after the worker crashloop"

# Case 4: SIGTERM with both healthy (a redeploy) -> forwarded to both, exit 0.
WORKER_CMD="$(child w4)" WEB_CMD="$(child g4)" bash "$START" >/dev/null 2>&1 &
pid=$!; sleep 0.7
pid_alive w4 && pid_alive g4 && pass "both children running before SIGTERM" || flunk "children not running before SIGTERM"
kill -TERM "$pid"; wait_exit "$pid" 5
[[ $EXIT_STATUS == 0 ]] && pass "SIGTERM -> exit 0" || flunk "SIGTERM -> expected exit 0, got $EXIT_STATUS"
sleep 0.5
{ pid_alive w4 || pid_alive g4; } && flunk "a child survived SIGTERM" || pass "both children stopped on SIGTERM"

# Case 5: SIGTERM DURING the restart delay -> exit 0 promptly, nothing left behind.
WORKER_RESTART_DELAY=5 WORKER_CMD="exit 0" WEB_CMD="$(child g5)" bash "$START" >/dev/null 2>&1 &
pid=$!; sleep 0.7; kill -TERM "$pid"; wait_exit "$pid" 3
[[ $EXIT_STATUS == 0 ]] && pass "SIGTERM during the restart delay -> exit 0 without waiting it out" || flunk "SIGTERM during delay -> got $EXIT_STATUS"
sleep 0.3; pid_alive g5 && flunk "web child survived SIGTERM during the delay" || pass "web child stopped (case 5)"

# Case 6: the default commands are built from PORT / CELERY_CONCURRENCY and name the real programs.
defaults=$(PORT=8123 CELERY_CONCURRENCY=7 bash -c 'source <(sed -n "/^: \"\${PORT/,/^WEB_CMD=/p" "$1"); echo "$WORKER_CMD"; echo "$WEB_CMD"' _ "$START")
[[ $defaults == *"--concurrency=7"* && $defaults == *"0.0.0.0:8123"* ]] && pass "defaults honour PORT and CELERY_CONCURRENCY" || flunk "defaults wrong: $defaults"
[[ $defaults == *"celery -A plant_community_backend worker"* && $defaults == *"gunicorn plant_community_backend.wsgi:application"* ]] && pass "defaults name the real worker and web commands" || flunk "defaults changed: $defaults"

(( fail == 0 )) && echo "test-start: all cases passed" || { echo "test-start: FAILURES"; exit 1; }
