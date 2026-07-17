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
