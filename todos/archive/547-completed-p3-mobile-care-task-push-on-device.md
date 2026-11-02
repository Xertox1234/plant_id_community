---
status: completed
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

- [x] A CareTask created in the mobile garden fires an FCM push when it
      falls due, verified end to end on a device. Record the date, the build
      and what was observed. (completed 2026-11-02: owner on iPhone, TestFlight build 16; see Work Log)

## Work Log

### 2026-11-02 - Care-task push observed on device (owner)

Setup: the owner's iPhone on TestFlight build 16 (uploaded 2026-10-17; it contains todo 386's garden and todo 621's push routing; the build number was not read back from the device), signed in as `plantadmin`, against prod.

Steps: Home → Care Schedule → Add plant ("House plant 1") → calendar-plus icon → Repeat **Once**, First due **today** → Schedule. A confirmation appeared and the task showed under Due care as "Watering House plant 1 · Due today".

| State | Result |
|---|---|
| Foreground | The care-task notification arrived within the ~15 min beat window (`care-task-reminders`); tapping it opened Care Schedule. |

Side observation: the owner tapped the skip icon on the first task by accident. It left Due care as expected, and a second task was scheduled for the check. Skip was not under test here.

Not covered: background and killed presentation of the care push (the forum-reply push covered all three states in todo 648), Android (todo 387).

## Notes

Owner hand-off: needs a TestFlight (or debug) build that contains todo 386's
garden, plus prod or dev FCM credentials. See the iOS signing / APNs and prod
FCM notes in `docs/LEARNINGS.md`.
