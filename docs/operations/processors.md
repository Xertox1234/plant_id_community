# Processor register

Taken on 2026-11-10 (auth + legal audit, rows M20 and L15; todos 702 and 707).

Every outside service that receives personal information from Houseplant MD:
what it gets, what our account-deletion job already removes there, and how to
ask the service to delete what the job cannot reach. Update this file in the
same pull request as any change that sends personal information somewhere new.

"The job" is `request_account_deletion` and the steps it queues
(`backend/apps/users/deletion.py`). "Unsourced" means the service's own
documentation was looked for on 2026-11-10 and did not answer the question;
it is a gap to close by asking the service, not a guess.

## The register

| Processor | What it receives | What the job removes there | What stays, and for how long |
|-----------|------------------|----------------------------|------------------------------|
| Railway (servers, Postgres, Redis; United States) | Everything in the database | Every row of the account (steps `forum`, `email`, `django`) | Database backups: unsourced |
| Cloudflare (website, R2 file storage) | Avatars and forum images (public bucket), scan photos (private bucket), web requests | Avatar files, scan photos, and forum images no post still uses | Request logs: unsourced |
| Google Firebase (login, Firestore, push) | Email, password hash or Google sign-in, saved plants under `users/{uid}`, push token | `users/{uid}` and everything under it (step `firestore`); the login (step `firebase_auth`) | Google's own logs and backups: unsourced |
| Apple (push) | Device push token, notification text | Nothing to remove: we blank our copy of the token | Unsourced |
| Plant.id (Kindwise; Czech Republic) | Scan photos only, as image data. No name, email or account id is sent, and we do not keep the request's access token | Nothing | The result is available for 6 months (Kindwise handbook). Whether the photo is kept as long: unsourced |
| PlantNet (France) | Scan photos only, as image data | Nothing | The API terms say photos "are not stored in the database" and are held in memory only while the request runs |
| OpenAI (United States) | Text of posts and private messages from new or not-yet-trusted members (spam screen); title and opening post of public topics (search index); text sent to an AI feature. No email address | Nothing | Abuse-monitoring logs: up to 30 days for embeddings and completions, none for moderation requests. Not used for training |
| Sentry (United States) | Error reports from the website and servers; a masked recording of a website session that hit an error. `send_default_pii` is off and request bodies are never sent | Nothing | Errors and replays: 90 days on Team and Business plans, 30 days on Developer |
| Resend (United States) | Recipient address and the content of each email we send | Nothing | Per the plan's retention window; its length is unsourced |
| Apple and Google (stores) | Purchase receipts (when in-app purchase ships) | Nothing | Held by the store under its own terms |

YouTube and Vimeo are not processors: a video a member embeds loads from that
service in the viewer's browser.

## Deletion routes

Use these when a person asks for deletion beyond what the job does, and always
for an account deleted as under the minimum age.

- **Plant.id (Kindwise).** No route by account: nothing we send identifies the
  person, and we keep no token for the request. Kindwise's FAQ says deleting
  an identification costs no credits, so a delete call exists, but it needs
  the request's access token, which we do not store. Route: email
  `support@kindwise.com` with the API key's account and the date range, and
  ask for the images to be deleted. Otherwise the result expires in 6 months.
- **PlantNet.** Nothing to delete by its terms. For a written confirmation,
  use the contact page linked from the API terms.
- **OpenAI.** No per-request delete. Logs expire within 30 days. An
  organisation can apply for zero data retention; that is approval-based.
- **Sentry.** Delete the issue, or the replay, in the Sentry interface or
  through its API. Find it by the time of the request; reports carry no email
  address. Otherwise it expires with the plan's retention period.
- **Resend.** No per-email delete was found in its documentation. Route:
  Resend support, naming the recipient address. Turning off content storage
  is a paid add-on with eligibility rules.
- **Google Firebase and Apple.** The job removes the login and the saved
  plants. For anything further, use the provider's data-request form from the
  developer account.
- **Railway and Cloudflare.** The job removes the rows and files. Backups and
  logs age out on the provider's schedule (unsourced).

Record each request sent to a processor, and its answer, with the access or
deletion request it belongs to (`docs/operations/access-requests.md`).

## Sources

Read on 2026-11-10.

- Kindwise handbook: <https://www.kindwise.com/handbook>; FAQ:
  <https://www.kindwise.com/faq>
- Pl@ntNet API terms: <https://my.plantnet.org/terms_of_use>
- OpenAI, "Your data": <https://developers.openai.com/api/docs/guides/your-data>
- Sentry retention periods:
  <https://docs.sentry.io/security-legal-pii/security/data-retention-periods/>;
  security page: <https://sentry.io/security>
- Resend, message content storage:
  <https://resend.com/docs/knowledge-base/how-do-i-ensure-sensitive-data-isnt-stored-on-resend>

## Open

- Agreement (data-processing terms) link for each processor: not collected.
- Storage region, read 2026-11-11: Sentry ingests at `ingest.us.sentry.io`
  (United States); both R2 buckets are `WNAM` (western North America) with
  jurisdiction `default`; Railway `us-west2`; Firestore `nam5`. Still not
  sourced: Resend's sending region (a dashboard setting) and whether OpenAI
  processes outside the United States.
- Every "unsourced" cell above.
