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
