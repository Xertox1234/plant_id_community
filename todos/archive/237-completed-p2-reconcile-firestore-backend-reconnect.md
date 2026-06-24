---
status: completed
priority: p2
issue_id: "237"
tags: [mobile, firestore, sync, api, architecture-decision]
dependencies: ["224"]
---

# Reconcile Firestore plant collection with the Django backend on reconnect

## Resolution (2026-06-24): premise invalid — collections are separate by design

Investigation while picking this up found the todo's founding premise — a **dual
write on the identify call** that can **drift** — does not exist in the code. There
is no reconciliation to build, because there is no second authoritative store to
reconcile against. Decision (owner-approved): **document the real architecture as
the source-of-truth decision and close; build no sync layer.** Details below.

## Corrected facts (what the code actually does)

- **The identify endpoint is stateless.** Both web and mobile call
  `POST /api/v1/plant-identification/identify/`
  (`backend/apps/plant_identification/api/simple_views.py::identify_plant`). It runs
  Plant.id + PlantNet via `CombinedPlantIdentificationService.identify_plant` and
  returns JSON. **It persists nothing.** The `user=` argument threaded into the
  service is accepted but never used to create or save any row
  (`combined_identification_service.py:179-251`). There is no `PlantIdentificationRequest`,
  `PlantIdentificationResult`, or `UserPlant` written by the identify path.
- **Mobile writes only to Firestore.**
  `plant_community_mobile/lib/features/camera/camera_screen.dart::_identifyPlant`
  calls the stateless identify endpoint, then fire-and-forget
  `_persistPlantOffline(plant)` → `firestoreServiceProvider.savePlant(uid, plant)`.
  This Firestore `plants` collection is read back by `CollectionScreen` via
  `plantsStreamProvider` (wired in todo 224) — it is the mobile collection and **is**
  user-facing.
- **The backend `UserPlant` collection is a separate, write-only system.** It is
  populated only when the **web** app calls `saveToCollection`
  (`web/src/services/plantIdService.ts:102` → `POST …/plant-identification/plants/`)
  from the "Save to My Collection" button. There is **no client that reads it back**:
  no web "My Plants" / collection list page or route, no GET of `…/plants/`, and the
  mobile app never POSTs to or reads `…/plant-identification/plants/`. (The only
  `/plants/` the mobile app references is `/calendar/api/plants/`, the unrelated
  garden-calendar system.) The `add_to_collection` viewset action
  (`views.py:~300-360`) needs a `PlantIdentificationResult`, which the real identify
  flow never creates — outside demo-data seeding
  (`backend/apps/users/services.py:611`), those rows are not produced.

So there is no dual-write drift. There are two **independent** collections — mobile
(Firestore, read by `CollectionScreen`) and backend (`UserPlant`, written by web,
**read by nothing**) — that never meet. Building a Cloud Function / ingest / reconcile
layer (the original Option 1) would sync mobile data **into a backend collection no
client displays**: effort for zero user-visible benefit, on top of a premise that
does not hold.

## Decision (source of truth)

- **Mobile plant collection: Firestore is the source of truth.** Offline-first via
  `savePlant`; read back through `plantsStreamProvider` → `CollectionScreen`. No
  backend mirror.
- **Web "Save to My Collection": backend `UserPlant` (Postgres) is the store**, but
  it is currently a **write-only sink** (no read surface). Tracked as a follow-up —
  see todo **243** — to either give it a read surface or remove the dead write.
- **The two collections are intentionally separate.** Cross-platform "one unified My
  Plants across web + mobile" is **not** a current goal. If it becomes one, it is a
  multi-day epic (choose a single source of truth, add the missing read surfaces,
  build sync) — not this todo.

This recorded decision satisfies the original intent of acceptance criterion #1
("a documented decision on the source of truth"). The remaining original criteria
(#2 reconcile pass, #3 reconcile integration test, #4 idempotency) are **withdrawn as
not applicable** — they presuppose the dual-write that does not exist, so there is
nothing to build or test.

## Original framing (filed 2026-06-22 — premise since invalidated)

> An identified plant is written to two independent stores with no link between them:
> the Django backend (during the identify API call) and Firestore … Nothing reconciles
> them when connectivity returns, so the two can drift.

The "Django backend writes during the identify API call" assumption is the part that
turned out to be false; see Corrected facts above.

## Acceptance Criteria

- [x] A documented decision on the source of truth lands in this todo (Decision
      section above) and in `docs/LEARNINGS.md` for discoverability.
- [x] The write-only backend `UserPlant` collection is captured as a follow-up todo
      (243) rather than silently dropped.
- [x] No sync/reconcile code is added (the premise that required it is invalid).

## Technical Details (verified during investigation)

- Stateless identify: `backend/apps/plant_identification/api/simple_views.py`
  (`identify_plant`) → `services/combined_identification_service.py`
  (`identify_plant`, `user` unused).
- Mobile write/read: `plant_community_mobile/lib/features/camera/camera_screen.dart`
  (`_identifyPlant`, `_persistPlantOffline`) →
  `plant_community_mobile/lib/services/firestore_service.dart`
  (`savePlant`, `getPlantsStream` / `plantsStreamProvider`).
- Web backend collection write (no read surface):
  `web/src/services/plantIdService.ts` (`saveToCollection` →
  `POST …/plant-identification/plants/`); UI in
  `web/src/pages/IdentifyPage.tsx` /
  `web/src/components/PlantIdentification/IdentificationResults.tsx`.
- Backend collection models/actions: `backend/apps/plant_identification/models.py`
  (`UserPlant`, `PlantIdentificationResult`),
  `backend/apps/plant_identification/views.py` (`add_to_collection`, `plants` viewset).

## Work Log

### 2026-06-22 - Filed

- Created from a todo-224 implementation follow-up (Firestore↔backend drift). Not
  yet started.

### 2026-06-24 - Started by completing-todos skill (run 2026-06-24-1509)

- Picked up by automated workflow.

### 2026-06-24 - Premise invalidated by investigation; re-scoped to a documented decision

- Traced both identify paths: `POST /plant-identification/identify/` is stateless
  (`simple_views.identify_plant` → `CombinedPlantIdentificationService.identify_plant`,
  `user` arg unused, no `.create`/`.save`). No backend record is written on identify,
  so the "dual-write drift" the todo was built on does not exist.
- Established that mobile = Firestore (read by `CollectionScreen`) and backend
  `UserPlant` = web-write-only (no list page / no GET / mobile never touches it).
  Reconciling into the backend collection would have no reader.
- Consulted the advisor (confirmed the read is airtight; this is a pause-for-decision,
  not a buildable completion) and surfaced the product decision to the owner, who
  chose **re-scope: separate by design**.
- Recorded the source-of-truth decision here, added a `docs/LEARNINGS.md` entry, and
  filed follow-up todo 243 for the write-only backend collection. No sync code added.

### 2026-06-24 - Completed by completing-todos skill (run 2026-06-24-1509)

- Verification: all 3 re-scoped acceptance criteria passed with evidence —
  `grep "Decision (source of truth)"` and `grep "Plant collection architecture (todo 237"`
  each returned 1 (decision recorded in this todo + `docs/LEARNINGS.md`); todo 243
  present; `git status --short` filtered for non-`.md`/non-`todos/` paths returned
  "(none — docs/todos only)", confirming no sync/reconcile code was added.
- Review: code-review-orchestrator not dispatched — the diff is documentation-only
  (this todo, `docs/LEARNINGS.md`, new todo 243); no code files changed, so no domain
  reviewer applies. 0 findings.
- Outcome: closed as a documented architecture decision (re-scope: separate by
  design), not a built reconcile feature.

## Notes

- Original priority p2 reflected a feared data-consistency gap. With the premise
  invalidated, there is no live drift between user-visible surfaces (the backend
  collection has no reader), so nothing user-facing is at risk today. The residual
  item is the dead web write, tracked at p3 in todo 243.
- Related: todo 236 (emulator round-trip test — also predicated on backend↔Firestore
  sync; revisit in light of this decision), archived todo 224, and new todo 243.
