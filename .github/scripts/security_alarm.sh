#!/usr/bin/env bash
# Give the weekly security scan a consumer.
#
# The scan already hard-fails on schedule, exactly as designed. It had failed
# 8 consecutive weeks (31 of its last 40 scheduled runs) before anyone noticed,
# because a scheduled-run failure blocks no PR and appears on no check list.
# This script turns that silent failure into one open GitHub issue.
#
# Dedupe: the single open issue carrying $LABEL IS the key. Week 2..N comment on
# it and refresh its body; they never open a second issue. A green run closes it.
# Closing ends the episode, so the next failure opens a NEW issue — and that
# issue number is what scripts/sync_alarm_todo.py binds a todo to.
#
# Required env: GH_TOKEN, FAILED (true|false), RUN_URL,
#               BACKEND_RESULT, FRONTEND_RESULT, MOBILE_RESULT
set -euo pipefail

LABEL="security-scan-alarm"
TODAY="$(date -u +%F)"

# --force updates an existing label rather than erroring, so the alarm has no
# manual prerequisite.
gh label create "$LABEL" --color d93f0b \
  --description "Auto-filed: the scheduled security scan is failing" --force >/dev/null 2>&1 || true

ISSUE="$(gh issue list --state open --label "$LABEL" --limit 1 \
          --json number --jq '.[0].number // empty')"

render_body() {
  cat <<BODY
**The scheduled security scan is failing.** This issue is opened and closed
automatically by \`.github/workflows/security-scan.yml\`.

| Job | Result |
|---|---|
| Backend Python Security Scan | \`${BACKEND_RESULT}\` |
| Frontend npm Security Scan | \`${FRONTEND_RESULT}\` |
| Flutter Dependency Security Check | \`${MOBILE_RESULT}\` |

Latest run: ${RUN_URL}
Last updated: ${TODAY}

---

### Alarm issue: #${1}

That line above is the dedupe key. To pull this failure into the todo sweep so
it gets worked like any other backlog item, run locally:

\`\`\`
python3 scripts/sync_alarm_todo.py
\`\`\`

CI cannot write the todo itself: this repo has
\`default_workflow_permissions: read\` with \`can_approve_pull_request_reviews:
false\`, so Actions cannot open a PR — and a \`GITHUB_TOKEN\`-created PR triggers
no workflows, so the required checks would never report and the PR would
deadlock.

### Why this issue exists

The scan is correct and has always hard-failed on schedule. What it lacked was
a consumer: a failed scheduled run blocks no PR and shows on no check list, so
it failed 8 weeks running without anyone seeing it. See
\`docs/superpowers/plans/2026-09-05-security-backlog-multi-session.md\`.
BODY
}

if [ "${FAILED}" = "true" ]; then
  if [ -z "${ISSUE}" ]; then
    URL="$(gh issue create --label "$LABEL" \
            --title "Scheduled security scan is failing" \
            --body "$(render_body 'pending')")"
    NEW="${URL##*/}"
    # Re-render now that the number exists, so the dedupe key is accurate.
    gh issue edit "$NEW" --body "$(render_body "$NEW")" >/dev/null
    echo "opened alarm issue #${NEW}"
  else
    gh issue comment "$ISSUE" \
      --body "Still failing as of ${TODAY}. Run: ${RUN_URL}"
    gh issue edit "$ISSUE" --body "$(render_body "$ISSUE")" >/dev/null
    echo "updated alarm issue #${ISSUE}"
  fi
else
  if [ -n "${ISSUE}" ]; then
    gh issue comment "$ISSUE" --body "Scan green as of ${TODAY}. Run: ${RUN_URL}"
    gh issue close "$ISSUE" --reason completed
    echo "closed alarm issue #${ISSUE}"
  else
    echo "scan green; no open alarm issue"
  fi
fi
