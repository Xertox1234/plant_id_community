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
  if echo "$combined" | grep -q "$pattern"; then
    echo "PASS: $name"; PASS=$((PASS + 1))
  else
    echo "FAIL: $name"; echo "  expected to find: $pattern"; FAIL=$((FAIL + 1))
  fi
}

check_no_match() {
  local name="$1" input="$2" pattern="$3" combined
  combined=$(run_hook "$input")
  if echo "$combined" | grep -q "$pattern"; then
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
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/garden/firebase_config.py"}}' \
  "RULES — database"

check "backend firebase .py → firebase (stacks on fallback)" \
  '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/garden/firebase_config.py"}}' \
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
if echo "$OUT1" | grep -q "systemMessage" && echo "$OUT1" | grep -q "RECENT MISTAKES"; then
  echo "PASS: trigger match → systemMessage + RECENT MISTAKES"; PASS=$((PASS + 1))
else
  echo "FAIL: trigger match → systemMessage + RECENT MISTAKES"; FAIL=$((FAIL + 1))
fi
if echo "$OUT2" | grep -q "RECENT MISTAKES"; then
  echo "FAIL: repeat trigger in same session → deduped"; FAIL=$((FAIL + 1))
else
  echo "PASS: repeat trigger in same session → deduped"; PASS=$((PASS + 1))
fi
rm -f "/tmp/inject-${TRIG_SESSION}-"* 2>/dev/null

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
