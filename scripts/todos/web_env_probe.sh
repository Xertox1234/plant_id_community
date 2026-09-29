#!/usr/bin/env bash
# Todo 479 / pilot check P5: does a worker's Vitest run in a fresh worktree see web/.env values?
# Prints key names and a match flag only, never a value.
#   bash scripts/todos/web_env_probe.sh <worktree> <slot>
# Needs WT/web/node_modules (the worker's `ln -sfn MAIN/web/node_modules ...`). The probe test lives in a
# temp dir, never in WT, and reads its env from WT/web exactly as the web app's Vite config does (envDir).
# The config is plain .mjs loaded natively: bundling a TS config writes into node_modules, which the
# sandbox denies when node_modules is a link into another checkout.
set -uo pipefail
WT="${1:?worktree}"; SLOT="${2:?slot}"
MAIN="$(cd "$(/usr/bin/git -C "$WT" rev-parse --path-format=absolute --git-common-dir)/.." && pwd)"
echo "worktree: $WT"
echo "harness main checkout (where .worktreeinclude is read): $MAIN"
if [ -f "$MAIN/.worktreeinclude" ]; then echo "  it has .worktreeinclude"; else echo "  it has NO .worktreeinclude"; fi
if [ -f "$WT/web/.env" ]; then echo "P5: $WT/web/.env present"; else echo "P5: $WT/web/.env MISSING"; fi
[ -d "$WT/web/node_modules" ] || { echo "no $WT/web/node_modules; link the toolchain first"; exit 2; }
PROBE=$(mktemp -d "${TMPDIR:-/tmp}/web-env-probe.XXXXXX") || exit 1
trap 'rm -rf "$PROBE"' EXIT
ln -s "$WT/web/node_modules" "$PROBE/node_modules"
cat > "$PROBE/vitest.config.mjs" <<'EOF'
export default { envDir: process.env.PROBE_ENVDIR, cacheDir: process.env.PROBE_CACHE, test: { include: ['env.test.ts'] } }
EOF
cat > "$PROBE/env.test.ts" <<'EOF'
import { test, expect } from 'vitest'
test('a worker Vitest run reads web env values', () => {
  const keys = Object.keys(import.meta.env).filter(k => k.startsWith('VITE_')).sort()
  console.log(`VITE keys seen by Vitest: ${keys.join(',') || '(none)'}`)
  console.log(`VITE_API_URL matches the main checkout's web/.env: ${import.meta.env.VITE_API_URL === process.env.PROBE_EXPECT}`)
  expect(import.meta.env.VITE_API_URL === process.env.PROBE_EXPECT, 'VITE_API_URL is the main checkout value').toBe(true)
})
EOF
EXPECT=$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import slot_env; print(slot_env.parse_dotenv(open(sys.argv[2]).read()).get("VITE_API_URL", ""))' \
  "$WT/scripts/todos" "$MAIN/web/.env")
cd "$PROBE" || exit 1
run() {
  PROBE_EXPECT="$EXPECT" PROBE_ENVDIR="$WT/web" PROBE_CACHE="$PROBE/.cache" "$@" ./node_modules/.bin/vitest run \
    --config vitest.config.mjs --configLoader native --reporter verbose --silent=false 2>&1 \
    | grep -E "VITE|a worker Vitest run|Test Files|Tests |Error" | head -10
}
echo "--- vitest run without slot_env"
run env -u VITE_API_URL
echo "--- vitest run through slot_env (slot $SLOT)"
run python3 "$WT/scripts/todos/slot_env.py" --worktree "$WT" "$SLOT" --
