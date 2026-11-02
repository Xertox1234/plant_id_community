# Scan 2.0 Part 2: diagnosis-first app, daily limits, background scan jobs — design

Date: 2026-11-02 · Status: draft for owner review · Platform: Flutter mobile app, Django backend

Parent spec: `docs/superpowers/specs/2026-10-24-scan-2-0-design.md` (sections 2,
"Submit and background processing", and "Settled after the builder check").
That spec still applies. This document adds what the 2026-11-02 brainstorm
decided and narrows Part 2's scope.

Marking: **[owner]** means the owner decided it. **[call]** means the author
decided it and the owner has not confirmed it. Unmarked text is description.

## Intent

The app is no longer an identification app. **Its primary job is diagnosis,
which almost always includes an identification.** **[owner]** The UI must say
so. It offers a diagnosis by default, with "just identify it" as the lighter,
cheaper second option. **[owner]** Part 2 also does what the parent spec
scheduled for it: the scan runs on the server in the background, and a push
notification brings the user back to the result.

Why now: Part 1 (the guided camera, #1197, TestFlight build 17) shipped the
diagnosis-first camera. Everything around it still says "identify": the home
hero, the centre bottom-bar button and the onboarding checklist. The submit
also still sends one photo synchronously, and in diagnosis mode that photo is
the leaf shot, not the problem shot.

## Current state (verified in code, 2026-11-02)

- **Camera.** `plant_community_mobile/lib/features/scan/` has
  `ScanMode { diagnose, identify }` and `CaptureRole { problem, leaf, whole,
  flower }` (`capture_steps.dart`). Identify mode already drops the problem
  step, so it needs no separate flow. Diagnose is the default mode.
- **Submit.** The camera hands one image to the old synchronous
  `POST /plant-identification/identify/` (`api/simple_views.py:163`). In
  diagnose mode that image is the leaf shot.
- **Limits.** There is **no per-user daily allowance.**
  - Per user: a burst limit of 100/h (`RATE_LIMITS["authenticated"]["plant_identification"]`).
  - App-wide, Plant.id: `PLANT_ID_DAILY_QUOTA = 3` and `PLANT_ID_MONTHLY_QUOTA = 100`
    (constants in `constants.py:61-62`, enforced in
    `services/quota_manager.py:102` and `:162`).
  - App-wide, PlantNet: `PLANTNET_DAILY_QUOTA = 500`.
- **Premium.** `User.is_premium` (`apps/users/models.py:254`) and
  `IsPremiumUser` (`apps/users/permissions.py:6`) already exist.
- **Server pieces.**
  - Push: `apps/core/fcm.py:102` `send_fcm_message`, and the garden reminder
    task `send_care_reminder_to_device` (`apps/garden_calendar/tasks.py:536`)
    is a worked example.
  - Celery is live in prod.
  - `USE_R2` media storage is live.
- **Mobile push.** `push_message_router_service.dart` and
  `push_foreground_presenter.dart` route and present incoming pushes.
- **Existing models.** `PlantIdentificationRequest` already has
  `request_id` (UUID), `user`, `status` and up to three image slots
  (`models.py:310`), but it has no role per image.
- **Home screen and bottom bar.** Identify-first copy appears in:
  - `features/home/home_page.dart:98–189`: "Plant identification community",
    "Identify a plant", "Instant Identification", and a separate "Diagnose a
    Sick Plant" card.
  - `core/routing/main_shell.dart:173`: the centre button "Identify a plant".
  - `features/onboarding/onboarding_checklist_card.dart:20`: "Identify your
    first plant".

## Goals

1. The app presents itself as diagnosis-first: home, bottom bar and
   onboarding. **[owner]**
2. The user chooses **Diagnose** (default) or **Just identify it**. Identify
   is cheaper and skips the "Show me what's wrong" step. **[owner]**
3. A per-user daily allowance: **free 1, premium 3**. **[owner]** (See "Daily
   limits" for what these count.)
4. Scans run on the server in the background. A notification opens the result.
   **[owner, parent spec]**
5. The submit sends **every** shot, each with its role. In diagnosis mode the
   problem shot drives the diagnosis. **[owner, parent spec]**
6. The photos go to the backend and are stored in R2. Firebase Storage is no
   longer used for scans. **[owner, 2026-10-25]**

## Non-goals (Part 2)

- The full new results screen (confidence bars, accept/reject, alternatives).
  That is Part 3. Part 2's notification opens the **existing** results screen,
  loaded by job id from the stored job result, **plus a minimal diagnosis
  block** (see section 6). **[owner: diagnosis shown in Part 2; call: minimal block]**
- Care guides and treatment plans (Part 4); reminders and the follow-up scan
  (Part 5).
- The web app. Mobile is primary. **[call]**
- Buying Plant.id commercial access. The owner will buy it closer to launch;
  the current plan is enough for testing. **[owner]**
- App-store listing copy. **[call]**

## Anti-goals

- A user waits on a scan that was never going to run (out of allowance, or the
  app-wide cap is hit). That check happens before upload. **[call]**
- A failure, or a cancel, that costs the user their one daily diagnosis. **[call]**
- A scan lost because the app was backgrounded or killed after upload. **[parent spec]**
- Limits hard-coded so that the plan upgrade at launch needs a code change. **[call]**

## 1. Diagnose vs Just identify

- **Diagnose** (default): steps problem → leaf → whole → flower. Only the
  problem shot is required. The server runs identification **and** the health
  assessment. **[owner]**
- **Just identify it**: steps leaf → whole → flower. Only the leaf is
  required. The server runs identification only, with no health assessment.
  **[owner]**
- **Identify-only routing.** Identify-only scans go to **PlantNet first**
  (500/day), and Plant.id is called only when PlantNet's top match is below a
  confidence floor. So they barely use the scarce Plant.id budget. A diagnosis
  always calls Plant.id, because the health assessment lives there. **[call]**
  The floor value is left to the builder; start from the existing combined-service merge thresholds.
- The mode chip on the camera stays as built in Part 1. Switching modes keeps
  any shots already taken whose role exists in the new mode. **[call]**

## 2. Daily limits

- **Free: 1 diagnosis a day. Premium: 3 diagnoses a day.** **[owner]**
- **Identify-only scans have their own, larger allowance: free 5 a day,
  premium 20.** They do not use up diagnoses. **[call: the owner left "how much a
  diagnosis affects the limits" to the author; these numbers are the author's guess]**
- **The day resets at local midnight**, using the UTC offset the app sends with
  the scan (`utc_offset_minutes`; the app has no IANA time-zone package). If it
  sends none, use UTC. **[call]**
- **What counts.** A scan counts when its job **succeeds**. A job that fails
  on our side, or is cancelled before it produced a result, does not count.
  **[call]** Reserve a slot when the job is created, so that two quick taps can't both get the last slot, and release it on failure or cancel. **[call]**
- **Before the camera sends anything**, the app asks the server what's left
  (or reads it from a recent response). Done is refused before upload when the
  allowance or the app-wide Plant.id cap is exhausted. **[call]**
- **When out:**
  - **Free, out of diagnoses:** an upgrade prompt ("No checks left today · Go
    premium for 3"). Just identify still works while identify allowance
    remains. **[call]**
  - **Premium, out of diagnoses:** "You've used today's 3 checks. More at
    midnight." **[call]**
  - **App-wide Plant.id cap hit:** diagnoses pause for everyone with "Plant
    checks are busy right now, try again later", and the user's allowance is
    not touched. Identify-only keeps working through PlantNet. **[call]**
- **Everything is a setting.** Read the per-user allowances (free and premium,
  diagnose and identify) and the app-wide Plant.id daily and monthly caps from
  Django settings, sourced from env with today's values as defaults. Moving to
  commercial Plant.id access is then an env change. **[owner: current plan stays;
  call: settings shape]**
- The existing 100/h burst limit stays as a second line of defence. **[call]**

## 3. Background scan job

- **A new endpoint** creates a scan job from multipart photos, each tagged with
  its role (`problem`, `leaf`, `whole`, `flower`) and the mode. It returns the
  job id at once. The old `identify/` and `disease-requests/` endpoints stay
  unchanged for installed app versions. **[parent spec]**
- **The photos are stored in R2, privately.** **[owner 2026-10-25: R2;
  owner 2026-11-02: private]** Today's default R2 storage serves every file at a
  permanent public URL (`settings.py:564-568`, `custom_domain` +
  `querystring_auth: False`), so scan photos must **not** use it. They need a
  separate private storage (a private bucket or prefix with no public domain).
  The app reaches them only through short-lived signed URLs, or an
  authenticated endpoint that checks the photo belongs to the requesting
  user. **[call: mechanism left to the builder, but it must be private]**
  The photos are user-scoped and deleted with the job and with the user's
  account. Retention is left to the builder. The parent spec says the problem
  photo must outlive the job when Part 5 reminders are set, so don't design
  that out.
- **A Celery task** runs the providers.
  - PlantNet gets every non-problem shot with its organ.
  - Plant.id gets the shots for identification, plus the problem shot for the
    health assessment in diagnose mode.
  - The task retries a provider hiccup **once** by itself, then records failure.
    **[call]**
  - How the `problem` role maps onto PlantNet organs is left to the builder
    (parent spec).
- **The result is stored server-side** under the job id, so a notification can
  deep-link to it and the app can fetch it again after a restart. **[parent spec]**
- **Status endpoint**: the app can ask a job's state: pending, done, failed or
  cancelled. Cancel is an action on the job. **[call]** The API shape is left to
  the builder.
- **When the job finishes**, send an FCM push:
  - "Your plant check is ready", or "We couldn't check your plant".
  - Its data names the job, so the push router opens it.
  - There is no push for "still working". **[call]**
  - Reuse `send_fcm_message`, following the garden-reminder task's handling of
    dead tokens and retries.
- **Reuse or new model** is the builder's choice. `PlantIdentificationRequest`
  has the UUID, user and status, but only three image slots and no role per
  image. Four role-tagged shots may need a child image table. **[call: left to
  builder, with that constraint noted]**
- **Firebase Storage** is no longer touched by the scan. **Correction to the
  parent spec:** Part 1 did *not* move the upload to "Add to collection". Today
  every scan still uploads to Firebase Storage (`plant_identification_service.dart:36`)
  and is auto-saved to My Collection in Firestore (`scan_submitter.dart`
  `_persistPlantOffline` → `users/{uid}/identified_plants`), and there is no
  "Add to collection" button yet. That button is Part 3. Part 2 removes the
  Firebase upload and **keeps the auto-save**. When a job finishes, the app
  writes the collection entry as today, but its image reference points at the
  server's private photo (resolved through the signed-URL/endpoint mechanism
  above) instead of a Firebase URL. If the app was killed, the entry is written
  the next time the app sees the finished job (on push tap, or on next launch
  through the pending-jobs check). **[call]**
- **Partial results and the allowance.** **[call]**
  - **Diagnose: the plant is named, but the health assessment failed or was
    unavailable.** The job is done-but-degraded. It is charged as an
    **identify**, not a diagnosis. The result says "We named your plant but
    couldn't check its health. Your check wasn't used." Try again is offered.
  - **Diagnose: Plant.id failed and PlantNet named the plant.** Same as the
    case above.
  - **Identify-only: PlantNet is below the floor and the Plant.id fallback
    failed.** Return PlantNet's best match as a low-confidence result, and
    charge it as an identify.
  - **Nothing usable from any provider.** The job fails and costs nothing.
- **The app-wide Plant.id cap counts real calls.** **[call]**
  - A diagnosis makes two Plant.id calls (identification plus
    `/health_assessment`). Today the counter goes up once
    (`plant_id_service.py:435`).
  - Enforce both the daily and the monthly cap. Today only the daily cap is
    checked (`quota_manager.py:102-118`).
  - Identify-only fallbacks to Plant.id may not use the last slots a
    diagnosis needs: reserve 2 calls' headroom for diagnoses.

## 4. The wait (mobile)

- After **Done**, the photos upload with visible progress. The camera then
  closes, and a small **"Checking your plant…"** pill stays on screen across
  the app until the result arrives. **[parent spec]**
- **Slow.** If there is no result after about **45 seconds**, the pill expands
  to:
  > This scan is taking a little longer than usual.  **Wait** · **Cancel**

  **[owner: wording and the Wait/Cancel choice; call: 45 s]**
  - **Wait** shrinks it back to the pill and keeps going.
  - **Cancel** cancels the job. Its result is thrown away and it does not use
    the allowance. **[call]**
- **Failed.** The pill becomes "We couldn't check your plant" with **Try
  again**. The photos are kept on the phone until the job succeeds or the user
  dismisses it, so there's no reshoot. A failure does not use the allowance.
  **[call]**
- **Done.**
  - App in the background: a system notification.
  - App open: an in-app banner through `push_foreground_presenter`.
  - Either way, tapping it opens the result. **[parent spec]**
- **The app is killed mid-wait.** On the next launch, the app finds the
  pending job (from local storage or a "my pending jobs" call) and restores
  the pill. The push still arrives either way. **[call]**
- **One scan at a time.** While a job is pending, the camera's Done is
  disabled and Check a plant opens the pending scan's status instead of a
  second camera. **[call]**
- The slow prompt and the failure state appear **only in the app**. There is
  no push for "slow". **[call]**

## 5. Diagnosis-first home, bottom bar and wording

The layout was chosen from mockups: **A, "one big action"**. **[owner]**

- **Home hero.**
  - Label "Plant health check".
  - Headline "What's wrong with your *plant?*"
  - Body: "Photograph the problem. We'll name the plant, find the cause and
    tell you what to do."
  - One primary **Check a sick plant** button, with today's count under it
    ("1 check left today").
  - A quiet **Just identify a plant** text link under it, which opens the
    camera in identify mode.
  - **[owner: layout A; call: exact copy]**
  - Out of diagnoses, the count line reads "No checks left today · Go premium
    for 3" (free) or "More checks at midnight" (premium). **[call]**
- **Bottom bar.** The centre button becomes **Check a plant** with a
  stethoscope icon, and opens the camera in diagnose mode. **[owner: mockup;
  call: icon]**
- **Feature list.** Remove "Instant Identification" and "Diagnose a Sick Plant",
  because the hero covers both. My Plants, Care Instructions, Care Schedule,
  Forum and Blog stay. **[call]**
- **Onboarding.** "Identify your first plant" becomes "Check on your first
  plant". Keep its completion key (`identify_plant`) so existing progress
  survives. **[call]**
- **The old Diagnose screen** leaves navigation. The `/diagnose` route opens
  the new camera in diagnose mode. Delete the screen once nothing links to it.
  Its backend endpoint stays. **[parent spec]**
- **The "Join the forum" ghost button** in today's hero is dropped from the
  hero. The Forum tab and feature card remain. **[call]**
- Follow Canopy and `plant_community_mobile/docs/patterns/flutter-ui-design.md`.
  The mockup is in `.superpowers/brainstorm/` (gitignored, local only).

## 6. Showing the diagnosis in Part 2

The owner decided the user must see the diagnosis in Part 2. A diagnosis
that uses up the daily check but shows only a name is not acceptable.
**[owner]**

- Today the old results screen takes a `Plant` through `state.extra`
  (`features/results/results_screen.dart`). `Plant` (`lib/models/plant.dart`)
  has no health or confidence fields, and `plant_identification_service.dart`
  drops `disease_detection`.
- Part 2 adds a results route that **loads by job id** from the server, so the
  notification and the restored pill can open it after a restart. **[call]**
- The client gets a result model that carries the diagnosis (top problem
  name, confidence and a short description, or healthy) and the
  identification confidence. **[call]**
- A **minimal diagnosis block** sits at the top of the existing results
  screen. **[call]**
  - Diagnosed: the likely problem, its confidence as a percentage and a
    one-line description.
  - Healthy: "Looks healthy".
  - Degraded: "We couldn't check its health this time".
  - The identification shows its confidence percentage.
  - Styling follows Canopy. The full layout (colour bands, alternatives,
    accept/reject) is Part 3, which replaces this block.

## Constraints

- No direct push to main. Feature branches and PRs.
- The repo is public. No keys in the client. Provider calls stay server-side.
- Riverpod 3.x, Canopy, and the full `flutter test` before any PR push (Part 1
  lesson).
- Backend tasks follow `docs/rules/celery.md`. Push follows the existing FCM
  helpers.
- Rate limits return a real 429 (CLAUDE.md gotcha 4), and an exhausted
  allowance must be distinguishable from a burst limit in the response, so the
  app can show the right message.

## Left to the builder

- The API shapes: create job, status, cancel, pending-jobs, allowance.
- The job model: reuse `PlantIdentificationRequest`, or add a new model plus a
  child image table.
- The `problem`-role-to-organ mapping and the identify-only PlantNet
  confidence floor.
- Photo retention, keeping Part 5's needs in mind.
- The private-photo mechanism: a private bucket or prefix, and signed URLs or an
  authenticated proxy endpoint.
- How the allowance is stored (a DB count of jobs per local day is simplest,
  or Redis).
- Phasing inside Part 2. A suggested order:
  1. Backend: job, limits and push, behind the new endpoint.
  2. Mobile: submit, pill and wait states.
  3. Mobile: home, bottom-bar and wording changes. These can ship before step 1,
     since they don't depend on it.
