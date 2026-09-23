#!/usr/bin/env bash
# Tests for inject-patterns.sh — run from anywhere.
# Requires docs/rules/<domain>.md files to exist (the hook only emits a
# [RULES — domain] block when the corresponding file is present).
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/inject-patterns.sh"
# inject-patterns.sh writes its spill file to a per-PID path
# (/tmp/plant-id-injection-context.<pid>.md), so match them with a glob.
SPILL_GLOB="/tmp/plant-id-injection-context.*.md"
PASS=0; FAIL=0

run_hook() {
  local input="$1"
  rm -f $SPILL_GLOB
  local output spill="" f
  output=$(echo "$input" | bash "$HOOK" 2>/dev/null || true)
  for f in $SPILL_GLOB; do
    [ -f "$f" ] && spill+=$(cat "$f")
  done
  printf '%s\n%s' "$output" "$spill"
}

check() {
  local name="$1" input="$2" pattern="$3" combined
  combined=$(run_hook "$input")
  if grep -q "$pattern" <<< "$combined"; then
    echo "PASS: $name"; PASS=$((PASS + 1))
  else
    echo "FAIL: $name"; echo "  expected to find: $pattern"; FAIL=$((FAIL + 1))
  fi
}

check_no_match() {
  local name="$1" input="$2" pattern="$3" combined
  combined=$(run_hook "$input")
  if grep -q "$pattern" <<< "$combined"; then
    echo "FAIL: $name (expected NOT to find: $pattern)"; FAIL=$((FAIL + 1))
  else
    echo "PASS: $name"; PASS=$((PASS + 1))
  fi
}

check_empty() {
  local name="$1" input="$2" output
  rm -f $SPILL_GLOB
  output=$(echo "$input" | bash "$HOOK" 2>/dev/null || true)
  if [ -z "$output" ]; then
    echo "PASS: $name"; PASS=$((PASS + 1))
  else
    echo "FAIL: $name (expected empty)"; echo "  got: $(echo "$output" | head -3)"; FAIL=$((FAIL + 1))
  fi
}

# blog → wagtail + api + security
check "blog models → wagtail rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/blog/models.py"}}' \
  "RULES — wagtail"

# forum (package + host app) → forum + wagtail
check "wagtail_forum package → forum rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/packages/wagtail_forum/wagtail_forum/models/topics.py"}}' \
  "RULES — forum"

check "forum_host app → wagtail rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/forum_host/settings.py"}}' \
  "RULES — wagtail"

# migrations → database + security
check "migration → database rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/plant_identification/migrations/0001_initial.py"}}' \
  "RULES — database"

check "migration → security rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/plant_identification/migrations/0001_initial.py"}}' \
  "RULES — security"

# serializers → api
check "serializers → api rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/forum/serializers.py"}}' \
  "RULES — api"

# views → api + security
check "views → api rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/users/views.py"}}' \
  "RULES — api"

check "views → security rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/users/views.py"}}' \
  "RULES — security"

# tasks → celery
check "tasks → celery rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/blog/tasks.py"}}' \
  "RULES — celery"

# React component → react + typescript
check "web component → react rules" \
  '{"tool_name":"Write","tool_input":{"file_path":"web/src/components/BlogCard.tsx"}}' \
  "RULES — react"

# Plain .ts → typescript fallback
check "web .ts → typescript fallback" \
  '{"tool_name":"Edit","tool_input":{"file_path":"web/src/lib/api.ts"}}' \
  "RULES — typescript"

# Flutter → flutter
check "dart file → flutter rules" \
  '{"tool_name":"Write","tool_input":{"file_path":"plant_community_mobile/lib/main.dart"}}' \
  "RULES — flutter"

# Test file → testing (additive)
check "backend test file → testing rules" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/forum/tests/test_views.py"}}' \
  "RULES — testing"

# Ordered-fallback regression: a backend *.py that ALSO matches *firebase* must get
# BOTH the backend/*.py fallback domains (database) AND the firebase additive domains
# (firebase). The backend/*.py fallback is positioned BEFORE the firebase rule in
# routing.json, so firebase stacks on top of it. A "fallback only if no rule matched
# anywhere" model would drop database here — these two checks guard against that
# regression (see docs/rules/routing.json: ORDER IS LOAD-BEARING).
check "backend firebase .py → database (fallback fires)" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/core/firebase_config.py"}}' \
  "RULES — database"

check "backend firebase .py → firebase (stacks on fallback)" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/core/firebase_config.py"}}' \
  "RULES — firebase"

# Output is valid JSON
check "output is valid JSON with hookSpecificOutput" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/users/views.py"}}' \
  "hookSpecificOutput"

# Discipline preamble always emitted for Edit/Write
check "non-domain file → discipline preamble emitted" \
  '{"tool_name":"Edit","tool_input":{"file_path":"README.md"}}' \
  "DISCIPLINE"

check_no_match "non-domain file → no RULES blocks" \
  '{"tool_name":"Edit","tool_input":{"file_path":"README.md"}}' \
  "RULES — "

# Read tool → no output (not Edit/Write/MultiEdit)
check_empty "Read tool → no output" \
  '{"tool_name":"Read","tool_input":{"file_path":"backend/apps/users/views.py"}}'

# Missing file_path → no output
check_empty "missing file_path → no output" \
  '{"tool_name":"Edit","tool_input":{}}'

# Trigger warnings fire once per session: first matching edit emits a
# systemMessage + RECENT MISTAKES block; an identical edit in the same session
# is deduped. Relies on the react-router-bare-import trigger in
# docs/rules/triggers.json; INJECT_FIRES_LOG=/dev/null keeps the real fire log
# clean.
TRIG_SESSION="inject-test-$$"
TRIG_EVENT=$(jq -n --arg sid "$TRIG_SESSION" \
  '{tool_name:"Write",session_id:$sid,tool_input:{file_path:"web/src/InjectTest.tsx",content:"import { useNavigate } from \"react-router\";\n"}}')
rm -f "/tmp/inject-${TRIG_SESSION}-"* 2>/dev/null
OUT1=$(printf '%s' "$TRIG_EVENT" | INJECT_FIRES_LOG=/dev/null bash "$HOOK" 2>/dev/null)
OUT2=$(printf '%s' "$TRIG_EVENT" | INJECT_FIRES_LOG=/dev/null bash "$HOOK" 2>/dev/null)
if grep -q "systemMessage" <<< "$OUT1" && grep -q "RECENT MISTAKES" <<< "$OUT1"; then
  echo "PASS: trigger match → systemMessage + RECENT MISTAKES"; PASS=$((PASS + 1))
else
  echo "FAIL: trigger match → systemMessage + RECENT MISTAKES"; FAIL=$((FAIL + 1))
fi
if grep -q "RECENT MISTAKES" <<< "$OUT2"; then
  echo "FAIL: repeat trigger in same session → deduped"; FAIL=$((FAIL + 1))
else
  echo "PASS: repeat trigger in same session → deduped"; PASS=$((PASS + 1))
fi
rm -f "/tmp/inject-${TRIG_SESSION}-"* 2>/dev/null

# ---------------------------------------------------------------------------
# Budgeted injection (todo 369). Before this, `cat` + `head -c 8800` gave the
# FIRST routed domain everything and later domains zero bytes, and truncated a
# single-domain edit mid-word. These four assert the properties that replaced it.
# ---------------------------------------------------------------------------
budget_ctx() {
  jq -n --arg sid "budget-test-$$-$RANDOM" --arg fp "$1" \
    '{tool_name:"Edit",session_id:$sid,tool_input:{file_path:$fp,old_string:"x",new_string:"y"}}' \
    | INJECT_FIRES_LOG=/dev/null bash "$HOOK" 2>/dev/null \
    | jq -r '.hookSpecificOutput.additionalContext'
}

# A path routing to three domains must carry content from ALL THREE. settings.py
# routes to api,security,database and used to deliver api alone.
MULTI=$(budget_ctx "backend/plant_community_backend/settings.py")
MISSING=""
for d in api security database; do
  grep -q "\[RULES — $d\]" <<< "$MULTI" || MISSING="$MISSING $d"
done
if [ -z "$MISSING" ]; then
  echo "PASS: 3-domain path injects all three domains"; PASS=$((PASS + 1))
else
  echo "FAIL: 3-domain path missing:$MISSING"; FAIL=$((FAIL + 1))
fi

# The payload must still respect the hook-output cap.
MULTI_SIZE=$(printf '%s' "$MULTI" | wc -c | tr -d ' ')
if [ "$MULTI_SIZE" -le 9000 ] && [ "$MULTI_SIZE" -gt 3000 ]; then
  echo "PASS: budgeted payload within the cap ($MULTI_SIZE B)"; PASS=$((PASS + 1))
else
  echo "FAIL: budgeted payload out of range ($MULTI_SIZE B)"; FAIL=$((FAIL + 1))
fi

# An elision marker must start its own line -- i.e. the cut landed on a line
# boundary, not mid-sentence. A marker appearing mid-line is the mid-bullet cut
# this replaced.
# Asserts markers EXIST as well as being well-placed. `|| ! grep` would have
# made this pass vacuously against the old hook, which emitted no markers at all
# -- the "green by emptiness" shape this repo keeps finding.
MARKERS_TOTAL=$(grep -c '\[\.\.\.' <<< "$MULTI" || true)
MARKERS_ANCHORED=$(grep -c '^\[\.\.\.' <<< "$MULTI" || true)
if [ "$MARKERS_TOTAL" -ge 1 ] && [ "$MARKERS_TOTAL" -eq "$MARKERS_ANCHORED" ]; then
  echo "PASS: $MARKERS_TOTAL elision marker(s), all starting their own line"; PASS=$((PASS + 1))
else
  echo "FAIL: $MARKERS_ANCHORED of $MARKERS_TOTAL elision markers start a line"; FAIL=$((FAIL + 1))
fi

# ---------------------------------------------------------------------------
# Direct budget_rules.py properties.
#
# The two assertions above go through the hook, where `allocate()`'s slack
# cascade lifts most shares well clear of the interesting range. Review round 1
# showed both of them pass against the PRE-FIX implementation, so neither is a
# regression guard. These two call excerpt() at the shares real 4- and
# 5-domain routes actually produce (620-928 B measured) and fail against it.
# ---------------------------------------------------------------------------
BR="$(cd "$(dirname "$HOOK")/../.." && pwd)/scripts/inject/budget_rules.py"
RULES_DIR="$(cd "$(dirname "$HOOK")/../.." && pwd)/docs/rules"

PROP=$(python3 - "$BR" "$RULES_DIR" <<'PYEOF'
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location("br", sys.argv[1])
br = importlib.util.module_from_spec(spec); spec.loader.exec_module(br)
text = (pathlib.Path(sys.argv[2]) / "testing.md").read_text() + "\n- SENTINEL_PROP_369\n"
lost = over = 0
for share in (300, 500, 620, 699, 734, 928, 1500, 3000, 6000):
    out = br.excerpt(text, share, "docs/rules/testing.md")
    if "SENTINEL_PROP_369" not in out:
        lost += 1
    if len(out.encode("utf-8")) > share:
        over += 1
print(f"{lost} {over}")
PYEOF
) || PROP="ERR ERR"
PROP_LOST=${PROP%% *}; PROP_OVER=${PROP##* }

if [ "$PROP_LOST" = "0" ]; then
  echo "PASS: excerpt() keeps the file tail at every real share"; PASS=$((PASS + 1))
else
  echo "FAIL: excerpt() dropped the tail at $PROP_LOST share(s)"; FAIL=$((FAIL + 1))
fi

if [ "$PROP_OVER" = "0" ]; then
  echo "PASS: excerpt() never exceeds the share it is given"; PASS=$((PASS + 1))
else
  echo "FAIL: excerpt() exceeded its share at $PROP_OVER share(s)"; FAIL=$((FAIL + 1))
fi

# The newest rule -- these files are append-only -- must reach the edit site.
# Asserted by appending a sentinel to the LARGEST rule file and looking for it.
# Without the tail half of the excerpt this fails: the sentinel sits ~46 KB into
# a file whose share is under 4 KB.
SENTINEL_FILE="$(cd "$(dirname "$HOOK")/../.." && pwd)/docs/rules/testing.md"
cp "$SENTINEL_FILE" "$SENTINEL_FILE.injecttest.bak"
# Restore on ANY exit, not just the happy path. Without this, a Ctrl-C in the
# window below leaves a tracked rules file mutated and a .bak beside it -- and
# this repo has lost time to exactly that residue shape before.
trap 'if [ -f "$SENTINEL_FILE.injecttest.bak" ]; then
        cp "$SENTINEL_FILE.injecttest.bak" "$SENTINEL_FILE"
        rm -f "$SENTINEL_FILE.injecttest.bak"
      fi' EXIT INT TERM
printf '\n- **SENTINEL_TAIL_369** proves an appended rule still injects.\n' >> "$SENTINEL_FILE"
TAIL_CTX=$(budget_ctx "backend/apps/core/tests/test_budget_probe.py")
cp "$SENTINEL_FILE.injecttest.bak" "$SENTINEL_FILE"
rm -f "$SENTINEL_FILE.injecttest.bak"
if grep -q "SENTINEL_TAIL_369" <<< "$TAIL_CTX"; then
  echo "PASS: newest rule in the largest file reaches the edit"; PASS=$((PASS + 1))
else
  echo "FAIL: newest rule in the largest file was cut"; FAIL=$((FAIL + 1))
fi
if grep -q "SENTINEL_TAIL_369" "$SENTINEL_FILE"; then
  echo "FAIL: sentinel left behind in docs/rules/testing.md"; FAIL=$((FAIL + 1))
else
  echo "PASS: sentinel removed from docs/rules/testing.md"; PASS=$((PASS + 1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
