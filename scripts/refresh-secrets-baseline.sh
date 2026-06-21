#!/usr/bin/env bash
# Refresh .secrets.baseline line numbers WITHOUT discarding audit decisions.
#
# Run this when the detect-secrets pre-commit hook re-flags an already-known
# placeholder secret after its line number shifted (baseline "churn").
#
# Uses `detect-secrets scan --baseline FILE`, which updates the existing
# baseline in place and PRESERVES the `is_secret` / `is_verified` audit
# decisions. Do NOT use `detect-secrets scan > .secrets.baseline` — the
# redirect form wipes every audit decision and re-introduces the churn.
#
# The --exclude-files set below mirrors .pre-commit-config.yaml so the
# refreshed baseline matches exactly what the commit gate scans.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

DS="backend/venv/bin/detect-secrets"
[ -x "$DS" ] || DS="$(command -v detect-secrets || true)"
if [ -z "$DS" ]; then
  echo "detect-secrets not found. Install it: backend/venv/bin/pip install detect-secrets" >&2
  exit 1
fi

echo "Refreshing .secrets.baseline (in place, preserving audit decisions)..."
# Mirror BOTH of the gate's exclusion mechanisms in .pre-commit-config.yaml: the
# detect-secrets `args: --exclude-files` (.env.example, package-lock.json) AND the
# pre-commit top-level `exclude:` regex (*.lock, *.min.js, *.g.dart,
# SECURITY_INCIDENT_*). If only the args set is mirrored, a full rescan adds
# entries (e.g. generated *.g.dart high-entropy strings) the gate never scans —
# baseline noise. Keep this list in sync if the gate's excludes change.
"$DS" scan --baseline .secrets.baseline \
  --exclude-files '\.env\.example$' \
  --exclude-files 'package-lock\.json$' \
  --exclude-files '\.lock$' \
  --exclude-files '\.min\.js$' \
  --exclude-files '\.g\.dart$' \
  --exclude-files 'backend/docs/development/SECURITY_INCIDENT_.*\.md$'

echo "Done. Review the diff, then stage it:"
echo "  git diff .secrets.baseline"
echo "  git add .secrets.baseline"
echo
echo "Tip: to stop a test PLACEHOLDER from churning again, add a trailing"
echo "     '# pragma: allowlist secret' on that line — it survives line shifts."
