---
status: pending
priority: p3
issue_id: "547"
tags: [mobile, flutter, fcm, device]
dependencies: ["386"]
triage: blocked-device
triaged: 2026-10-10
blocked_on: "An owner check on a physical device or TestFlight build after todo 386's garden code ships"
---

# On-device check: a due CareTask fires an FCM push

## Problem

Todo 386 builds the mobile garden and routes `care_task_due` pushes to it.
Its fourth acceptance criterion needs an end-to-end check on a real device,
which no worker can do. The owner split it out on 2026-10-10 (run
2026-10-11-0053) so the code can ship and 386 can archive.

The criterion came from todo 410 AC 1 and was re-pointed to 386 on 2026-09-27.

## Acceptance Criteria

- [ ] A CareTask created in the mobile garden fires an FCM push when it
      falls due, verified end to end on a device. Record the date, the build
      and what was observed.

## Notes

Owner hand-off: needs a TestFlight (or debug) build that contains todo 386's
garden, plus prod or dev FCM credentials. See the iOS signing / APNs and prod
FCM notes in `docs/LEARNINGS.md`.
