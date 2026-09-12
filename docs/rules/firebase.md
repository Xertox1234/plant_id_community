# Firebase — binding rules

Compact checklist auto-injected before edits. Long-form:
`plant_community_mobile/docs/patterns/firebase-auth.md`,
`firebase/docs/patterns/`.

- **Firebase auth → Django JWT exchange**: the Firebase ID token is exchanged
  for a Django JWT; backend verifies the Firebase token server-side.
- **Redact PII from logs** — emails and tokens are GDPR-sensitive; never log them
  raw on the auth path.
- **Cloud Functions are idempotent** — guard against duplicate event delivery;
  minimize cold-start work (lazy-init heavy clients).
- **Firestore security rules deny by default** — every collection has explicit
  read/write rules scoped to the owner.
- IAM follows least privilege — no broad `Editor`/`Owner` service accounts.
- Secrets via Secret Manager / env, never committed to the repo.
- **One canonical Firebase credentials setting** — every module (auth exchange,
  FCM sender, availability gates) reads `settings.FIREBASE_CREDENTIALS_PATH`;
  it absorbs `GOOGLE_APPLICATION_CREDENTIALS` in settings.py, set-but-empty
  disables. Two knobs read by different modules = push silently dead on the
  config half the docs describe (todo 253 slice 6). Never create a
  credential-less default firebase_admin app when a credentials path IS
  configured but failed — the FCM sender's get_app() reuse would adopt it and
  burn retries instead of skipping cleanly.
- **Never merge an edit to `firebase/*.rules` without deploying it in the same
  motion.** A committed rules file, a `firebase.json` entry and an old green
  deploy log are all consistent with production serving something else — the
  2026-05-23 Storage tightening sat undeployed for 3.5 months, and todo 224 was
  the same shape. Deploy, then verify through the **Rules API**, never from the
  CLI's exit code: `python3 scripts/check_firebase_rules_drift.py` (exit 0 match, 1 drift,
  2 could-not-determine). Deploy from the checkout that holds the edit — in a
  worktree that is the worktree path, not the main checkout.
