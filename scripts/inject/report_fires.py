#!/usr/bin/env python3
"""Report trigger fire counts from the inject-fires log.

Usage:
  python3 scripts/inject/report_fires.py

Log path defaults to /tmp/inject-fires.log; override with INJECT_FIRES_LOG.
Each line in the log: <ISO-timestamp>\t<rel-file>\t<trigger-id>
"""
import os
import sys
from collections import Counter


def main():
    log_path = os.environ.get("INJECT_FIRES_LOG", "/tmp/inject-fires.log")

    if not os.path.exists(log_path):
        print("No fire log at {} — no triggers have fired yet.".format(log_path))
        sys.exit(0)

    counts = Counter()
    total = 0
    with open(log_path) as fh:
        for line in fh:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                counts[parts[-1]] += 1
                total += 1

    if not counts:
        print("Log exists but contains no valid entries.")
        sys.exit(0)

    print("Trigger fire counts ({}, {} total fires):".format(log_path, total))
    for trigger_id, count in counts.most_common():
        print("  {:4d}  {}".format(count, trigger_id))


if __name__ == "__main__":
    main()
