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

# --- Firebase credential materialization (todo 286) --------------------------
# Each case boots start.sh with fake children, so the assertions are about what
# the CHILDREN inherit -- the export has to happen before the fork or the worker
# that actually sends the push never sees it.
# The private_key value is a SENTINEL, not a PEM. start.sh only checks the field
# is non-empty, and a fixture carrying a real PEM armour header trips both
# the detect-secrets and detect-private-key pre-commit hooks -- a test fixture
# must not look like the thing it is testing the handling of. The sentinel also
# makes the "never logged" assertion below sharper than grepping for a PEM header.
SA_JSON='{"type":"service_account","project_id":"plant-community-prod","private_key":"SENTINEL_KEY_MUST_NEVER_BE_LOGGED","client_email":"x@plant-community-prod.iam.gserviceaccount.com"}'

# Records what the child actually inherited, then stays alive.
env_child() { echo "sh -c 'printf %s \"\${FIREBASE_CREDENTIALS_PATH:-NONE}\" > $tmp/$1.env; exec sleep 30'"; }
# Boot start.sh, let it fork, SIGTERM it, and wait. $1 names the env file.
boot() {
  local name=$1 logfile=$2; shift 2
  env "$@" WORKER_CMD="$(env_child "${name}w")" WEB_CMD="$(env_child "$name")" \
    bash "$START" >"$logfile" 2>&1 &
  local pid=$!; sleep 0.8; kill -TERM "$pid" 2>/dev/null; wait_exit "$pid" 5
}

# Case 7: variable unset -> nothing written, children see no path, and the log SAYS SO.
rm -f "$tmp/f7.env" /tmp/firebase-service-account.json
boot f7 "$tmp/c7.log" FIREBASE_CREDENTIALS_FILE="$tmp/sa7.json"
[[ $(cat "$tmp/f7.env" 2>/dev/null) == NONE ]] && pass "no B64 -> child inherits no credentials path" || flunk "unset case leaked a path: $(cat "$tmp/f7.env" 2>/dev/null)"
[[ -f "$tmp/sa7.json" ]] && flunk "unset case wrote a credentials file" || pass "unset case writes no file"
grep -q "FCM PUSH DISABLED" "$tmp/c7.log" && pass "unset case is logged loudly (not silent)" || flunk "unset case not logged: $(cat "$tmp/c7.log")"

# Case 8: valid base64 -> file written 0600, children inherit the path, project id logged.
b64=$(printf %s "$SA_JSON" | base64 | tr -d '\n')
boot f8 "$tmp/c8.log" FIREBASE_CREDENTIALS_FILE="$tmp/sa8.json" FIREBASE_CREDENTIALS_B64="$b64"
[[ $(cat "$tmp/f8.env" 2>/dev/null) == "$tmp/sa8.json" ]] && pass "valid B64 -> child inherits the credentials path" || flunk "child did not inherit the path: $(cat "$tmp/f8.env" 2>/dev/null)"
[[ $(cat "$tmp/sa8.json" 2>/dev/null) == "$SA_JSON" ]] && pass "decoded JSON is written verbatim" || flunk "written file wrong: $(cat "$tmp/sa8.json" 2>/dev/null)"
perms=$(ls -l "$tmp/sa8.json" | cut -c1-10)
[[ $perms == -rw------- ]] && pass "credentials file is 0600" || flunk "credentials file perms are $perms, expected -rw-------"
# Guards the bug where the log read a file nothing wrote: the project id must be
# INTERPOLATED, so a literal 'project ->' or an empty slot is a failure.
grep -q "for project plant-community-prod" "$tmp/c8.log" && pass "project id is logged" || flunk "project id missing from log: $(cat "$tmp/c8.log")"
grep -q "SENTINEL_KEY_MUST_NEVER_BE_LOGGED" "$tmp/c8.log" && flunk "THE PRIVATE KEY WAS LOGGED" || pass "the private key never reaches the log"
grep -q "client_email\|gserviceaccount" "$tmp/c8.log" && flunk "the client_email reached the log" || pass "only the project id is logged, not the account identity"

# Case 9: base64 WRAPPED at 76 cols, plus a trailing newline -- what a copied
# `base64 -i file` value actually looks like in a Railway variable.
#
# The fold is EXPLICIT on purpose. Writing this as `printf ... | base64` and
# trusting the wrapping is platform-dependent: GNU coreutils wraps at 76, macOS
# /usr/bin/base64 does NOT wrap at all. That fixture contained zero newlines
# locally, so the case was vacuous on macOS and only real in CI -- caught by a
# surviving mutant when the whitespace-strip was removed and nothing failed.
wrapped=$(printf %s "$SA_JSON" | base64 | tr -d '\n' | fold -w 76)
wrapped="${wrapped}"$'\n'
[[ $(grep -c "" <<<"$wrapped") -ge 3 ]] && pass "wrapped fixture really contains newlines (not vacuous)" || flunk "wrapped fixture has no newlines; case 9 would prove nothing"
boot f9 "$tmp/c9.log" FIREBASE_CREDENTIALS_FILE="$tmp/sa9.json" FIREBASE_CREDENTIALS_B64="$wrapped"
[[ $(cat "$tmp/sa9.json" 2>/dev/null) == "$SA_JSON" ]] && pass "wrapped base64 (newlines) is accepted" || flunk "wrapped base64 rejected: $(cat "$tmp/c9.log")"

# Case 10: raw JSON pasted straight in -- the obvious operator mistake.
boot f10 "$tmp/c10.log" FIREBASE_CREDENTIALS_FILE="$tmp/sa10.json" FIREBASE_CREDENTIALS_B64="$SA_JSON"
[[ $(cat "$tmp/sa10.json" 2>/dev/null) == "$SA_JSON" ]] && pass "raw JSON is accepted too" || flunk "raw JSON rejected: $(cat "$tmp/c10.log")"

# Case 11: garbage -> the container STILL BOOTS (push is not worth an outage),
# push stays disabled, and the reason is logged.
boot f11 "$tmp/c11.log" FIREBASE_CREDENTIALS_FILE="$tmp/sa11.json" FIREBASE_CREDENTIALS_B64="!!!not base64!!!"
[[ $EXIT_STATUS == 0 ]] && pass "malformed credentials do not take the web tier down" || flunk "malformed credentials exited $EXIT_STATUS"
[[ $(cat "$tmp/f11.env" 2>/dev/null) == NONE ]] && pass "malformed -> child inherits no path" || flunk "malformed case exported a path anyway"
grep -q "UNUSABLE" "$tmp/c11.log" && pass "malformed credentials are logged with the reason" || flunk "malformed not logged: $(cat "$tmp/c11.log")"

# Case 12: valid base64 but NOT a service account -> refused, not written.
b64user=$(printf %s '{"type":"authorized_user","project_id":"p"}' | base64 | tr -d '\n')
boot f12 "$tmp/c12.log" FIREBASE_CREDENTIALS_FILE="$tmp/sa12.json" FIREBASE_CREDENTIALS_B64="$b64user"
[[ -f "$tmp/sa12.json" ]] && flunk "a non-service_account JSON was written" || pass "non-service_account JSON is refused"
grep -q "expected service_account" "$tmp/c12.log" && pass "wrong credential type names itself" || flunk "type error not logged: $(cat "$tmp/c12.log")"
grep -q "authorized_user" "$tmp/c12.log" && pass "the offending type is named, not swallowed" || flunk "log did not name the actual type: $(cat "$tmp/c12.log")"

# Case 14 (static): the embedded python is ONE single-quoted shell argument, so a
# single quote anywhere inside it is silently eaten by the shell and Python gets
# different code. That shipped once: parsed.get('type') arrived as
# parsed.get(type) -- the BUILTIN -- which returns None, so every malformed
# credential reported "type is None" instead of the real type. Only the failure
# branch evaluated that line, so every valid-credential case still passed. This
# guards the CLASS, not the instance.
embedded=$(sed -n "/python3 -c '/,/^' 2>\/tmp\/firebase-cred-error)/p" "$START" | sed '1d;$d')
[[ -n $embedded ]] && pass "embedded python block is locatable" || flunk "could not extract the embedded python block"
if grep -q "'" <<<"$embedded"; then
  flunk "the embedded python contains a single quote (the shell will eat it): $(grep -n "'" <<<"$embedded")"
else
  pass "embedded python contains no single quotes"
fi
python3 -c 'import sys; compile(sys.stdin.read(), "embedded", "exec")' <<<"$embedded" \
  && pass "embedded python compiles as written" || flunk "embedded python does not compile"

# Case 13: an explicitly-set path wins (the Railway-volume route) and is not clobbered.
boot f13 "$tmp/c13.log" FIREBASE_CREDENTIALS_FILE="$tmp/sa13.json" FIREBASE_CREDENTIALS_B64="$b64" FIREBASE_CREDENTIALS_PATH=/mnt/creds.json
[[ $(cat "$tmp/f13.env" 2>/dev/null) == /mnt/creds.json ]] && pass "an explicit FIREBASE_CREDENTIALS_PATH is not clobbered" || flunk "explicit path was overwritten: $(cat "$tmp/f13.env" 2>/dev/null)"
[[ -f "$tmp/sa13.json" ]] && flunk "explicit-path case wrote a file anyway" || pass "explicit-path case writes nothing"

(( fail == 0 )) && echo "test-start: all cases passed" || { echo "test-start: FAILURES"; exit 1; }
