#!/usr/bin/env python3
"""Turn code-review findings into candidate write-time triggers.

The code-review orchestrator pipes its merged findings JSON here (stdin or a file
arg). For each finding carrying a `trigger_signature` (which the reviewer that
found it emits only when a clean textual signature exists), this appends a
`severity: candidate` trigger to docs/rules/triggers.json so the same mistake is
flagged at write-time in future sessions.

Safe by construction: candidates are provisional + prunable, dedup is strict on
id, regexes are validated, and a signature without a `content_present` is skipped
(a path-only review trigger would fire on every edit to that path — pure noise).
Malformed input is non-fatal: exits 0, index untouched.

Input shapes accepted (liberal):
  - a list of findings
  - a list of reviewer results ({agent, batch_label, findings: [...]})
  - a dict with a top-level "findings" array

Env: INJECT_TRIGGERS_FILE overrides the index path (used by tests).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import capture_trigger as ct  # noqa: E402


def extract_findings(data):
    """Normalise assorted review payloads into a flat list of finding dicts."""
    if isinstance(data, dict):
        data = data.get("findings", [])
    if not isinstance(data, list):
        return []
    findings = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("findings"), list):
            # reviewer-result object: flatten, propagating attribution
            label = item.get("batch_label") or item.get("agent")
            for f in item["findings"]:
                if isinstance(f, dict):
                    if label and "batch_label" not in f:
                        f = dict(f, batch_label=label)
                    findings.append(f)
        else:
            findings.append(item)
    return findings


def _source(finding):
    label = finding.get("batch_label") or finding.get("agent") or "orchestrator"
    return "review: {}".format(label)


def process(findings, triggers_path, severity="candidate"):
    """Capture a candidate trigger for each finding with a usable trigger_signature."""
    results = {"captured": [], "exists": [], "skipped": [], "errors": []}
    project_root = ct.default_root()
    for f in findings:
        if not isinstance(f, dict):
            continue
        ts = f.get("trigger_signature")
        if not isinstance(ts, dict):
            continue
        if not ts.get("content_present"):
            results["skipped"].append(
                {"id": ts.get("id"), "reason": "no content_present (would fire on every edit to the path)"}
            )
            continue
        pattern_ref, warn = ct.resolve_pattern_ref(ts.get("pattern_ref"), project_root)
        if warn:
            sys.stderr.write("capture_from_review: {} ({})\n".format(warn, ts.get("id")))
        try:
            trigger = ct.build_trigger(
                id=ts.get("id") or "",
                message=ts.get("message") or f.get("description") or "review finding",
                path_glob=ts.get("path_glob") or [],
                domains=ts.get("domains"),
                content_present=ts.get("content_present"),
                content_absent=ts.get("content_absent"),
                pattern_ref=pattern_ref,
                source=_source(f),
                severity=severity,
            )
        except ValueError as e:
            results["errors"].append({"id": ts.get("id"), "error": str(e)})
            continue
        try:
            status = ct.capture(triggers_path, trigger)
        except Exception as e:  # IO/permission failure must not abort the review
            results["errors"].append({"id": trigger["id"], "error": "capture failed: {}".format(e)})
            continue
        results["captured" if status == "added" else "exists"].append(trigger["id"])
    return results


def _summary(results):
    lines = []
    if results["captured"]:
        lines.append("captured {} candidate trigger(s): {}".format(
            len(results["captured"]), ", ".join(results["captured"])))
    if results["exists"]:
        lines.append("{} already present (no-op): {}".format(
            len(results["exists"]), ", ".join(results["exists"])))
    if results["skipped"]:
        lines.append("{} skipped (no content signature): {}".format(
            len(results["skipped"]), ", ".join(str(s.get("id")) for s in results["skipped"])))
    if results["errors"]:
        lines.append("{} error(s): {}".format(
            len(results["errors"]),
            "; ".join("{}: {}".format(e.get("id"), e.get("error")) for e in results["errors"])))
    if not lines:
        lines.append("no trigger_signature findings — nothing captured")
    return "\n".join(lines)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        raw = open(argv[0]).read() if argv else sys.stdin.read()
        data = json.loads(raw)
    except Exception as e:
        sys.stderr.write("capture_from_review: could not read findings JSON ({}); nothing captured\n".format(e))
        return 0
    triggers_path = os.environ.get("INJECT_TRIGGERS_FILE") or os.path.join(
        ct.default_root(), "docs", "rules", "triggers.json"
    )
    results = process(extract_findings(data), triggers_path)
    sys.stdout.write(_summary(results) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
